"""Command-line dispatch for the OSS Sentinel stages."""

from __future__ import annotations

import argparse
from typing import Sequence

from src.analyze import run_analysis
from src.enrichment import EnrichmentEngine
from src.ingestion import IngestionEngine
from src.processing import ProcessingEngine


def _add_io_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--raw-dir", default="data/raw", help="raw JSON directory")
    parser.add_argument("--processed-dir", default="data/processed", help="processed data directory")
    parser.add_argument("--enriched-dir", default="data/enriched", help="enriched CSV directory")
    parser.add_argument("--analysis-dir", default="data/analysis", help="analysis output directory")
    parser.add_argument("--plots-dir", default="assets/plots", help="plot output directory")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oss-sentinel")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="fetch GitHub issue JSON")
    ingest.add_argument("--raw-dir", default="data/raw")
    ingest.add_argument("--config", default="config/settings.yaml")

    process = subparsers.add_parser("process", help="normalize raw issue JSON")
    process.add_argument("--raw-dir", default="data/raw")
    process.add_argument("--processed-dir", default="data/processed")

    enrich = subparsers.add_parser("enrich", help="classify processed issues")
    enrich.add_argument("--processed-dir", default="data/processed")
    enrich.add_argument("--enriched-dir", default="data/enriched")
    enrich.add_argument("--provider", choices=("fake", "openai"), default=None)

    analyze = subparsers.add_parser("analyze", help="calculate Pain Index and plots")
    analyze.add_argument("--enriched-dir", default="data/enriched")
    analyze.add_argument("--analysis-dir", default="data/analysis")
    analyze.add_argument("--plots-dir", default="assets/plots")

    run = subparsers.add_parser("run", help="run the complete pipeline")
    _add_io_arguments(run)
    run.add_argument("--config", default="config/settings.yaml")
    run.add_argument("--provider", choices=("fake", "openai"), default=None)
    run.add_argument(
        "--offline",
        action="store_true",
        help="skip network ingestion and process existing raw fixture/data",
    )
    return parser


def _ingest(args: argparse.Namespace) -> None:
    IngestionEngine(output_dir=args.raw_dir, config_path=args.config).run()


def _process(args: argparse.Namespace) -> None:
    ProcessingEngine(raw_dir=args.raw_dir, processed_dir=args.processed_dir).run_batch()


def _enrich(args: argparse.Namespace) -> None:
    EnrichmentEngine(
        processed_dir=args.processed_dir,
        enriched_dir=args.enriched_dir,
        provider_name=args.provider,
    ).run_batch()


def _analyze(args: argparse.Namespace) -> None:
    run_analysis(
        enriched_dir=args.enriched_dir,
        analysis_dir=args.analysis_dir,
        plots_dir=args.plots_dir,
    )


def _run(args: argparse.Namespace) -> None:
    if not args.offline:
        _ingest(args)
    _process(args)
    _enrich(args)
    _analyze(args)


COMMANDS = {
    "ingest": _ingest,
    "process": _process,
    "enrich": _enrich,
    "analyze": _analyze,
    "run": _run,
}


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    COMMANDS[args.command](args)
    return 0
