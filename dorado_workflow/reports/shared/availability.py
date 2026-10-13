"""Presentation audit of imported coverage, warnings and source provenance."""
from html import escape
from dorado_workflow.reports.interactive.models import unavailable


def availability_html(run):
    """Show coverage without treating absent exports as negative observations.

    Rows count imported records, not all input reads. Existing importer warnings
    explain invalid exports and skipped joins. No scientific filters run here.
    """
    rows, stats, coverage_warnings = [], [], []
    summary = run.stages.get("summary_only")
    detail_note = ("Summary-only run: motif and density exports were not requested."
                   if summary and summary.value is True else
                   "Missing motif/density files require a new full NanoTel run; summary values cannot reconstruct them.")
    for barcode in run.barcodes:
        count = len(barcode.reads)
        values = []
        for kind in ("density", "motifs", "mapping"):
            facts = [r.alignments if kind == "mapping" else
                     r.tracks.get(kind, unavailable("Track not supplied")) for r in barcode.reads]
            values.append(f"{sum(f.status == 'available' for f in facts)} / {count}")
            # Group repeated reasons so thousands of missing tracks do not
            # produce thousands of identical messages in the report.
            reasons = {f.reason for f in facts if f.status != 'available'}
            coverage_warnings.extend(f"{barcode.label} {kind}: {reason}" for reason in sorted(reasons))
        rows.append("<tr><th>" + escape(barcode.label) + "</th>" +
                    "".join(f"<td>{v}</td>" for v in values) + "</tr>")
        for key, fact in barcode.metrics.items():
            if not (key.startswith(("nanotel_final_", "km_", "below_"))):
                continue
            value = str(fact.value) if fact.status == "available" else fact.reason
            sources = {e.source_id for e in fact.evidence}
            source_text = "; ".join(s.path for s in run.sources if s.id in sources)
            # Present readable names; population/source columns retain the exact
            # distinction between the two filters and the KM input population.
            label = key.removeprefix("nanotel_final_").replace("_", " ")
            label = label.replace("km ", "KM ").replace(" pct", " (%)").replace(" bp", " (bp)")
            stats.append("<tr>" + "".join("<td>" + escape(str(v)) + "</td>" for v in (
                barcode.label, label, value, fact.unit or "", fact.population or "", source_text)) + "</tr>")
    warnings = list(run.warnings) + coverage_warnings
    for barcode in run.barcodes:
        warnings.extend(f"{barcode.label}: {w}" for w in barcode.warnings)
        for read in barcode.reads:
            warnings.extend(f"{barcode.label} / {read.original_id}: {w}" for w in read.warnings)
    provenance = "".join(f"<li>{escape(s.path)}{escape(' · ' + s.sheet) if s.sheet else ''}<br>SHA-256: {s.sha256}</li>" for s in run.sources)
    return ('<section><details><summary>Data availability and source statistics</summary>'
        '<p>Coverage below is for imported summary records. Missing data is not zero.</p>'
        f'<p>{escape(detail_note)}</p><table><tr><th>Barcode</th><th>Density</th><th>Motifs</th><th>Mapping</th></tr>'
        + ''.join(rows) + '</table><p>NanoTel final-filtered statistics, pre-edge KM estimates, and R post-analysis '
        'statistics describe different populations. KM medians are not pooled or averaged.</p>'
        '<div style="overflow-x:auto"><table><tr><th>Barcode</th><th>Source metric</th><th>Value / status</th>'
        '<th>Unit</th><th>Population</th><th>Source</th></tr>' + ''.join(stats) + '</table></div>'
        '<h3>Validation messages</h3><ul>' + ''.join('<li>' + escape(w) + '</li>' for w in dict.fromkeys(warnings))
        + '</ul><details><summary>Source files and checksums</summary><ul>' + provenance + '</ul></details></details></section>')
