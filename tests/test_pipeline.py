from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src import cli
from src.analyze import run_analysis
from src.enrichment import EnrichmentEngine
from src.ingestion import IngestionEngine
from src.providers import FakeProvider, OpenAIProvider
from src.processing import ProcessingEngine


FIXTURE = Path(__file__).parent / "fixtures/github_issues_cc0.json"


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
