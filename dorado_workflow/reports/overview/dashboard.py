"""Generate the first All Barcodes screen from existing NanoTel outputs.

Usage: python -m dorado_workflow.reports.all_barcodes RESULTS --output REPORT
Detection, filtering and source import remain in the existing modules.

Data flow: results directory -> validated Run model -> presentation aggregates
-> HTML cards and Plotly figures. The renderer reads source files; workflow publication manages their lifecycle.
Outputs are index.html (self-contained browser view) and source-data.json
(imported facts, availability states and provenance for auditing).

This renderer connects overview, barcode, and read pages. It never runs
scientific analysis or infers missing chromosome annotations.
"""
import argparse
from pathlib import Path
from ..storage.layout import atomic_text, SAVED_REPORTS_MARKER
import json
from html import escape
from dataclasses import asdict
from dorado_workflow.reports.interactive.importers import import_results
from dorado_workflow.reports.overview.comparisons import comparison_figures, comparison_data
from dorado_workflow.reports.barcode.dashboard import barcode_views, barcode_summary_section, ROUTER
from dorado_workflow.reports.barcode.length_plots import length_plot_sections

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


def render_screen(run, results_root=None, summary_only=False, comparisons=None):
    """Render an imported Run model without writing files or changing its data.

    Each summary row uses one barcode's recorded population. Unit conversion
    and rounding below affect display only; no pooled summary cards are built.
    Plotly's JavaScript and the sibling stylesheet are embedded once, allowing
    the returned document to open from file:// without a server or internet.

    Args:
        run: Imported run model containing barcodes, reads and source evidence.
        results_root: Results directory used to resolve saved scientific exports. Default: None.
        summary_only: Whether to omit individual-read pages from the report. Default: False.
        comparisons: Precomputed report comparisons; reused when supplied. Default: None.

    Returns:
        HTML markup for screen.
    """
    # Lazy imports keep the importer usable independently of chart generation.
    import plotly.graph_objects as go
    from plotly.offline import get_plotlyjs
    # Overview statistics are one row per barcode, without pooled summary cards.
    comparisons = comparison_data(run) if comparisons is None else comparisons
    distributions = [{"id": b.id, "label": b.label,
                      "lengths": asdict(b.metrics["filtered_length_records"])} for b in run.barcodes]
    nanotel_population = any(b.metrics.get("amount_of_telomeres") and
        b.metrics["amount_of_telomeres"].population == "NanoTel final-filtered reads" for b in run.barcodes)
    # Only source-reported post-filtered counts enter the bars. An unavailable
    # barcode count is omitted rather than fabricated as a zero-height bar.
    counts = [(b.label.replace("barcode", "BC"), b.metrics["amount_of_telomeres"].value)
              for b in run.barcodes if b.metrics["amount_of_telomeres"].status == "available"]
    # Keep x labels, heights and text in the same source order. cliponaxis=False
    # allows count labels to remain visible above the plotting rectangle.
    bars = go.Figure(go.Bar(x=[x for x, _ in counts], y=[y for _, y in counts],
        customdata=[b.id for b in run.barcodes if b.metrics["amount_of_telomeres"].status == "available"],
        meta="barcode-links",
        marker_color="#5996E8", width=0.55, text=[str(y) for _, y in counts], textposition="outside", cliponaxis=False,
        hovertemplate="%{x}<br>%{y} telomeric reads<extra></extra>"))
    # Leave headroom for count labels, including an all-zero dataset.
    bars.update_layout(xaxis_title="Barcode", yaxis_title="Number of telomeric reads",
                       yaxis_range=[0, max([y for _, y in counts] or [1]) * 1.18 or 1])
    # Plot individual exported lengths, not summaries of barcode summaries.
    boxes = go.Figure()
    from ..shared.short_telomeres import short_cutoff_bp, add_cutoff_line
    short_cutoffs = {}
    for item in distributions:
        if item["lengths"]["status"] != "available":
            continue
        # A linear axis displays all exported lengths, including zero.
        records = item["lengths"]["value"]
        values = [r["length_bp"] / 1000 for r in records]
        # Keep identity attached to each plotted observation, including duplicate
        # lengths. Matching by a y value would route equal-length reads incorrectly.
        barcode = next((b for b in run.barcodes if b.id == item['id']), None)
        cutoff = short_cutoff_bp(run.settings, barcode)
        short_cutoffs[item['label'].replace('barcode', 'BC')] = cutoff / 1000 if cutoff is not None else None
        labels = {}
        for read in barcode.reads if barcode else []:
            serial = read.metrics.get('read_number')
            if serial and serial.status == 'available':
                labels[read.id] = f'Read {int(serial.value)}'
        customdata = [[item["id"], r.get("read_id"), labels.get(r.get('read_id'), 'Read number unavailable')] for r in records]
        # Each barcode is a separate trace. Plotly computes presentation
        # quartiles from these source lengths; jitter only separates markers
        # horizontally and never changes a read's length.
        boxes.add_trace(go.Violin(name=item["label"].replace("barcode", "BC"), y=values,
            customdata=customdata, points="all", bandwidth=1.0 if len(set(values)) > 1 else 0, spanmode="hard", scalemode="width", box=dict(visible=False), pointpos=0, fillcolor="#a6d0f5", line_color="#214e78",
            marker=dict(color="#3d83c9", size=5), hovertemplate="%{customdata[2]}<br>Telomere length: %{y:.3f} kb<br>Click to open read<extra>%{fullData.name}</extra>"))
    boxes.update_layout(xaxis_title="Barcode", yaxis_title="Telomere length (kb)",
                        yaxis_type="linear", yaxis_rangemode="tozero",
                        updatemenus=[dict(type='dropdown',direction='down',active=0,
                            x=1,y=1.42,xanchor='right',yanchor='bottom',
                            buttons=[dict(label='Linear',method='relayout',args=[{'yaxis.type':'linear','yaxis.autorange':True,'yaxis.rangemode':'tozero'}]),
                                     dict(label='Logarithmic',method='relayout',args=[{'yaxis.type':'log','yaxis.autorange':True,'yaxis.rangemode':'normal'}])])])
    # Both panels share typography, dimensions and offline Plotly settings.
    panels = []
    for index, title, fig, note in sorted([(3, "Telomeric Reads by Barcode", bars, "Post-filtered telomeric reads."),
                                    (2, "Telomere Length by Barcode", boxes, "Post-filtered reads. Choose Linear or Logarithmic scale; zero lengths cannot appear on a logarithmic axis. A single read appears as a point.")] + comparison_figures(run, data=comparisons), key=lambda panel: panel[0]):
        if fig is None:
            panels.append(note)
            continue
        fig.update_layout(template="plotly_white", height=350, showlegend=False,
            margin=dict(l=65, r=120 if index == 5 else 24, t=25, b=65), font=dict(family="Segoe UI, Arial", color="#12203c"))
        if index == 2:
            from ..shared.plot_statistics import add_group_statistics
            add_group_statistics(fig, [(trace.name, list(trace.y)) for trace in fig.data], include_median=False,
                                 short_cutoffs=short_cutoffs)
            cutoffs = {value for value in short_cutoffs.values() if value is not None}
            if len(cutoffs) == 1 and None not in short_cutoffs.values():
                layout = fig.layout.to_plotly_json()
                add_cutoff_line(layout, next(iter(cutoffs)) * 1000)
                fig.update_layout(layout)
            elif cutoffs:
                for index, trace in enumerate(fig.data):
                    cutoff = short_cutoffs.get(trace.name)
                    if cutoff is not None:
                        fig.add_shape(type='line', name='short-telomere-cutoff', xref='x', x0=index-.35,
                                      x1=index+.35, yref='y', y0=cutoff, y1=cutoff,
                                      line=dict(color='#b45309', width=1.5, dash='dash'))
            note += ' Short percentages use n, the exported post-filtered reads plotted for each barcode; lengths equal to the cutoff are not short.'
            fig.update_layout(margin=dict(t=88))
        if index == 5:
            row_count = len(fig.data[0].y) if fig.data else 0
            fig.update_layout(height=620,
                yaxis=dict(tickmode='array',tickvals=list(fig.data[0].y) if fig.data else []),
                margin=dict(l=85,r=120,t=25,b=65))
        # Bar charts can contain an empty trace, so trace count alone cannot
        # identify missing count data. Paper coordinates center the message
        # independently of the axis units and logarithmic scale.
        if not fig.data or (index == 3 and not counts):
            fig.add_annotation(text="Data unavailable", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)
        # The document head includes Plotly once; figures supply only their
        # own markup and initialization script.
        chart = fig.to_html(full_html=False, include_plotlyjs=False,
                            config={"responsive": True, "displaylogo": False, "scrollZoom": False})
        width_style = ''
        if index == 5:
            chart = '<div style="max-width:1400px;margin:0 auto">' + chart + '</div>'
        panels.append(f'<section{width_style}><h2><span class="number">{index}</span>{title}</h2>{chart}<p class="note">{note}</p></section>')
    from ..shared.barcode_exclusion import exclusion_data_html
    selection_data = exclusion_data_html(run, comparisons=comparisons)
    # Resolve beside this module, independent of the process working directory.
    barcode_plots = length_plot_sections(run)
    navigation, barcode_pages = barcode_views(run, ICONS, barcode_plots, results_root=results_root,summary_only=summary_only,comparisons=comparisons)
    css = (Path(__file__).parents[1] / "assets" / "dashboard.css").read_text(encoding="utf-8")
    barcode_summary = barcode_summary_section(run, comparisons)
    body_attributes = ' data-run-label="' + escape(run.label, quote=True) + '"'
    body_attributes += ' data-summary-only="true"' if summary_only else ''
    organism = str(run.organism.value) if run.organism.status == 'available' else 'Not recorded'
    report_title = TITLE + ' | ' + run.label
    run_identity = ('Run: ' + escape(run.label) + ' &nbsp; | &nbsp; Organism: ' + escape(organism)
                    + (' &nbsp; | &nbsp; Summary' if summary_only else ''))
    if summary_only:
        css += 'body[data-summary-only] .reads-table tr:focus{outline:2px solid #d59a15}'
    # The per-barcode statistics table leads the overview comparison panels.
    html = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(report_title)}</title><style>{css}</style><script>{get_plotlyjs()}</script></head><body{body_attributes}><header><h1>{TITLE}</h1><span class="run-identity">{run_identity}</span></header><main><div id="run-overview">{navigation}{barcode_summary}<div class="charts">{"".join(panels)}</div>{selection_data}</div>{barcode_pages}<section id="unknown-barcode" hidden><h2>Barcode or read not found</h2><a href="#/">Back to All Barcodes</a></section>{SAVED_REPORTS_MARKER}</main>{ROUTER}</body></html>'
    export_script = (Path(__file__).parents[1] / 'assets' / 'graph_export.js').read_text(encoding='utf-8')
    table_export_script = (Path(__file__).parents[1] / 'assets' / 'table_export.js').read_text(encoding='utf-8')
    spacing_script = (Path(__file__).parents[1] / 'assets' / 'chromosome_spacing.js').read_text(encoding='utf-8')
    spacing_script += '\n' + (Path(__file__).parents[1] / 'assets' / 'barcode_navigation.js').read_text(encoding='utf-8')
    spacing_script += '\n' + (Path(__file__).parents[1] / 'assets' / 'barcode_scale.js').read_text(encoding='utf-8')
    spacing_script += '\n' + (Path(__file__).parents[1] / 'assets' / 'overview_layout.js').read_text(encoding='utf-8')
    spacing_script += '\n' + (Path(__file__).parents[1] / 'assets' / 'barcode_names.js').read_text(encoding='utf-8')
    spacing_script += '\n' + (Path(__file__).parents[1] / 'assets' / 'barcode_exclusion.js').read_text(encoding='utf-8')
    spacing_script += '\n' + (Path(__file__).parents[1] / 'assets' / 'barcode_compact_controls.js').read_text(encoding='utf-8')
    spacing_script += '\n' + (Path(__file__).parents[1] / 'assets' / 'barcode_header_design.js').read_text(encoding='utf-8')
    spacing_script += '\n' + (Path(__file__).parents[1] / 'assets' / 'report_workbook.js').read_text(encoding='utf-8')
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

    Returns:
        Path to the generated report index HTML.
    """
    # Import only supported scientific exports. A folder containing only plots
    # or FASTA reads cannot supply summary statistics; availability stays explicit.
    destination = Path(output)
    if destination.exists():
        raise FileExistsError(f"Output already exists; choose a new report folder: {destination}")
    from dorado_workflow.reports.storage.archive import available_details
    from dorado_workflow.reports.exports.dashboard_workbook import write_dashboard_workbook
    # Keep one extraction alive for import, HTML and workbook. Reopening the
    # archive separately for each output repeats decompression and hashing.
    with available_details(results):
        print("Importing NanoTel results...", flush=True)
        run = import_results(results)
        comparisons = comparison_data(run)
        print(f"Rendering five sections for {len(run.barcodes)} barcodes...", flush=True)
        page = render_screen(run, results_root=results, comparisons=comparisons)
        # Import/render errors still occur before creating the output directory.
        destination.mkdir(parents=True, exist_ok=False)
        (destination / "index.html").write_text(page, encoding="utf-8")
        (destination / "source-data.json").write_text(json.dumps(run.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")
        write_dashboard_workbook(run, destination / "nanotel_results.xlsx", results, comparisons=comparisons)
    return destination / "index.html"


def generate_run_report(results, nanotel_directory, progress=None):
    """Compatibility entry point; publication is owned by the workflow service."""
    from dorado_workflow.operators.report_publication import publish_run_report
    return publish_run_report(results, nanotel_directory, progress=progress)



def main():
    """Parse explicit input/output paths and print the generated HTML location.

    Inputs:
        None.

    Returns:
        None.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    # Path arguments are independent: results is the existing input folder;
    # --output must name a new folder, typically a child of results.
    parser.add_argument("results", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    # Print an absolute path for convenient opening from any working directory.
    # Exceptions intentionally reach the CLI caller with their original context.
    print(generate_report(args.results, args.output).resolve())


def render_summary(run, results_root=None, comparisons=None):
    """Render summary.

    Args:
        run: Imported run model containing barcodes, reads and source evidence.
        results_root: Results directory used to resolve saved scientific exports. Default: None.
        comparisons: Precomputed report comparisons; reused when supplied. Default: None.

    Returns:
        HTML markup for summary.
    """
    return render_screen(run, results_root=results_root, summary_only=True, comparisons=comparisons)


def write_summary_dashboard(run, destination, comparisons=None):
    """Write summary dashboard.

    Args:
        run: Imported run model containing barcodes, reads and source evidence.
        destination: Path where the new output is written.
        comparisons: Precomputed report comparisons; reused when supplied. Default: None.

    Returns:
        Path object for the requested artifact.
    """
    from ..shared.report_identity import dashboard_filename
    destination = Path(destination).with_name(dashboard_filename(run.label, summary=True))
    atomic_text(destination, render_summary(run, results_root=destination.parent, comparisons=comparisons))
    return destination


if __name__ == "__main__":
    main()
