"""Presentation counts over complete, already-filtered length exports."""
from html import escape
import math


def short_cutoff_bp(settings, barcode=None):
    options = settings.value if settings and settings.status == 'available' else {}
    if isinstance(options, dict):
        options = options.get('nanotel_analysis', options)
    value = options.get('short_telomere_threshold_bp') if isinstance(options, dict) else None
    if value is None and barcode is not None:
        fact = barcode.metrics.get('nanotel_final_short_telomere_threshold_bp')
        value = fact.value if fact and fact.status == 'available' else None
    try:
        if isinstance(value, bool) or not math.isfinite(float(value)) or float(value) <= 0:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def short_statistics(barcode, settings):
    cutoff = short_cutoff_bp(settings, barcode)
    fact = barcode.metrics.get('filtered_length_records')
    result = dict(cutoff_bp=cutoff, numerator=None, denominator=None, percent=None)
    if not fact or fact.status != 'available':
        return result
    values = [row['length_bp'] for row in fact.value]
    result['denominator'] = len(values)
    if cutoff is not None and values:
        result['numerator'] = sum(value < cutoff for value in values)
        result['percent'] = 100 * result['numerator'] / len(values)
    return result


def short_summary_html(barcode, settings):
    return _summary_html(short_statistics(barcode, settings))


def pooled_short_statistics(run):
    """Pool counts only when every barcode has complete, comparable data."""
    rows = [short_statistics(barcode, run.settings) for barcode in run.barcodes]
    result = dict(cutoff_bp=None, numerator=None, denominator=None, percent=None)
    if not rows or any(row['denominator'] is None for row in rows):
        return result
    result['denominator'] = sum(row['denominator'] for row in rows)
    cutoffs = {row['cutoff_bp'] for row in rows if row['denominator'] > 0}
    if not result['denominator']:
        result['cutoff_bp'] = short_cutoff_bp(run.settings)
    elif len(cutoffs) == 1 and None not in cutoffs:
        result['cutoff_bp'] = cutoffs.pop()
        result['numerator'] = sum(row['numerator'] or 0 for row in rows)
        result['percent'] = 100 * result['numerator'] / result['denominator']
    return result


def pooled_short_summary_html(run):
    return _summary_html(pooled_short_statistics(run), pooled=True)


def _summary_html(result, *, pooled=False):
    cutoff = result['cutoff_bp']
    definition = f'Length < {cutoff:,.0f} bp ({cutoff / 1000:g} kb).' if cutoff is not None else 'Cutoff unavailable.'
    if result['percent'] is not None:
        display = f"{result['percent']:.1f}%"
        note = f"< {cutoff / 1000:g} kb · {result['numerator']:,}/{result['denominator']:,} post-filtered telomeric reads"
        if pooled:
            note += ' across all barcodes'
    elif result['denominator'] == 0:
        display = 'No reads'
        note = definition + ' Denominator: 0 post-filtered telomeric reads; percentage is undefined.'
    else:
        display = 'Unavailable'
        note = definition + ' A recorded cutoff and complete post-filtered read lengths are required.'
        if pooled:
            note = definition + ' Complete lengths and a common cutoff across all barcodes are required.'
    return ('<article class="stat stat-short short-telomere-stat">'
            '<svg aria-hidden="true" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.5">'
            '<path d="M8 12h32M12 8v8M20 8v8M28 8v8M36 8v8M8 34h16M12 30v8M20 30v8M34 23v18m-6-6 6 6 6-6"/></svg><div>'
            '<h3>Short telomeres</h3><strong>' + display + '</strong><p>' + escape(note) + '</p></div></article>')


def add_cutoff_line(layout, cutoff_bp, *, axis='y', unit='kb'):
    """Add an explicitly labelled reference line without changing any data."""
    if cutoff_bp is None or unit not in ('bp', 'kb'):
        return
    value = cutoff_bp / (1000 if unit == 'kb' else 1)
    shape = dict(type='line', name='short-telomere-cutoff',
                 line=dict(color='#b45309', width=1.5, dash='dash'))
    annotation = dict(name='short-telomere-cutoff-label', showarrow=False,
                      text=f'Short: < {cutoff_bp / 1000:g} kb', font=dict(size=12, color='#92400e'))
    if axis == 'y':
        shape.update(xref='paper', x0=0, x1=1, yref='y', y0=value, y1=value)
        annotation.update(xref='paper', x=1, xanchor='right', yref='y', y=value, yanchor='bottom')
    else:
        shape.update(xref='x', x0=value, x1=value, yref='paper', y0=0, y1=1)
        annotation.update(xref='x', x=value, xanchor='left', yref='paper', y=1, yanchor='top')
    layout['shapes'] = list(layout.get('shapes') or []) + [shape]
    layout['annotations'] = list(layout.get('annotations') or []) + [annotation]
