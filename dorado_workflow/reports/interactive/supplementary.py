"""Import source-assessed statistics without refitting KM or reapplying filters."""
import json
import re

from .models import Availability as A, Evidence, Fact, unavailable


def import_statistics(importer, barcode, number):
    """Keep NanoTel final-filter and pre-edge KM metrics in separate namespaces."""
    # Preserve explicit unavailable states even when neither export exists.
    reason = "NanoTel analysis statistics file not exported"
    state = A.NOT_EXPORTED
    for key in ("nanotel_final_censoring_rate_pct", "nanotel_final_telomeres_shorter_than_threshold_pct",
                "km_status", "km_median_bp", "km_censoring_rate_pct"):
        barcode.metrics[key] = unavailable(reason, state)
    paths = importer.files(f"{barcode.label}_analysis.json")
    analysis = None
    if len(paths) == 1:
        path = paths[0]
        ev = Evidence(importer.source(path, "json").id)
        try:
            row = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(row, dict) or row.get("barcode") != barcode.label:
                raise ValueError("barcode identity mismatch")
            analysis = row, ev, {}
        except (ValueError, TypeError) as exc:
            barcode.warnings.append(f"Invalid NanoTel analysis JSON: {exc}")
    elif len(paths) > 1:
        barcode.warnings.append("Ambiguous NanoTel analysis JSON files; statistics not imported")
    else:
        # Summary mode archives these source values in Excel before cleanup.
        # Recover exact fields with worksheet evidence; do not refit or infer KM.
        table = getattr(importer, 'saved_statistics', {}).get('NanoTel analysis facts')
        if table:
            entries = [(r, e) for r, e in table[1] if r.get('Barcode') == barcode.label]
            fields = [r.get('Source field') for r, _ in entries]
            if entries and all(isinstance(f, str) and f for f in fields) and len(set(fields)) == len(fields):
                row = {r['Source field']: r.get('Value') for r, _ in entries}
                if row.get('barcode') == barcode.label:
                    analysis = row, entries[0][1], {r['Source field']: e for r, e in entries}
                else:
                    barcode.warnings.append('Workbook analysis barcode identity mismatch')
            elif entries:
                barcode.warnings.append('Duplicate or invalid workbook analysis fields; statistics not imported')
    if analysis:
        row, ev, field_evidence = analysis
        fields = {
            "number_of_telomeric_reads_post_filtration": "reads",
            "complete_telomeric_reads": "reads", "incomplete_telomeric_reads": "reads",
            "censoring_rate_pct": "%", "median_telomeric_length_post_filtration_bp": "bp",
            "short_telomere_threshold_bp": "bp", "telomeres_shorter_than_threshold_pct": "%",
        }
        for key, unit in fields.items():
            raw = row.get(key)
            source_row = {key: None if raw == 'Unavailable' else raw}
            barcode.metrics["nanotel_final_" + key] = number(
                source_row, key, field_evidence.get(key, ev), unit=unit, population="NanoTel final-filtered reads",
                maximum=100 if unit == "%" else None)

    paths = importer.files(f"{barcode.label}_km_statistics.csv")
    if len(paths) == 1:
        _, rows, _ = importer.csv_table(paths[0])
        if len(rows) != 1 or rows[0][0].get("barcode") != barcode.label:
            barcode.warnings.append("Invalid KM statistics barcode/row count")
            return
    elif paths:
        barcode.warnings.append("Ambiguous KM statistics files; statistics not imported")
        return
    else:
        table = getattr(importer, 'saved_statistics', {}).get('KM by barcode')
        rows = [(r, e) for r, e in table[1] if r.get('barcode') == barcode.label] if table else []
        if len(rows) != 1:
            if rows:
                barcode.warnings.append('Ambiguous workbook KM barcode rows; statistics not imported')
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


def restore_summary_sources(importer,barcode):
    figures={};figure_evidence=[]
    for kind in ('histogram','plot'):
        paths=[p for p in importer.files('*_telomere_'+kind+'.plotly.json') if p.name==barcode.label+'_telomere_'+kind+'.plotly.json']
        if len(paths)==1:
            obj=json.loads(paths[0].read_text(encoding='utf-8-sig'))
            if isinstance(obj.get('data'),list) and isinstance(obj.get('layout'),dict):
                figures[kind]=obj
                figure_evidence.append(Evidence(importer.source(paths[0],'json').id))
    table=importer.saved_statistics.get('Barcode figures')
    if table:
        for kind in ('histogram','plot'):
            parts=sorted((int(r['Part']),r['Value']) for r,e in table[1] if r['barcode']==barcode.label and r['Kind']==kind)
            if kind not in figures and parts and [i for i,_ in parts]==list(range(1,len(parts)+1)):
                obj=json.loads(''.join(v for _,v in parts))
                if isinstance(obj.get('data'),list) and isinstance(obj.get('layout'),dict):
                    figures[kind]=obj
                    figure_evidence.extend(e for r,e in table[1] if r['barcode']==barcode.label and r['Kind']==kind)
    if figures:barcode.metrics['saved_barcode_figures']=Fact(A.AVAILABLE,figures,evidence=figure_evidence)
    table=importer.saved_statistics.get('Read motifs')
    if not table:return
    groups={}
    for row,evidence in table[1]:
        if row['barcode']==barcode.label:
            groups.setdefault(row['read_id'],[]).append((int(row['Part']),row['Value'],evidence))
    for read in barcode.reads:
        if read.tracks['motifs'].status=='available':continue
        parts=sorted(groups.get(read.id,[]))
        if parts and [i for i,_,_ in parts]==list(range(1,len(parts)+1)):
            obj=json.loads(''.join(v for _,v,_ in parts))
            if isinstance(obj.get('methods'),list) and isinstance(obj.get('matches'),list):
                read.tracks['motifs']=Fact(A.AVAILABLE,obj,evidence=[parts[0][2]])
