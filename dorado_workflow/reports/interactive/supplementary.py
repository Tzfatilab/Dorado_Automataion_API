"""Import source-assessed statistics without refitting KM or reapplying filters."""
import json
import re

from .models import Availability as A, Evidence, Fact, unavailable


def import_statistics(importer, barcode, number):
    """Keep NanoTel final-filter and pre-edge KM metrics in separate namespaces."""
    # Preserve explicit unavailable states even when neither export exists.
    # Summary-only intentionally skips NanoTel's --analysis artifact generation.
    skipped = importer.metadata.get("stages", {}).get("summary_only") is True
    reason = "Summary-only run: analysis statistics not requested" if skipped else "NanoTel analysis statistics file not exported"
    state = A.NOT_REQUESTED if skipped else A.NOT_EXPORTED
    for key in ("nanotel_final_censoring_rate_pct", "nanotel_final_telomeres_shorter_than_threshold_pct",
                "km_status", "km_median_bp", "km_censoring_rate_pct"):
        barcode.metrics[key] = unavailable(reason, state)
    paths = importer.files(f"{barcode.label}_analysis.json")
    if len(paths) == 1:
        path = paths[0]
        ev = Evidence(importer.source(path, "json").id)
        try:
            row = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(row, dict) or row.get("barcode") != barcode.label:
                raise ValueError("barcode identity mismatch")
            fields = {
                "number_of_telomeric_reads_post_filtration": "reads",
                "complete_telomeric_reads": "reads", "incomplete_telomeric_reads": "reads",
                "censoring_rate_pct": "%", "median_telomeric_length_post_filtration_bp": "bp",
                "short_telomere_threshold_bp": "bp", "telomeres_shorter_than_threshold_pct": "%",
            }
            for key, unit in fields.items():
                barcode.metrics["nanotel_final_" + key] = number(
                    row, key, ev, unit=unit, population="NanoTel final-filtered reads",
                    maximum=100 if unit == "%" else None)
        except (ValueError, TypeError) as exc:
            barcode.warnings.append(f"Invalid NanoTel analysis JSON: {exc}")
    elif len(paths) > 1:
        barcode.warnings.append("Ambiguous NanoTel analysis JSON files; statistics not imported")

    paths = importer.files(f"{barcode.label}_km_statistics.csv")
    if len(paths) != 1:
        if paths:
            barcode.warnings.append("Ambiguous KM statistics files; statistics not imported")
        return
    _, rows, _ = importer.csv_table(paths[0])
    if len(rows) != 1 or rows[0][0].get("barcode") != barcode.label:
        barcode.warnings.append("Invalid KM statistics barcode/row count")
        return
    row, ev = rows[0]
    status = row.get("km_status")
    if status not in {"reportable", "too_wide", "non_estimable", "invalid", "failed"}:
        barcode.warnings.append("Unknown source KM reporting status")
        return
    # Preserve the source decision: withheld estimates must never become numbers
    # just because a malformed/legacy CSV happens to contain them.
    barcode.metrics["km_status"] = Fact(A.AVAILABLE, status, evidence=[ev], population="NanoTel pre-edge KM input")
    reason = row.get("km_reporting_reason") or status
    barcode.metrics["km_reporting_reason"] = Fact(A.AVAILABLE, reason, evidence=[ev])
    for key, value in row.items():
        if key in {"barcode", "km_status", "km_reporting_reason"}:
            continue
        unit = "bp" if key.endswith("_bp") else "reads" if key.endswith("_count") else "%"
        if key in {"km_median_bp", "km_ci_lower_bp", "km_ci_upper_bp"} and status != "reportable":
            barcode.metrics[key] = unavailable("Source withheld KM estimate: " + reason, A.NOT_APPLICABLE)
        else:
            barcode.metrics[key] = number(row, key, ev, unit=unit, population="NanoTel pre-edge KM input",
                maximum=100 if key == "km_censoring_rate_pct" else None)


def chromosome_fact(reference, evidence):
    """Recognize only explicit chrN/chrX/chrY/chrM labels, optionally Head/Tail.

    This is a reference-name convention, not an inferred p/q-arm annotation.
    Unrecognized contigs remain unavailable rather than increasing the count.
    """
    match = re.fullmatch(r"(chr(?:[0-9]+|X|Y|M|MT))(?:_(?:Head|Tail))?", str(reference or ""))
    if not match:
        return unavailable("Reference name does not establish a chromosome")
    return Fact(A.AVAILABLE, match.group(1), evidence=[evidence],
                origin="presentation_aggregate", population="explicit chromosome reference labels")


def detected_chromosomes(run):
    """Count distinct unambiguous chromosomes among source post-filtered reads."""
    names, evidence = set(), []
    for barcode in run.barcodes:
        lengths = barcode.metrics.get("filtered_length_records")
        if not lengths or lengths.status != A.AVAILABLE:
            continue
        ids = {row["read_id"] for row in lengths.value}
        for read in barcode.reads:
            if read.id not in ids or read.alignments.status != A.AVAILABLE:
                continue
            chromosomes = {a["chromosome"].value for a in read.alignments.value
                           if a["chromosome"].status == A.AVAILABLE}
            if len(chromosomes) == 1:
                names.update(chromosomes)
                evidence.extend(read.alignments.evidence)
    return (Fact(A.AVAILABLE, len(names), evidence=evidence, origin="presentation_aggregate",
                 population="imported unambiguous mapped post-filtered reads") if names
            else unavailable("No unambiguous chromosome annotations in imported post-filtered reads"))
