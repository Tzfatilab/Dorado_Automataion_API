"""Standalone milestone-1 builder; not connected to GUI/workflow execution yet."""
import argparse
from pathlib import Path

from .builder import build_report
from .importers import import_results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build an offline NanoTel report from existing results.")
    parser.add_argument("results", type=Path, help="One run's results directory")
    parser.add_argument("--output", type=Path, help="New or empty report directory; defaults to RESULTS/report")
    parser.add_argument("--metadata", type=Path, help="Optional explicit run metadata JSON; see SCHEMA.md")
    args = parser.parse_args(argv)
    try:
        run = import_results(args.results, args.metadata)
        output = build_report(run, args.output or args.results / "report")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Could not build report: {exc}\n")
    print(output.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
