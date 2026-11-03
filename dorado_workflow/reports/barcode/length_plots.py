"""Embed existing NanoTel histogram HTML without regenerating its statistics."""
from html import escape
from pathlib import Path
from html.parser import HTMLParser
import json
import hashlib
import re
from dorado_workflow.reports.shared.organism import show_km


def _hide_completeness(figure):
    """Hide completeness overlays in the embedded copy, retaining menu indexes."""
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
    """Remove the decorative rug box and align paired saved plot baselines."""
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
        super().__init__()
        self.inside = False
        self.parts = []
        self.count = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('id') == 'figure':
            self.inside = True
            self.count += 1

    def handle_data(self, data):
        if self.inside:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'script':
            self.inside = False


def histogram_sections(run, results_root=None):
    """Section 2 uses the original histogram and its unit controls."""
    return _saved_plot_sections(run, results_root, 'histogram', 3,
        'Telomere Length Distribution',
        'Saved NanoTel histogram; original count/percentage controls and population are preserved. '
        'NanoTel final-filtered reads may differ from the R post-analysis population in the cards above.')


def telomere_plot_sections(run, results_root=None):
    """Section 3 preserves the original per-read plot, including its axes."""
    return _saved_plot_sections(run, results_root, 'plot', 4,
        'Telomere and Read Length per Read',
        'Saved NanoTel per-read plot. Original traces, running median, axes and pre-final-filter population are preserved.')


def _saved_plot_sections(run, results_root, kind, number, title, note):
    """Reuse the figure saved in NanoTel's histogram HTML, with no recalculation.

    Extract JSON, not executable HTML. The parent report supplies offline Plotly.
    Duplicate files and unsupported legacy HTML remain explicitly unavailable.
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
        if not paths and stored is None and getattr(run.stages.get('summary_only'),'value',False):
            sections[barcode.id]=_summary_length_plot(barcode,run.settings,kind,heading)
            continue
        if len(paths) != 1 and stored is None:
            reason = (f'Multiple matching {kind} files; select an unambiguous results directory.' if paths else
                      f'Saved NanoTel {kind} not available. Summary-only runs do not generate this plot.')
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
        source = escape(path.relative_to(root).as_posix()) if paths else 'Retained original NanoTel figure in Summary workbook'
        digest = hashlib.sha256(raw).hexdigest()
        sections[barcode.id] = (heading + '<div class="saved-histogram"></div>'
            f'<script type="application/json" class="histogram-figure">{payload}</script>'
            f'<p class="note">{escape(note)}</p>'
            f'<details class="note"><summary>Plot source</summary>{source}<br>SHA-256: {digest}</details></section>')
    return sections


def _summary_length_plot(barcode, settings, kind, heading):
    """Numeric fallback when original NanoTel plot specifications were not saved.

    Explicitly uses imported populations; never reconstructs filter decisions or
    running medians from a different population.
    """
    import plotly.graph_objects as go
    from ..reads.browser import read_rows
    from ..reads.density import mismatch_enabled
    from ..shared.short_telomeres import short_cutoff_bp, add_cutoff_line
    rows=read_rows(barcode,include_unfiltered=kind=='plot')
    fig=go.Figure()
    if kind=='histogram':
        values=[r['telomere']/1000 for r in rows or [] if r['telomere'] is not None]
        fig.add_trace(go.Histogram(x=values,name='Telomere length',marker_color='#6795de'))
        fig.update_layout(xaxis_title='Telomere length (kb)',yaxis_title='Read count',updatemenus=[dict(buttons=[
            dict(label='Read count',method='update',args=[{'histnorm':['']},{'yaxis.title.text':'Read count'}]),
            dict(label='Percentage',method='update',args=[{'histnorm':['percent']},{'yaxis.title.text':'Percentage'}])])])
        note='Imported post-filtered reads, matching the cards and read table. Original NanoTel final-filter plot data was not saved in this older Summary run.'
    else:
        rows=sorted(rows or [],key=lambda r:-(r['length'] or 0))
        method='mismatch_length' if mismatch_enabled(settings) is True else 'exact_length'
        for key,name,color in [('length','Read length','#e8735a'),(method,'Telomere length','#228b22')]:
            fig.add_trace(go.Scatter(x=list(range(1,len(rows)+1)),y=[r[key]/1000 if r[key] is not None else None for r in rows],
                mode='lines+markers',name=name,line=dict(color=color),marker=dict(size=4),meta='read-links',
                customdata=[[barcode.id,r['id']] for r in rows],text=[r['label'] for r in rows],
                hovertemplate='%{text}<br>'+name+': %{y:.3f} kb<extra></extra>'))
        fig.update_layout(xaxis_title='Read (sorted by read length)',yaxis_title='Length (kb)',showlegend=True,legend=dict(orientation='h',y=-.2))
        note='Imported before-filter summary reads, sorted by read length. Original NanoTel pre-edge plot/running-median data was not saved; no running median is inferred.'
    fig.update_layout(template='plotly_white',height=460,margin=dict(l=75,r=25,t=25,b=100),font=dict(family='Segoe UI, Arial',color='#12203c'))
    layout=fig.layout.to_plotly_json();add_cutoff_line(layout,short_cutoff_bp(settings,barcode),axis='x' if kind=='histogram' else 'y');fig.update_layout(layout)
    return heading+'<div class="saved-histogram"></div><script type="application/json" class="histogram-figure">'+fig.to_json().replace('<','\\u003c')+'</script><p class="note">'+escape(note)+'</p></section>'
