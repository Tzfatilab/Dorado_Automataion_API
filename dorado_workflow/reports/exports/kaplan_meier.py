"""Combine assessed NanoTel KM rows once per run; never refit or pool medians."""
import argparse
import csv
import math
from pathlib import Path


KM_FIELDS = (
    "barcode", "km_status", "km_median_bp", "km_ci_lower_bp", "km_ci_upper_bp",
    "km_whole_relative_ci_width_pct", "km_input_read_count",
    "km_complete_read_count", "km_censored_read_count", "km_censoring_rate_pct",
    "km_reporting_reason",
)
RUN_FIELDS = (
    "barcodes_with_reportable_km", "barcodes_with_withheld_km",
    "barcodes_with_available_km_censoring", "mean_barcode_km_censoring_rate_pct",
)
KM_STATUSES = {"reportable", "too_wide", "non_estimable", "invalid", "failed"}


def write_km_run_statistics(source_paths, output_dir):
    """Read explicit current-run paths, write barcode observations and one mean.

    Missing/failed barcode executions are excluded by the caller. A KM fitting
    failure is still a row: its pre-edge censoring may remain available.
    """
    rows = []
    seen = set()
    for path in source_paths:
        with Path(path).open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != list(KM_FIELDS):
                raise ValueError(f"Unexpected KM CSV columns: {path}")
            records = list(reader)
        if len(records) != 1:
            raise ValueError(f"Expected one barcode KM row: {path}")
        row = records[0]
        if not row["barcode"] or row["barcode"] in seen:
            raise ValueError(f"Missing or duplicate KM barcode: {path}")
        seen.add(row["barcode"])
        if row["km_status"] not in KM_STATUSES:
            raise ValueError(f"Unknown KM status: {path}")
        # Defense against a legacy/malformed export bypassing the reporting rule.
        if row["km_status"] != "reportable":
            for field in ("km_median_bp", "km_ci_lower_bp", "km_ci_upper_bp"):
                row[field] = ""
        rows.append(row)

    rates = []
    for row in rows:
        value = row["km_censoring_rate_pct"]
        if value:
            rate = float(value)
            if not math.isfinite(rate) or not 0 <= rate <= 100:
                raise ValueError(f"Invalid KM censoring rate for {row['barcode']}")
            rates.append(rate)
    reportable = sum(row["km_status"] == "reportable" for row in rows)
    summary = dict(zip(RUN_FIELDS, (
        reportable, len(rows) - reportable, len(rates),
        math.fsum(rates) / len(rates) if rates else "",
    )))
    # Equal weight per barcode; not the pooled fraction of censored reads.
    # Histograms use these saved observations; binning belongs to the plot layer.
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, fields, records in (
        ("km_barcode_statistics.csv", KM_FIELDS, sorted(rows, key=lambda r: r["barcode"])),
        ("km_run_statistics.csv", RUN_FIELDS, [summary]),
    ):
        target = output_dir / name
        temporary = target.with_suffix(".tmp.csv")
        with temporary.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(records)
        temporary.replace(target)
    return summary


if __name__ == "__main__":
    # Standalone R runs have no run coordinator: supply their barcode CSVs explicitly.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("sources", nargs="+", type=Path)
    args = parser.parse_args()
    write_km_run_statistics(args.sources, args.output_dir)
