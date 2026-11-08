"""Presentation aggregates of existing calls; no detection, TVR calling or filters."""
from dataclasses import asdict
from statistics import median

from .models import Availability as A, Fact, unavailable


def aggregate(value, evidence, unit, population):
    # Wrap a presentation-derived value with its units, population and supporting
    # evidence. The origin distinguishes this value from a statistic exported by NanoTel.
    """Available Fact tagged as a presentation aggregate with source evidence.

    Args:
        value: Value to inspect, convert or format.
        evidence: Source references supporting the returned measurement.
        unit: Measurement or display unit.
        population: Label identifying the measurement population.

    Returns:
        Available Fact tagged as a presentation aggregate with source evidence.
    """
    return Fact(A.AVAILABLE, value, unit=unit, population=population,
                origin="presentation_aggregate", evidence=evidence)


def sum_complete(barcodes, key, population):
    # Require every imported barcode to supply this metric. A partial sum would look
    # like a complete run total, so missing contributors make the whole result unavailable.
    """Summed Fact when all inputs are available; otherwise an unavailable Fact.

    Args:
        barcodes: Barcode labels or records to process.
        key: Lookup key or field name.
        population: Label identifying the measurement population.

    Returns:
        Summed Fact when all inputs are available; otherwise an unavailable Fact.
    """
    facts = [b.metrics.get(key) for b in barcodes]
    if not facts or any(f is None or f.status != A.AVAILABLE for f in facts):
        return unavailable("Not recorded for every barcode")
    return aggregate(sum(f.value for f in facts), [e for f in facts for e in f.evidence], "reads", population)


def motif_comparison(run):
    """Count exported hits in an explicit population; no new motif calling.

    Args:
        run: Imported run model containing barcodes, reads and source evidence.

    Returns:
        Per-barcode motif comparison records derived from exported matches.
    """
    # Build two explicitly different match-count populations: whole reads and matches
    # overlapping TVR-inclusive telomere intervals, both limited to post-filtered reads.
    # Counts are search hits, not covered bases, unique regions or percentages of reads.
    result = []
    for barcode in run.barcodes:
        lengths = barcode.metrics.get("filtered_length_records")
        entry = {"id": barcode.id, "label": barcode.label, "available": False,
                 "reason": "Complete post-filtered motif exports are required", "telomere": {}, "whole_read": {}}
        # Keep an unavailable entry too, allowing the chart to explain omitted
        # barcodes instead of silently removing them from the comparison.
        result.append(entry)
        if not lengths or lengths.status != A.AVAILABLE:
            continue
        # Safe report IDs link filtered rows to reads without depending on display
        # names, which may contain metadata or be duplicated in source exports.
        ids = {item["read_id"] for item in lengths.value}
        reads = [read for read in barcode.reads if read.id in ids]
        if not reads or len(reads) != len(lengths.value):
            continue
        if any(not read.tracks.get("motifs") or read.tracks["motifs"].status != A.AVAILABLE or
               "tvr_inclusive" not in read.tracks["motifs"].value["methods"] or
               read.calls["tvr_inclusive"]["interval"].status != A.AVAILABLE for read in reads):
            continue
        # All required reads passed the completeness checks. Only now may zero
        # matches be interpreted as an observed empty result rather than missing data.
        entry["available"] = True
        entry["evidence"] = [asdict(e) for read in reads for e in read.tracks["motifs"].evidence]
        for read in reads:
            interval = read.calls["tvr_inclusive"]["interval"].value
            for hit in read.tracks["motifs"].value["matches"]:
                # Use one search method, avoiding triple-counting the same motif
                # across exact, mismatch and TVR-inclusive exports.
                if hit["method"] != "tvr_inclusive":
                    continue
                label = hit["motif"] + (" (canonical)" if hit["role"] == "canonical" else "")
                entry["whole_read"][label] = entry["whole_read"].get(label, 0) + 1
                # Half-open intervals overlap only when they share at least one base.
                # Include crossing hits consistently with source coverage exports.
                if hit["end"] > interval["start"] and hit["start"] < interval["end"]:
                    entry["telomere"][label] = entry["telomere"].get(label, 0) + 1
    return result


def dashboard_data(run, include_details=True):
    """Build presentation payloads with explicit population/completeness rules.

    Detailed reference/motif tables are optional when the caller uses another
    shared adapter for those plots. The default export remains unchanged.

    Args:
        run: Imported run model containing barcodes, reads and source evidence.
        include_details: Whether to include individual-read detail payloads. Default: True.

    Returns:
        Serializable presentation data for the requested level of read detail.
    """
    # Create serializable chart payloads from imported facts. Aggregate only supported
    # populations and keep missing/invalid states available to the presentation layer.
    # Whole-run totals require complete barcode coverage; summing only known
    # barcodes would understate the run and give a misleading percentage.
    total = sum_complete(run.barcodes, "total_reads", "input_reads")
    populations = {b.metrics["amount_of_telomeres"].population for b in run.barcodes
                   if b.metrics["amount_of_telomeres"].status == A.AVAILABLE}
    population = (next(iter(populations)) if len(populations) == 1 else None) or "post_filtered_telomeres"
    filtered = sum_complete(run.barcodes, "amount_of_telomeres", population)
    if len(populations) > 1:
        filtered = unavailable("Barcode counts describe different filtering populations")
    detected = sum_complete(run.barcodes, "detected_telomeric_reads", "detected_telomeric_reads")
    pct = unavailable("Requires input counts and post-filtered counts for every barcode")
    # Both operands must be available. Zero input has no defined percentage;
    # a numerator above the input count signals inconsistent source statistics.
    if total.status == filtered.status == A.AVAILABLE:
        if total.value > 0 and filtered.value <= total.value:
            pct = aggregate(100 * filtered.value / total.value, total.evidence + filtered.evidence,
                            "%", population + " / input_reads")
        elif total.value == 0:
            pct = unavailable("No input reads; percentage is undefined", A.NOT_APPLICABLE)
        else:
            pct = unavailable("Filtered counts exceed the reported input count", A.INVALID)
    distributions = [{"id": b.id, "label": b.label, "lengths": asdict(b.metrics["filtered_length_records"])} for b in run.barcodes]
    # Pool individual before-filtration measurements; never average barcode medians.
    from ..shared.measurement_statistics import method_statistics, selected_method
    before = [method_statistics(b, run.settings, selected_method(run.settings), 'before') for b in run.barcodes]
    before_values = [n for row in before for n in row['lengths'] or []]
    med = (aggregate(median(before_values), [e for b in run.barcodes for e in b.evidence], 'bp', 'before_filtration')
           if before and all(row['lengths'] is not None for row in before) and before_values
           else unavailable('Before-filtration source measurements are required'))
    result = {
        "metrics": {
            "barcode_count": asdict(run.metrics.get("barcode_count", unavailable("Barcode count was not exported"))),
            "total_reads": asdict(total), "telomeric_reads": asdict(filtered),
            "telomeric_percentage": asdict(pct), "median_telomere_length": asdict(med),
            "detected_telomeric_reads": asdict(detected),
        },
        "distributions": distributions,
    }
    # The HTML renderer uses the shared chromosome/composition adapter instead.
    # Keep these optional exports for callers that actually request them.
    if not include_details:
        return result
    # Build reference-by-barcode cells from mapped post-filtered read lengths.
    # These labels are references, not inferred chromosomes or chromosome arms.
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
            # A read may have several alignments to one reference. Count that
            # reference once per read, while retaining distinct reference labels.
            refs = {a["reference"].value for a in read.alignments.value
                    if a["reference"].status == A.AVAILABLE and a["reference"].value != "*"}
            for reference in refs:
                groups.setdefault(reference, []).append(item["length_bp"])
                references.add(reference)
            mapped_evidence.extend(read.alignments.evidence)
        # A read aligning to distinct references can contribute to multiple cells.
        # Consequently, cell counts are not additive unique-read totals.
        for reference, values in groups.items():
            cells.append({"barcode_id": b.id, "barcode": b.label, "reference": reference,
                          "median_bp": median(values), "read_count": len(values)})
    reference_count = aggregate(len(references), mapped_evidence, "references", "mapped post-filtered reads") if references else unavailable("No mapped post-filtered reference records available")
    # Convert Facts to plain dictionaries at the presentation boundary. Keep the
    # legacy unavailable TVR-coverage fact separate from motif match-count payloads.
    result["metrics"]["mapped_references"] = asdict(reference_count)
    result.update(reference_cells=cells, motif_comparison=motif_comparison(run),
                  tvr=asdict(unavailable("Exact motif composition was not exported. TVR-inclusive density is not TVR percentage.")))
    return result
