"""Presentation aggregates of existing calls; no detection, TVR calling or filters."""
from dataclasses import asdict
from statistics import median

from .models import Availability as A, Fact, unavailable


def aggregate(value, evidence, unit, population):
    return Fact(A.AVAILABLE, value, unit=unit, population=population,
                origin="presentation_aggregate", evidence=evidence)


def sum_complete(barcodes, key, population):
    facts = [b.metrics.get(key) for b in barcodes]
    if not facts or any(f is None or f.status != A.AVAILABLE for f in facts):
        return unavailable("Not recorded for every barcode")
    return aggregate(sum(f.value for f in facts), [e for f in facts for e in f.evidence], "reads", population)


def motif_comparison(run):
    """Count exported hits in an explicit population; no new motif calling."""
    result = []
    for barcode in run.barcodes:
        lengths = barcode.metrics.get("filtered_length_records")
        entry = {"id": barcode.id, "label": barcode.label, "available": False,
                 "reason": "Complete post-filtered motif exports are required", "telomere": {}, "whole_read": {}}
        result.append(entry)
        if not lengths or lengths.status != A.AVAILABLE:
            continue
        ids = {item["read_id"] for item in lengths.value}
        reads = [read for read in barcode.reads if read.id in ids]
        if not reads or len(reads) != len(lengths.value):
            continue
        if any(read.tracks["motifs"].status != A.AVAILABLE or
               "tvr_inclusive" not in read.tracks["motifs"].value["methods"] or
               read.calls["exact"]["interval"].status != A.AVAILABLE for read in reads):
            continue
        entry["available"] = True
        entry["evidence"] = [asdict(e) for read in reads for e in read.tracks["motifs"].evidence]
        for read in reads:
            interval = read.calls["exact"]["interval"].value
            for hit in read.tracks["motifs"].value["matches"]:
                if hit["method"] != "tvr_inclusive":
                    continue
                label = hit["motif"] + (" (canonical)" if hit["role"] == "canonical" else "")
                entry["whole_read"][label] = entry["whole_read"].get(label, 0) + 1
                if hit["start"] >= interval["start"] and hit["end"] <= interval["end"]:
                    entry["telomere"][label] = entry["telomere"].get(label, 0) + 1
    return result


def dashboard_data(run):
    """Build chart payloads with explicit populations and complete-data checks."""
    total = sum_complete(run.barcodes, "total_reads", "input_reads")
    filtered = sum_complete(run.barcodes, "amount_of_telomeres", "post_filtered_telomeres")
    detected = sum_complete(run.barcodes, "detected_telomeric_reads", "detected_telomeric_reads")
    pct = unavailable("Requires input counts and post-filtered counts for every barcode")
    if total.status == filtered.status == A.AVAILABLE:
        if total.value > 0 and filtered.value <= total.value:
            pct = aggregate(100 * filtered.value / total.value, total.evidence + filtered.evidence,
                            "%", "post_filtered_telomeres / input_reads")
        elif total.value == 0:
            pct = unavailable("No input reads; percentage is undefined", A.NOT_APPLICABLE)
        else:
            pct = unavailable("Filtered counts exceed the reported input count", A.INVALID)
    distributions = [{"id": b.id, "label": b.label, "lengths": asdict(b.metrics["filtered_length_records"])} for b in run.barcodes]
    complete = bool(distributions) and all(d["lengths"]["status"] == A.AVAILABLE for d in distributions)
    all_lengths = [r["length_bp"] for d in distributions if d["lengths"]["status"] == A.AVAILABLE for r in d["lengths"]["value"]]
    evidence = [e for b in run.barcodes for e in b.metrics["filtered_length_records"].evidence]
    med = aggregate(median(all_lengths), evidence, "bp", "post_filtered_telomeres") if complete and all_lengths else unavailable("Complete filtered per-read lengths are required; barcode medians are not averaged")
    cells = []; references = set(); mapped_evidence = []
    for b in run.barcodes:
        lengths = b.metrics["filtered_length_records"]
        if lengths.status != A.AVAILABLE:
            continue
        by_id = {r.id: r for r in b.reads}; groups = {}
        for item in lengths.value:
            read = by_id.get(item["read_id"])
            if not read or read.alignments.status != A.AVAILABLE:
                continue
            refs = {a["reference"].value for a in read.alignments.value
                    if a["reference"].status == A.AVAILABLE and a["reference"].value != "*"}
            for reference in refs:
                groups.setdefault(reference, []).append(item["length_bp"])
                references.add(reference)
            mapped_evidence.extend(read.alignments.evidence)
        for reference, values in groups.items():
            cells.append({"barcode_id": b.id, "barcode": b.label, "reference": reference,
                          "median_bp": median(values), "read_count": len(values)})
    reference_count = aggregate(len(references), mapped_evidence, "references", "mapped post-filtered reads") if references else unavailable("No mapped post-filtered reference records available")
    return {"metrics": {"barcode_count": asdict(run.metrics["barcode_count"]), "total_reads": asdict(total),
             "telomeric_reads": asdict(filtered), "telomeric_percentage": asdict(pct),
             "median_telomere_length": asdict(med), "mapped_references": asdict(reference_count),
             "detected_telomeric_reads": asdict(detected)},
            "distributions": distributions, "reference_cells": cells,
            "motif_comparison": motif_comparison(run),
            "tvr": asdict(unavailable("Exact motif composition was not exported. TVR-inclusive density is not TVR percentage."))}
