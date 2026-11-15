"""Length figures synchronized with the recorded read-table populations."""
from html import escape
import json
import re


RUNNING_MEDIAN_NOTE = ('Running median: cumulative median of the measured telomere lengths in the displayed read order; '
                       'missing telomere lengths are excluded. This display calculation does not change filtering.')


def _running_median_trace(x, lengths):
    from ..shared.plot_statistics import running_medians
    return dict(type='scatter', x=x, y=running_medians(lengths), mode='lines',
                name='Running median telomere length', line=dict(color='#4169e1', width=2.5),
                hovertemplate='Running median telomere length: %{y:.3f}<extra></extra>')


def _hide_completeness(figure):
    """Hide completeness overlays in the embedded copy, retaining menu indexes.

    Args:
        figure: Plotly figure to annotate or style.

    Returns:
        None.
    """
    for trace in figure['data']:
        if re.search(r'censor|kaplan|\bKM\b|completeness|^complete reads', str(trace.get('name', '')), re.I):
            # The rug repeats observations already counted in the histogram.
            # Retain its slot so saved count/percentage updates keep their targets.
            trace.clear()
            trace.update(type='scatter', x=[], y=[], visible=False, showlegend=False)
    layout = figure['layout']
    title = layout.get('title')
    if isinstance(title, str):
        layout['title'] = re.sub(r'\s*\|\s*(?:complete|censored|unknown):\s*\d+', '', title, flags=re.I)
    elif isinstance(title, dict) and isinstance(title.get('text'), str):
        title['text'] = re.sub(r'\s*\|\s*(?:complete|censored|unknown):\s*\d+', '', title['text'], flags=re.I)
    if isinstance(layout.get('meta'), dict):
        layout['meta'].pop('read_completeness', None)
    for annotation in layout.get('annotations', []):
        if isinstance(annotation.get('text'), str):
            annotation['text'] = re.sub(
                r'\s*\|\s*(?:complete|censored|unknown):\s*\d+', '',
                annotation['text'], flags=re.IGNORECASE)
    layout['annotations'] = [a for a in layout.get('annotations', [])
                             if not re.search(r'censor|kaplan|\bKM\b|completeness', str(a.get('text', '')), re.I)]
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
    layout.setdefault('legend', {}).update(orientation='h', x=0, xanchor='left', y=-.2, yanchor='top')


def length_plot_sections(run):
    """Build both length charts from the same recorded table populations.

    Histogram variants share one original NanoTel R renderer invocation. Only
    compact figure specifications are embedded; no read tracks are duplicated.
    Saved aggregate plots cannot be used here: their historical population can
    differ from the table, and bins cannot be filtered after aggregation.
    """
    from ..reads.browser import read_rows
    from ..reads.density import mismatch_enabled
    from .original_histograms import original_histograms
    mode = mismatch_enabled(run.settings)
    method = 'mismatch_length' if mode is True else 'exact_length'
    populations, requests = {}, []
    for barcode in run.barcodes:
        all_rows = read_rows(barcode, include_unfiltered=True)
        membership = barcode.metrics.get('filtered_length_records')
        filtered = ([row for row in all_rows if not row.get('source_note')]
                    if membership and membership.status == 'available' else None)
        # Missing membership evidence is unavailable, rather than zero reads.
        variants = dict(filtered=filtered, all=all_rows,
                        excluded=None if filtered is None else
                        [row for row in all_rows if row.get('source_note')])
        populations[barcode.id] = variants
        if mode is None:
            continue
        for population, rows in variants.items():
            if rows is None:
                continue
            measured = [row for row in rows if row.get(method) is not None]
            requests.append(dict(id=barcode.id + ':' + population,
                barcode=barcode.label, mismatch_allowance=int(mode), include_km=False,
                lengths_bp=[row[method] for row in measured],
                read_ids=[row['header'] for row in measured]))
    histograms = original_histograms(requests)
    sections = {}
    for barcode in run.barcodes:
        charts = []
        for kind, number, title in [('histogram', 3, 'Telomere Length Distribution'),
                                     ('plot', 4, 'Telomere and Read Length per Read')]:
            variants = {}
            for population, rows in populations[barcode.id].items():
                figure = histograms.get(barcode.id + ':' + population) if kind == 'histogram' else (
                    _read_length_figure(barcode, rows, method) if rows is not None and mode is not None else None)
                label = {'filtered': 'After filtering', 'all': 'All detected telomeric reads (before filtering)',
                         'excluded': 'Excluded by filtering'}[population]
                note = label + '. Telomere lengths: ' + ('including mismatch. ' if mode is True else 'canonical. ')
                if figure is not None:
                    figure['layout']['title'] = {'text': ''}
                    for axis in ('xaxis', 'yaxis'):
                        axis_layout = figure['layout'].get(axis, {})
                        if isinstance(axis_layout.get('title'), str):
                            axis_layout['title'] = dict(text=axis_layout['title'])
                    _style_length_plot(figure['layout'])
                    from ..shared.short_telomeres import short_cutoff_bp, add_cutoff_line
                    add_cutoff_line(figure['layout'], short_cutoff_bp(run.settings, barcode),
                                    axis='x' if kind == 'histogram' else 'y', unit='bp' if kind == 'histogram' else 'kb')
                    if kind == 'histogram':
                        # Completeness belongs to its own opt-in panels, never
                        # infer it from the chosen length-chart population.
                        note += 'Original NanoTel bins and smoothing. '
                        missing = sum(row.get(method) is None or row[method] <= 0 for row in rows)
                        note += f'{len(rows) - missing} measured of {len(rows)} reads; missing or non-positive telomere lengths omitted.'
                        for annotation in figure['layout'].get('annotations', []):
                            if 'No final-filtered reads' in str(annotation.get('text', '')):
                                annotation['text'] = 'No measured telomere lengths in this population'
                    else:
                        note += 'Sorted by total read length. ' + RUNNING_MEDIAN_NOTE
                else:
                    note += 'Unavailable: the recorded read population or matching mode is missing.'
                variants[population] = dict(figure=figure, note=note)
            initial = variants['filtered']
            choices = json.dumps(variants, ensure_ascii=True, allow_nan=False).replace('<', '\\u003c')
            charts.append(f'<section data-length-population-chart="{kind}"><div class="histogram-heading"><h2><span class="number">{number}</span>{title}</h2>'
                '<div class="histogram-controls" role="group" aria-label="Histogram units"></div></div>'
                '<div class="saved-histogram"></div>'
                '<script type="application/json" class="histogram-figure">{"data":[],"layout":{}}</script>'
                f'<script type="application/json" class="length-population-figures">{choices}</script>'
                f'<p class="note">{escape(initial["note"])}</p></section>')
        sections[barcode.id] = '<div class="charts barcode-length-charts">' + ''.join(charts) + '</div>'
    return sections


def _read_length_figure(barcode, rows, method):
    """Plot source measurements and the running median for exactly these rows."""
    rows = sorted(rows, key=lambda row: -(row['length'] or 0))
    x = list(range(1, len(rows) + 1))
    method_label = 'including mismatch' if method == 'mismatch_length' else 'Canonical'
    data = []
    for key, name, color in [('length', 'Total read length', '#e8735a'),
                             (method, 'Telomere length (' + method_label + ')', '#228b22')]:
        data.append(dict(type='scatter', x=x,
            y=[row[key]/1000 if row[key] is not None else None for row in rows],
            mode='lines+markers', name=name, line=dict(color=color), marker=dict(size=4), meta='read-links',
            customdata=[[barcode.id, row['id']] for row in rows], text=[row['label'] for row in rows],
            hovertemplate='%{text}<br>' + name + ': %{y:.3f} kb<extra></extra>'))
    data.append(_running_median_trace(x, [row[method]/1000 if row[method] is not None else None for row in rows]))
    layout = dict(xaxis=dict(title=dict(text='Read (sorted by read length)')),
                  yaxis=dict(title=dict(text='Length (kb)'), rangemode='tozero'), showlegend=True,
                  font=dict(family='Segoe UI, Arial', color='#12203c'),
                  plot_bgcolor='white', paper_bgcolor='white')
    if not rows:
        layout['annotations'] = [dict(text='No reads in this population', x=.5, y=.5,
                                     xref='paper', yref='paper', showarrow=False)]
    return dict(data=data, layout=layout)
