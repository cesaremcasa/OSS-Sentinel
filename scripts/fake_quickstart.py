#!/usr/bin/env python3
"""Run the complete pipeline against the repository-authored CC0 fixture."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from src.cli import main as cli_main


def main() -> int:
    fixture = Path(__file__).resolve().parents[1] / "tests/fixtures/github_issues_cc0.json"
    with tempfile.TemporaryDirectory(prefix="oss-sentinel-fake-") as temporary:
        root = Path(temporary)
        raw_dir = root / "raw"
        raw_dir.mkdir()
        shutil.copyfile(fixture, raw_dir / "ingest_fixture_20260101_000000.json")
        cli_main(
            [
                "run",
                "--offline",
                "--provider",
                "fake",
                "--raw-dir",
                str(raw_dir),
                "--processed-dir",
                str(root / "processed"),
                "--enriched-dir",
                str(root / "enriched"),
                "--analysis-dir",
                str(root / "analysis"),
                "--plots-dir",
                str(root / "plots"),
            ]
        )
        enriched = list((root / "enriched").glob("enriched_*.csv"))
        plot = root / "plots/barplot_pain_index_comparison.png"
        if len(enriched) != 1 or not plot.is_file():
            raise SystemExit("fake quickstart did not produce expected outputs")
    print("fake quickstart PASS: offline fixture completed ingest-to-analysis")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
