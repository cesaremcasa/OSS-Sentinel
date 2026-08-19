from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src import cli
from src.analyze import analyze_labels, calculate_pain_index, feature_engineering, run_analysis
from src.enrichment import EnrichmentEngine
from src.ingestion import IngestionEngine, IngestionError
from src.providers import FakeProvider, OpenAIProvider
from src.processing import ProcessingEngine


FIXTURE = Path(__file__).parent / "fixtures/github_issues_cc0.json"


class FakeResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _engine_with_session(tmp_path, session, **kwargs):
    config = tmp_path / "settings.yaml"
    config.write_text("github: {}\nparameters: {}\n")
    return IngestionEngine(
        output_dir=tmp_path / "raw",
        config_path=config,
        session=session,
        backoff=lambda _delay: None,
        **kwargs,
    )


def _write_fixture(raw_dir: Path, name: str = "ingest_fixture_20260101_000000.json") -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / name
    path.write_text(FIXTURE.read_text())
    return path


def test_provider_is_lazy_and_fake_is_deterministic(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAIProvider()
    assert provider.model == "gpt-4o-mini"
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        provider.classify_issue("title", "body")

    fake = FakeProvider()
    first = fake.classify_issue("Synthetic dashboard export bug", "it fails")
    assert first == fake.classify_issue("Synthetic dashboard export bug", "it fails")
    assert first == {"sentiment": "negative", "category": "bug", "urgency": "medium"}


def test_ingestion_writes_fixture_without_network(monkeypatch, tmp_path):
    config = tmp_path / "settings.yaml"
    config.write_text("github:\n  targets: ['repo:fixture/demo is:issue']\nparameters:\n  days_back: 1\n  max_results: 2\n")
    engine = IngestionEngine(output_dir=tmp_path / "raw", config_path=config)
    monkeypatch.setattr(engine, "fetch_github_issues", lambda **_: json.loads(FIXTURE.read_text()))

    engine.run()

    outputs = list((tmp_path / "raw").glob("ingest_*.json"))
    assert len(outputs) == 1
    assert len(json.loads(outputs[0].read_text())) == 2


def test_processing_and_enrichment_io(tmp_path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    enriched_dir = tmp_path / "enriched"
    _write_fixture(raw_dir)

    ProcessingEngine(raw_dir=raw_dir, processed_dir=processed_dir).run_batch()
    processed = list(processed_dir.glob("processed_*.csv"))
    assert len(processed) == 1
    frame = pd.read_csv(processed[0])
    assert list(frame.columns) == [
        "id", "number", "title", "state", "body", "author", "comments_count",
        "labels", "url", "created_at", "closed_at",
    ]

    EnrichmentEngine(
        processed_dir=processed_dir,
        enriched_dir=enriched_dir,
        provider=FakeProvider(),
    ).run_batch()
    enriched = list(enriched_dir.glob("enriched_*.csv"))
    assert len(enriched) == 1
    enriched_frame = pd.read_csv(enriched[0])
    assert {"sentiment", "category", "urgency"}.issubset(enriched_frame.columns)
    assert set(enriched_frame["sentiment"]) == {"negative", "neutral"}


def test_analysis_io_preserves_pain_index_and_labels(tmp_path):
    enriched_dir = tmp_path / "enriched"
    enriched_dir.mkdir()
    frame = pd.DataFrame(
        [
            {"sentiment": "negative", "urgency": "high", "labels": "bug", "id": 1},
            {"sentiment": "neutral", "urgency": "low", "labels": "documentation", "id": 2},
        ]
    )
    frame.to_csv(enriched_dir / "enriched_fixture.csv", index=False)

    plots_dir = tmp_path / "plots"
    run_analysis(enriched_dir=enriched_dir, analysis_dir=tmp_path / "analysis", plots_dir=plots_dir)

    assert (plots_dir / "heatmap_sentiment_labels.png").exists()
    assert (plots_dir / "barplot_pain_index_comparison.png").exists()


def test_cli_dispatches_each_named_stage(monkeypatch):
    calls: list[str] = []
    for command in ("ingest", "process", "enrich", "analyze", "run"):
        monkeypatch.setitem(cli.COMMANDS, command, lambda _args, name=command: calls.append(name))
        assert cli.main([command]) == 0
    assert calls == ["ingest", "process", "enrich", "analyze", "run"]


def test_pipeline_run_uses_fake_provider_and_no_network(monkeypatch, tmp_path):
    class FixtureIngestion:
        def __init__(self, output_dir, config_path):
            self.output_dir = Path(output_dir)

        def run(self):
            _write_fixture(self.output_dir)

    monkeypatch.setattr(cli, "IngestionEngine", FixtureIngestion)
    assert cli.main(
        [
            "run",
            "--raw-dir", str(tmp_path / "raw"),
            "--processed-dir", str(tmp_path / "processed"),
            "--enriched-dir", str(tmp_path / "enriched"),
            "--analysis-dir", str(tmp_path / "analysis"),
            "--plots-dir", str(tmp_path / "plots"),
            "--provider", "fake",
        ]
    ) == 0
    assert list((tmp_path / "enriched").glob("enriched_*.csv"))
    assert (tmp_path / "plots/barplot_pain_index_comparison.png").exists()


def test_ingestion_paginates_to_limit_and_passes_explicit_timeout(tmp_path):
    session = FakeSession(
        [
            FakeResponse(200, {"total_count": 3, "items": [{"id": 1}, {"id": 2}]}),
            FakeResponse(200, {"total_count": 3, "items": [{"id": 3}]}),
        ]
    )
    engine = _engine_with_session(tmp_path, session, timeout=4.25, cache_ttl=0)

    result = engine.fetch_github_issues("repo:fixture/demo", per_page=2, max_results=3)

    assert [item["id"] for item in result["items"]] == [1, 2, 3]
    assert [call[1]["params"]["page"] for call in session.calls] == [1, 2]
    assert all(call[1]["timeout"] == 4.25 for call in session.calls)


def test_ingestion_retries_5xx_and_rate_limit_without_sleep(tmp_path):
    delays = []
    session = FakeSession(
        [
            FakeResponse(503),
            FakeResponse(429, headers={"Retry-After": "0.25"}),
            FakeResponse(200, {"total_count": 1, "items": [{"id": 9}]}),
        ]
    )
    engine = _engine_with_session(tmp_path, session, cache_ttl=0)
    engine.backoff = delays.append

    assert engine.fetch_github_issues("retry", max_results=1)["items"] == [{"id": 9}]
    assert len(session.calls) == 3
    assert delays == [1.0, 0.25]


def test_ingestion_rate_reset_header_is_used_and_final_error_is_safe(tmp_path):
    now = 100.0
    session = FakeSession(
        [FakeResponse(403, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "103"})]
        * 4
    )
    engine = _engine_with_session(tmp_path, session, cache_ttl=0, clock=lambda: now)
    delays = []
    engine.backoff = delays.append

    with pytest.raises(IngestionError, match="after 4 attempts.*HTTP 403") as error:
        engine.fetch_github_issues("safe-query", max_results=1)
    assert delays == [3.0, 3.0, 3.0]
    assert "X-RateLimit" not in str(error.value)
    assert "token" not in str(error.value).lower()

    session.responses = [FakeResponse(401, {"message": "token=do-not-leak"})]
    with pytest.raises(IngestionError, match="HTTP 401") as rejected:
        engine.fetch_github_issues("unauthorized", max_results=1)
    assert "do-not-leak" not in str(rejected.value)


def test_ingestion_cache_honors_ttl_without_second_request(tmp_path):
    now = [10.0]
    session = FakeSession([FakeResponse(200, {"total_count": 1, "items": [{"id": 4}]}),
                           FakeResponse(200, {"total_count": 1, "items": [{"id": 5}]})])
    engine = _engine_with_session(
        tmp_path,
        session,
        cache_dir=tmp_path / "cache",
        cache_ttl=5,
        clock=lambda: now[0],
    )

    assert engine.fetch_github_issues("cached", max_results=1)["items"] == [{"id": 4}]
    assert engine.fetch_github_issues("cached", max_results=1)["items"] == [{"id": 4}]
    assert len(session.calls) == 1
    now[0] = 16.0
    assert engine.fetch_github_issues("cached", max_results=1)["items"] == [{"id": 5}]
    assert len(session.calls) == 2


def test_labels_are_exact_normalized_tokens_not_substrings():
    frame = pd.DataFrame(
        [
            {"labels": "debug, bugfix", "sentiment": "negative", "urgency": "low"},
            {"labels": "bug, BUG", "sentiment": "neutral", "urgency": "low"},
        ]
    )
    top_labels, _ = analyze_labels(frame)
    assert top_labels[0] == "bug"
    assert "debug" in top_labels and "bugfix" in top_labels


def test_pain_index_is_bounded_and_higher_means_worse():
    assert calculate_pain_index("positive", "low") == 0.0
    assert calculate_pain_index("neutral", "medium") == 1.0
    assert calculate_pain_index("negative", "high") == 3.0
    assert 0.0 <= calculate_pain_index("unknown", "unknown") <= 3.0

    frame = pd.DataFrame(
        [
            {"sentiment": "positive", "urgency": "high"},
            {"sentiment": "neutral", "urgency": "medium"},
            {"sentiment": "negative", "urgency": "low"},
        ]
    )
    scored = feature_engineering(frame)
    assert list(scored["pain_index"]) == [0.0, 1.0, 1.0]
