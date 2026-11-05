"""Display saved NanoTel figures or plot explicitly exported read populations."""
from html import escape
from pathlib import Path
from html.parser import HTMLParser
import json
import hashlib
import re
from dorado_workflow.reports.shared.organism import show_km


def _hide_completeness(figure):
    """Hide completeness overlays in the embedded copy, retaining menu indexes.

    Args:
        figure: Plotly figure to annotate or style.

    Returns:
        None.
    """
    for trace in figure['data']:
        if 'censored' in str(trace.get('name', '')).casefold():
            # The rug repeats observations already counted in the histogram.
            # Retain its slot so saved count/percentage updates keep their targets.
            trace.clear()
            trace.update(type='scatter', x=[], y=[], visible=False, showlegend=False)
    layout = figure['layout']
    if isinstance(layout.get('meta'), dict):
        layout['meta'].pop('read_completeness', None)
    for annotation in layout.get('annotations', []):
        if isinstance(annotation.get('text'), str):
            annotation['text'] = re.sub(
                r'\s*\|\s*(?:complete|censored|unknown):\s*\d+', '',
                annotation['text'], flags=re.IGNORECASE)
    layout['annotations'] = [a for a in layout.get('annotations', [])
                             if 'censor' not in str(a.get('text', '')).casefold()]
    # No rug remains: attach the x axis to the main plot, without a blank lane.
    layout.setdefault('xaxis', {})['anchor'] = 'y'
    layout.setdefault('yaxis', {})['domain'] = [0, 1]
    layout.pop('yaxis2', None)


def _style_length_plot(layout):
    """Remove the decorative rug box and align paired saved plot baselines.

    Args:
        layout: Layout object to inspect or update.

    Returns:
        None.
    """
    layout['shapes'] = [shape for shape in layout.get('shapes', []) if not (
        shape.get('type') == 'rect' and shape.get('xref') == 'paper'
        and shape.get('yref') == 'paper' and shape.get('y0') == 0
        and shape.get('y1') == .07
        and str(shape.get('fillcolor', '')).upper() == '#FFF8FA')]
    layout['height'] = 620
    layout['margin'] = dict(l=80, r=30, t=24, b=140, autoexpand=False)


class _FigureParser(HTMLParser):
    """Read only NanoTel's saved JSON figure; never execute source HTML."""
    def __init__(self):
        """Initialize the instance and its dependencies.

        Inputs:
            None; uses instance state.

        Returns:
            None; initializes the instance.
        """
        super().__init__()
        self.inside = False
        self.parts = []
        self.count = 0

    def handle_starttag(self, tag, attrs):
        """Handle starttag.

        Args:
            tag: HTML element name reported by the parser.
            attrs: HTML attributes reported by the parser.

        Returns:
            None.
        """
        if tag == 'script' and dict(attrs).get('id') == 'figure':
            self.inside = True
            self.count += 1

    def handle_data(self, data):
        """Handle data.

        Args:
            data: Source data or presentation records for this operation.

        Returns:
            None.
        """
        if self.inside:
            self.parts.append(data)

    def handle_endtag(self, tag):
        """Handle endtag.

        Args:
            tag: HTML element name reported by the parser.

        Returns:
            None.
        """
        if tag == 'script':
            self.inside = False


def histogram_sections(run, results_root=None):
    """Prefer saved histograms; otherwise plot exported post-filtered lengths.

    Args:
        run: Imported run model containing barcodes, reads and source evidence.
        results_root: Results directory used to resolve saved scientific exports. Default: None.

    Returns:
        Saved length-histogram section HTML indexed by barcode.
    """
    return _saved_plot_sections(run, results_root, 'histogram', 3,
        'Telomere Length Distribution',
        'Saved NanoTel histogram; original count/percentage controls and population are preserved. '
        'NanoTel final-filtered reads may differ from the R post-analysis population in the cards above.')


def telomere_plot_sections(run, results_root=None):
    """Prefer saved per-read plots; otherwise plot exported before-filter reads.

    Args:
        run: Imported run model containing barcodes, reads and source evidence.
        results_root: Results directory used to resolve saved scientific exports. Default: None.

    Returns:
        Saved per-read length-plot section HTML indexed by barcode.
    """
    return _saved_plot_sections(run, results_root, 'plot', 4,
        'Telomere and Read Length per Read',
        'Saved NanoTel per-read plot. Original traces, running median, axes and pre-final-filter population are preserved.')


def _saved_plot_sections(run, results_root, kind, number, title, note):
    """Reuse saved figures, falling back to current exported measurements.

    Extract JSON, not executable HTML. The parent report supplies offline Plotly.
    Duplicate files and unsupported legacy HTML remain explicitly unavailable.

    Args:
        run: Imported run model containing barcodes, reads and source evidence.
        results_root: Results directory used to resolve saved scientific exports.
        kind: Saved figure kind: histogram or plot.
        number: Section number or numeric-source parser used by the enclosing adapter.
        title: Displayed title.
        note: Explanation displayed beside the chart.

    Returns:
        Rendered saved-plot sections indexed by barcode.
    """
    found = {}
    specifications = {}
    if results_root is not None:
        root = Path(results_root).resolve()
        for path in root.rglob(f'*_telomere_{kind}.html'):
            if path.is_file() and path.resolve().is_relative_to(root):
                found.setdefault(path.name.lower(), []).append(path)
        for path in root.rglob(f'*_telomere_{kind}.plotly.json'):
            if path.is_file() and path.resolve().is_relative_to(root):
                specifications.setdefault(path.name.lower(), []).append(path)
    regenerated = {}
    if kind == 'histogram':
        from .original_histograms import original_histograms
        missing = []
        for barcode in run.barcodes:
            saved = barcode.metrics.get('saved_barcode_figures')
            stored = saved.value.get(kind) if saved and saved.status == 'available' else None
            name = f'{barcode.label}_telomere_{kind}'
            if (not specifications.get((name + '.plotly.json').lower())
                    and not found.get((name + '.html').lower()) and stored is None):
                missing.append(barcode)
        regenerated = original_histograms(missing, run.settings)
    sections = {}
    for barcode in run.barcodes:
        paths = specifications.get(f'{barcode.label}_telomere_{kind}.plotly.json'.lower(), []) or found.get(f'{barcode.label}_telomere_{kind}.html'.lower(), [])
        # Use the numbered dashboard heading as the single visible plot title.
        heading = (f'<section><div class="histogram-heading"><h2><span class="number">{number}</span>'
                   f'{title}</h2><div class="histogram-controls" '
                   'role="group" aria-label="Histogram units"></div></div>')
        reason = ''
        saved=barcode.metrics.get('saved_barcode_figures')
        stored=saved.value.get(kind) if saved and saved.status=='available' else None
        if barcode.id in regenerated:
            stored = regenerated[barcode.id]
        if not paths and stored is None:
            # Recalculation deliberately omits old aggregate plots. Full and
            # Summary reports share the same fallback over the current exports.
            if kind == 'histogram':
                sections[barcode.id] = heading + '<p class="note">Original NanoTel histogram unavailable: complete exported lengths and the recorded matching mode are required.</p></section>'
            else:
                sections[barcode.id]=_exported_read_length_plot(barcode,run.settings,heading)
            continue
        if len(paths) != 1 and stored is None:
            reason = f'Multiple matching {kind} files; select an unambiguous results directory.'
        else:
            path = paths[0] if paths else Path(barcode.label+'_telomere_'+kind+'.plotly.json')
            raw = path.read_bytes() if paths else json.dumps(stored).encode('utf-8')
            try:
                if path.name.endswith('.plotly.json'):
                    figure = json.loads(raw.decode('utf-8-sig'))
                else:
                    parser = _FigureParser()
                    parser.feed(raw.decode('utf-8-sig'))
                    if parser.count != 1:
                        raise ValueError('Ambiguous figure')
                    figure = json.loads(''.join(parser.parts))
                if not isinstance(figure, dict) or not isinstance(figure.get('data'), list) or not isinstance(figure.get('layout'), dict):
                    raise ValueError('Unsupported figure schema')
                # R's older Plotly serializes titles as strings. Plotly 6 needs
                # title objects for saved updates such as yaxis.title.text.
                # Normalize presentation metadata only; source files, bins and
                # the saved count/percentage arrays remain unchanged.
                layout = figure['layout']
                if isinstance(layout.get('title'), str):
                    layout['title'] = {'text': layout['title']}
                # Hide the duplicate title only in this embedded copy. Keep
                # annotations/subtitles, scientific data and source HTML intact.
                layout['title'] = {'text': ''}
                if not show_km(run):
                    _hide_completeness(figure)
                # The dashboard supplies the title and unit buttons, so the
                # saved plot's large title/menu margin is no longer needed.
                if not isinstance(layout.get('margin', {}), dict):
                    raise ValueError('Invalid plot margins')
                layout.setdefault('margin', {})['t'] = 24
                _style_length_plot(layout)
                from ..shared.short_telomeres import short_cutoff_bp, add_cutoff_line
                # These saved plots can use a different exported population;
                # mark the definition, without borrowing their counts for cards.
                length_axis = 'xaxis' if kind == 'histogram' else 'yaxis'
                axis_title = layout.get(length_axis, {}).get('title', '')
                axis_title = axis_title.get('text', '') if isinstance(axis_title, dict) else str(axis_title)
                unit = 'kb' if re.search(r'\bkb\b', axis_title, re.I) else 'bp' if re.search(r'\bbp\b', axis_title, re.I) else None
                if unit:
                    add_cutoff_line(layout, short_cutoff_bp(run.settings, barcode),
                                    axis='x' if kind == 'histogram' else 'y', unit=unit)
                for key, axis in layout.items():
                    if re.fullmatch(r'[xy]axis\d*', key) and isinstance(axis, dict) and isinstance(axis.get('title'), str):
                        axis['title'] = {'text': axis['title']}
                # Escaping script delimiters prevents source labels closing the
                # JSON element. Values and histogram bins are retained verbatim.
                payload = json.dumps(figure, ensure_ascii=True, allow_nan=False).replace('<', '\\u003c')
            except (ValueError, UnicodeError, TypeError):
                reason = f'Saved {kind} has missing or invalid Plotly figure data.'
        if reason:
            sections[barcode.id] = heading + f'<p class="note">{reason}</p></section>'
            continue
        rebuilt = barcode.id in regenerated
        source = (escape(path.relative_to(root).as_posix()) if paths else
                  'Original NanoTel histogram builder; current exported post-filtered lengths' if rebuilt else
                  'Retained original NanoTel figure in Summary workbook')
        figure_note = ('Post-filtered reads, matching the cards and read table. Original NanoTel bins, smoothing and count/percentage controls.'
                       if rebuilt else note)
        digest = hashlib.sha256(raw).hexdigest()
        sections[barcode.id] = (heading + '<div class="saved-histogram"></div>'
            f'<script type="application/json" class="histogram-figure">{payload}</script>'
            f'<p class="note">{escape(figure_note)}</p>'
            f'<details class="note"><summary>Plot source</summary>{source}<br>SHA-256: {digest}</details></section>')
    return sections


def _exported_read_length_plot(barcode, settings, heading):
    """Show exported per-read lengths when the saved line plot is absent.

    Explicitly uses imported populations; never reconstructs filter decisions or
    running medians from a different population.

    Args:
        barcode: Imported Barcode record containing reads, metrics and evidence.
        settings: Recorded analysis settings and their availability.
        heading: Prepared section heading HTML.

    Returns:
        HTML containing a regenerated length chart and its source-data payload.
    """
    import plotly.graph_objects as go
    from ..reads.browser import read_rows
    from ..reads.density import mismatch_enabled
    from ..shared.short_telomeres import short_cutoff_bp, add_cutoff_line
    rows=read_rows(barcode,include_unfiltered=True)
    if rows is None:
        return heading + '<p class="note">Unavailable: complete exported before-filter read measurements are required for this chart.</p></section>'
    fig=go.Figure()
    rows=sorted(rows or [],key=lambda r:-(r['length'] or 0))
    method='mismatch_length' if mismatch_enabled(settings) is True else 'exact_length'
    for key,name,color in [('length','Read length','#e8735a'),(method,'Telomere length','#228b22')]:
        fig.add_trace(go.Scatter(x=list(range(1,len(rows)+1)),y=[r[key]/1000 if r[key] is not None else None for r in rows],
            mode='lines+markers',name=name,line=dict(color=color),marker=dict(size=4),meta='read-links',
            customdata=[[barcode.id,r['id']] for r in rows],text=[r['label'] for r in rows],
            hovertemplate='%{text}<br>'+name+': %{y:.3f} kb<extra></extra>'))
    fig.update_layout(xaxis_title='Read (sorted by read length)',yaxis_title='Length (kb)',showlegend=True,legend=dict(orientation='h',y=-.2))
    note='Before-filter summary reads, sorted by read length. Original NanoTel pre-edge plot data was not retained; no running median is inferred.'
    fig.update_layout(template='plotly_white',height=460,margin=dict(l=75,r=25,t=25,b=100),font=dict(family='Segoe UI, Arial',color='#12203c'))
    layout=fig.layout.to_plotly_json();add_cutoff_line(layout,short_cutoff_bp(settings,barcode),axis='y');fig.update_layout(layout)
    return heading+'<div class="saved-histogram"></div><script type="application/json" class="histogram-figure">'+fig.to_json().replace('<','\\u003c')+'</script><p class="note">'+escape(note)+'</p></section>'
