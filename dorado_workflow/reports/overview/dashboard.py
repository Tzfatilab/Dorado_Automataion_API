"""Generate the first All Barcodes screen from existing NanoTel outputs.

Usage: python -m dorado_workflow.reports.all_barcodes RESULTS --output REPORT
Detection, filtering and source import remain in the existing modules.

Data flow: results directory -> validated Run model -> presentation aggregates
-> HTML cards and Plotly figures. The source files are read, never modified.
Outputs are index.html (self-contained browser view) and source-data.json
(imported facts, availability states and provenance for auditing).

This renderer connects overview, barcode, and read pages. It never runs
scientific analysis or infers missing chromosome annotations.
"""
import argparse
from html import escape
from pathlib import Path
import json
from dataclasses import asdict
from dorado_workflow.reports.interactive.importers import import_results
from dorado_workflow.reports.interactive.dashboard import dashboard_data
from dorado_workflow.reports.overview.comparisons import comparison_figures
from dorado_workflow.reports.shared.availability import availability_html
from dorado_workflow.reports.barcode.dashboard import barcode_views, ROUTER
from dorado_workflow.reports.barcode.length_plots import histogram_sections, telomere_plot_sections

TITLE = "Telomere Analysis Summary - All Barcodes"
# Inline SVG paths, in the same order as the six card specifications below.
# Keeping icons local avoids network requests and missing external font assets.
# They are decorative (aria-hidden); the adjacent text supplies their meaning.
ICONS = [
    '<ellipse cx="24" cy="10" rx="15" ry="6"/><path d="M9 10v27c0 8 30 8 30 0V10M9 19c0 8 30 8 30 0M9 28c0 8 30 8 30 0"/>',
    '<rect x="12" y="5" width="27" height="38" rx="4"/><path d="M19 15h7M19 23h13M19 30h13M19 37h13"/>',
    '<path d="M12 4c0 20 24 20 24 40M36 4c0 20-24 20-24 40M13 10h22M17 17h14M17 31h14M13 38h22"/>',
    '<path d="M24 5v19h19A19 19 0 1 1 24 5ZM30 4v14h14A19 19 0 0 0 30 4Z"/>',
    '<path d="m5 34 29-29 10 10-29 29ZM28 11l5 5M23 16l3 3M18 21l5 5M13 26l3 3"/>',
    '<path d="M13 5c-7 0 0 15 7 19-7 4-14 19-7 19 5 0 6-12 11-16 5 4 6 16 11 16 7 0 0-15-7-19 7-4 14-19 7-19-5 0-6 12-11 16C19 17 18 5 13 5Z"/>',
]


def render_screen(run, results_root=None):
    """Render an imported Run model without writing files or changing its data.

    Aggregates come from dashboard_data(), which preserves population and
    availability rules. Unit conversion and rounding below affect display only.
    Plotly's JavaScript and the sibling stylesheet are embedded once, allowing
    the returned document to open from file:// without a server or internet.
    """
    # Lazy imports keep the importer usable independently of chart generation.
    import plotly.graph_objects as go
    from plotly.offline import get_plotlyjs
    # Reuse the shared aggregate layer; do not average barcode medians here.
    data = dashboard_data(run)
    metrics = data["metrics"]
    nanotel_population = any(b.metrics.get("amount_of_telomeres") and
        b.metrics["amount_of_telomeres"].population == "NanoTel final-filtered reads" for b in run.barcodes)

    # Use an explicit run chromosome statistic when supplied. Reference counts
    # must never substitute for missing chromosome annotations.
    if "detected_chromosomes" in run.metrics:
        metrics["detected_chromosomes"] = asdict(run.metrics["detected_chromosomes"])
    cards = []
    # Card order mirrors the approved design; notes identify each population.
    specs = [("barcode_count", "Total barcodes", ""),
             ("total_reads", "Total reads", "Input reads"),
             ("telomeric_reads", "Total telomeric reads", "Post-filtered reads"),
             ("telomeric_percentage", "% telomeric reads", "Of total input reads"),
             ("median_telomere_length", "Median length", "Pooled post-filtered reads"),
             ("detected_chromosomes", "Chromosomes", "Chromosome annotations unavailable")]
    # Reference labels are not chromosome annotations; never substitute their count.
    for index, (key, label, note) in enumerate(specs):
        # A missing metric key is handled like an unavailable fact. This also
        # supports the chromosome card before chromosome annotations exist.
        fact = metrics.get(key, {})
        # Missing facts must not appear as zero; an available zero is valid.
        value = fact.get("value") if fact.get("status") == "available" else None
        display = "Unavailable"
        if value is not None:
            if key == "detected_chromosomes":
                note = "Distinct annotated chromosomes"
            # Stored lengths remain in bp; only the displayed median uses kb.
            # Fractions in dashboard_data are already percentages, so do not
            # multiply them by 100 a second time.
            display = f"{value / 1000:,.2f} kb" if key == "median_telomere_length" else f"{value:.2f}%" if key == "telomeric_percentage" else f"{value:,}"
        # Escape source-derived captions/tooltips before inserting them into HTML.
        caption = f'<p>{escape(note)}</p>' if note else ''
        cards.append(f'<article class="stat stat-{index}" title="{escape(fact.get("reason") or note, quote=True)}"><svg viewBox="0 0 48 48" aria-hidden="true">{ICONS[index]}</svg><div><h3>{label}</h3><strong class="{"missing" if value is None else ""}">{display}</strong>{caption}</div></article>')
    # Only source-reported post-filtered counts enter the bars. An unavailable
    # barcode count is omitted rather than fabricated as a zero-height bar.
    counts = [(b.label.replace("barcode", "BC"), b.metrics["amount_of_telomeres"].value)
              for b in run.barcodes if b.metrics["amount_of_telomeres"].status == "available"]
    # Keep x labels, heights and text in the same source order. cliponaxis=False
    # allows count labels to remain visible above the plotting rectangle.
    bars = go.Figure(go.Bar(x=[x for x, _ in counts], y=[y for _, y in counts],
        marker_color="#5996E8", width=0.55, text=[str(y) for _, y in counts], textposition="outside", cliponaxis=False,
        hovertemplate="%{x}<br>%{y} telomeric reads<extra></extra>"))
    # Leave headroom for count labels, including an all-zero dataset.
    bars.update_layout(xaxis_title="Barcode", yaxis_title="Telomeric reads",
                       yaxis_range=[0, max([y for _, y in counts] or [1]) * 1.18 or 1])
    # Plot individual exported lengths, not summaries of barcode summaries.
    boxes = go.Figure()
    for item in data["distributions"]:
        if item["lengths"]["status"] != "available":
            continue
        # A linear axis displays all exported lengths, including zero.
        records = item["lengths"]["value"]
        values = [r["length_bp"] / 1000 for r in records]
        # Keep identity attached to each plotted observation, including duplicate
        # lengths. Matching by a y value would route equal-length reads incorrectly.
        customdata = [[item["id"], r.get("read_id")] for r in records]
        # Each barcode is a separate trace. Plotly computes presentation
        # quartiles from these source lengths; jitter only separates markers
        # horizontally and never changes a read's length.
        boxes.add_trace(go.Box(name=item["label"].replace("barcode", "BC"), y=values,
            customdata=customdata, boxpoints="all", jitter=0.16, pointpos=0, fillcolor="#a6d0f5", line_color="#214e78",
            marker=dict(color="#3d83c9", size=5), hovertemplate="%{y:.3f} kb<extra>%{fullData.name}</extra>"))
    boxes.update_layout(xaxis_title="Barcode", yaxis_title="Telomere length (kb)",
                        yaxis_type="linear", yaxis_rangemode="tozero")
    # Both panels share typography, dimensions and offline Plotly settings.
    panels = []
    for index, title, fig, note in [(2, "Telomeric Reads by Barcode", bars, "Post-filtered telomeric reads."),
                                    (3, "Telomere Length by Barcode", boxes, "Post-filtered reads. Linear scale; a single read appears as a point.")] + comparison_figures(run):
        if fig is None:
            panels.append(note)
            continue
        fig.update_layout(template="plotly_white", height=350, showlegend=index == 4,
            margin=dict(l=65, r=175 if index == 4 else 24, t=25, b=65), font=dict(family="Segoe UI, Arial", color="#12203c"))
        # Bar charts can contain an empty trace, so trace count alone cannot
        # identify missing count data. Paper coordinates center the message
        # independently of the axis units and logarithmic scale.
        if not fig.data or (index == 2 and not counts):
            fig.add_annotation(text="Data unavailable", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)
        # The document head includes Plotly once; figures supply only their
        # own markup and initialization script.
        chart = fig.to_html(full_html=False, include_plotlyjs=False,
                            config={"responsive": True, "displaylogo": False, "scrollZoom": False})
        panels.append(f'<section><h2><span class="number">{index}</span>{title}</h2>{chart}<p class="note">{note}</p></section>')
    # Resolve beside this module, independent of the process working directory.
    histograms = histogram_sections(run, results_root)
    read_plots = telomere_plot_sections(run, results_root)
    # Sections 2 and 3 share a row on desktop and stack on smaller screens.
    barcode_plots = {b.id: '<div class="charts">' + histograms[b.id] + read_plots[b.id] + '</div>'
                     for b in run.barcodes}
    navigation, barcode_pages = barcode_views(run, ICONS, barcode_plots, results_root=results_root)
    css = (Path(__file__).parents[1] / "assets" / "dashboard.css").read_text(encoding="utf-8")
    # Combine the complete page in memory. Cards appear before the two panels;
    # CSS controls wrapping while figure scripts attach hover/zoom behavior.
    html = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{TITLE}</title><style>{css}</style><script>{get_plotlyjs()}</script></head><body><header><h1>{TITLE}</h1><span>Project overview &nbsp; | &nbsp; NanoTel summary</span></header><main><div id="run-overview">{navigation}<section><h2><span class="number">1</span>Key Statistics (All Barcodes)</h2><div class="stats">{"".join(cards)}</div></section><div class="charts">{"".join(panels)}</div>{availability_html(run)}</div>{barcode_pages}<section id="unknown-barcode" hidden><h2>Barcode or read not found</h2><a href="#/">Back to All Barcodes</a></section></main>{ROUTER}</body></html>'
    export_script = (Path(__file__).parents[1] / 'assets' / 'graph_export.js').read_text(encoding='utf-8')
    table_export_script = (Path(__file__).parents[1] / 'assets' / 'table_export.js').read_text(encoding='utf-8')
    spacing_script = (Path(__file__).parents[1] / 'assets' / 'chromosome_spacing.js').read_text(encoding='utf-8')
    spacing_script += '\n' + (Path(__file__).parents[1] / 'assets' / 'barcode_navigation.js').read_text(encoding='utf-8')
    html = html.removesuffix('</body></html>') + '<script>' + export_script + '</script><script>' + table_export_script + '</script><script>' + spacing_script + '</script></body></html>'
    if nanotel_population:
        html = html.replace('Post-filtered', 'NanoTel final-filtered').replace('post-filtered', 'NanoTel final-filtered')
    return html



def generate_report(results, output):
    """Import results and write a new report folder, returning its index path.

    Args:
        results: Directory understood by the existing NanoTel result importer.
        output: New destination directory. Existing destinations are rejected.

    Import/render errors propagate before any output directory is created.
    FileExistsError protects existing reports; filesystem write errors propagate
    to the caller. Writes are not transactional if a later filesystem write fails.
    """
    # Import only supported scientific exports. A folder containing only plots
    # or FASTA reads cannot supply summary statistics; availability stays explicit.
    destination = Path(output)
    if destination.exists():
        raise FileExistsError(f"Output already exists; choose a new report folder: {destination}")
    print("Importing NanoTel results...", flush=True)
    run = import_results(results)
    # Finish importing and rendering before creating the output folder, so
    # calculation/import errors do not leave an empty report destination.
    print(f"Rendering five sections for {len(run.barcodes)} barcodes...", flush=True)
    from dorado_workflow.reports.storage.archive import available_details
    with available_details(results):
        page = render_screen(run, results_root=results)
    destination = Path(output)
    # Refuse overwrites, including an existing empty destination directory.
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "index.html").write_text(page, encoding="utf-8")
    # Preserve unrounded imported facts and source evidence alongside the view.
    (destination / "source-data.json").write_text(json.dumps(run.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")
    return destination / "index.html"


def generate_run_report(results, nanotel_directory):
    """Save a self-contained dashboard.html directly under NanoTel.

    Source provenance and links to barcode reports are embedded in the HTML.
    Scientific exports stay at their original paths for downstream consumers.
    """
    from dorado_workflow.reports.storage.layout import write_run_reports, organize_barcode_reports
    from dorado_workflow.reports.storage.archive import available_details, pack_details
    organize_barcode_reports(nanotel_directory)
    # Import and embed saved plots while the archive contents are available.
    with available_details(results):
        run = import_results(results)
        page = render_screen(run, results_root=results)
        destination = write_run_reports(nanotel_directory, run, page)
    # Archive only after a complete dashboard has been saved successfully.
    for barcode in Path(nanotel_directory).glob('barcode*'):
        if barcode.is_dir():
            pack_details(barcode)
    return destination



def main():
    """Parse explicit input/output paths and print the generated HTML location."""
    parser = argparse.ArgumentParser(description=__doc__)
    # Path arguments are independent: results is the existing input folder;
    # --output must name a new folder, typically a child of results.
    parser.add_argument("results", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    # Print an absolute path for convenient opening from any working directory.
    # Exceptions intentionally reach the CLI caller with their original context.
    print(generate_report(args.results, args.output).resolve())


if __name__ == "__main__":
    main()
