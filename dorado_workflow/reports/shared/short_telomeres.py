"""Presentation counts over complete, already-filtered length exports."""
from html import escape
import math


def short_cutoff_bp(settings, barcode=None):
    """Positive cutoff in base pairs, or None when not recorded or invalid.

    Args:
        settings: Recorded analysis settings and their availability.
        barcode: Imported Barcode record containing reads, metrics and evidence. Default: None.

    Returns:
        Positive cutoff in base pairs, or None when not recorded or invalid.
    """
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


def short_statistics(barcode, settings, method=None):
    """Count lengths strictly below the cutoff over the exported filtered reads.

    An empty population has denominator zero and an undefined percentage;
    missing measurements remain unavailable rather than becoming zero.

    Args:
        barcode: Imported Barcode record containing reads, metrics and evidence.
        settings: Recorded analysis settings and their availability.

    Returns:
        Dictionary containing cutoff, numerator, denominator and short percentage.
    """
    cutoff = short_cutoff_bp(settings, barcode)
    fact = barcode.metrics.get('filtered_length_records')
    result = dict(cutoff_bp=cutoff, numerator=None, denominator=None, percent=None)
    if method is not None:
        from .measurement_statistics import method_statistics
        stats = method_statistics(barcode, settings, method, 'after')
        values = stats['lengths']
        result['requested'] = stats['requested']
        result['denominator'] = stats['measured']
        if values and cutoff is not None:
            result['numerator'] = sum(n < cutoff for n in values)
            result['percent'] = stats['short_percent']
        return result
    if not fact or fact.status != 'available':
        return result
    values = [row['length_bp'] for row in fact.value]
    result['denominator'] = len(values)
    if cutoff is not None and values:
        result['numerator'] = sum(value < cutoff for value in values)
        result['percent'] = 100 * result['numerator'] / len(values)
    return result


def short_summary_html(barcode, settings):
    """Short summary html.

    Args:
        barcode: Imported Barcode record containing reads, metrics and evidence.
        settings: Recorded analysis settings and their availability.

    Returns:
        HTML markup for short summary html.
    """
    from .repeat_categories import displayed_methods
    return _combined_summary_html([(method, short_statistics(barcode, settings, method)) for method, _ in displayed_methods(settings)])


def _combined_summary_html(results):
    cutoffs = {row['cutoff_bp'] for _, row in results if row.get('requested') is not False}
    cutoff = next(iter(cutoffs)) if len(cutoffs) == 1 else None
    caption = 'After filtering'
    caption += f' \u00b7 Telomere length < {cutoff / 1000:g} kb' if cutoff is not None else ' \u00b7 Cutoff unavailable'
    values = ''.join(_summary_html(row, method=method) for method, row in results)
    return ('<article class="stat stat-short-compact"><svg aria-hidden="true" viewBox="0 0 48 48"><path d="M6 20A18 18 0 0 1 36 8l6 6M42 4v10H32M42 28A18 18 0 0 1 12 40l-6-6M6 44V34h10M18 28v-6M24 28V16M30 28v-8"/></svg><h3>Short telomeres (%)</h3>'
            '<div class="short-method-values">' + values + '</div><p class="short-card-note">'
            + escape(caption) + '</p></article>')


def _summary_html(result, *, method=None):
    """Summary html.

    Args:
        result: Result produced by the preceding operation.

    Returns:
        HTML markup for summary html.
    """
    cutoff = result['cutoff_bp']
    definition = f'Telomere length < {cutoff:,.0f} bp ({cutoff / 1000:g} kb).' if cutoff is not None else 'Cutoff unavailable.'
    if result.get('requested') is False:
        display, note = 'Off', 'This matching mode was not requested.'
    elif result['percent'] is not None:
        display = f"{result['percent']:.1f}%"
        note = f"< {cutoff / 1000:g} kb · {result['numerator']:,}/{result['denominator']:,} measured post-filtered telomeric reads"
    elif result['denominator'] == 0:
        display = '\u2014'
        note = definition + ' Denominator: 0 measured telomere lengths; percentage is undefined.'
    else:
        display = '\u2014'
        note = definition + ' A recorded cutoff and complete post-filtered telomere lengths are required.'
    mode = {'exact': 'Canonical', 'mismatch': '+ Mismatch', 'tvr_inclusive': '+ TVRs', 'tsq_inclusive': '+ TSQ'}.get(method, 'Short telomeres')
    description = {'exact': 'Without mismatch or TVR. ', 'mismatch': 'With mismatch, without TVR. ',
                   'tvr_inclusive': 'Including TVRs, using the recorded matching settings. '}.get(method, '')
    return ('<div class="short-telomere-stat" data-compact-card="true" data-short-method="'+(method or '')
            +'" title="'+escape(description + note, quote=True)+'"><h4>'+escape(mode)+'</h4><strong'
            + (' aria-label="Unavailable"' if display == '\u2014' else '') + '>'
            + display + '</strong><p class="short-method-note">' + escape(note) + '</p></div>')


def short_table_summary_html(barcode, settings):
    """One overview-table cell retaining three distinct post-filter percentages."""
    from .repeat_categories import displayed_methods
    results = [(method, label, short_statistics(barcode, settings, method)) for method, label in displayed_methods(settings)]
    parts = []
    for method, label, result in results:
        attributes = ''
        if result.get('requested') is False:
            display = 'Off'
        elif result['percent'] is not None:
            display = f"{result['percent']:.2f}%"
        else:
            display = '\u2014'
            attributes = ' aria-label="Unavailable" title="Percentage unavailable: a valid cutoff and measured telomere lengths are required."'
        parts.append('<div class="short-summary-method" data-short-method="' + method + '"><span>' + label + '</span><strong' + attributes + '>'
                     + display + '</strong></div>')
    cutoff = short_cutoff_bp(settings, barcode)
    note = f'After filtering \u00b7 Telomere length < {cutoff / 1000:g} kb' if cutoff is not None else 'After filtering \u00b7 Cutoff unavailable'
    return ('<div class="short-summary-card"><div class="short-summary-methods">' + ''.join(parts)
            + '</div><div class="short-summary-note">' + escape(note) + '</div></div>')


def add_cutoff_line(layout, cutoff_bp, *, axis='y', unit='kb'):
    """Add an explicitly labelled reference line without changing any data.

    Args:
        layout: Layout object to inspect or update.
        cutoff_bp: Short-telomere cutoff in base pairs; lengths below it are short.
        axis: Plot axis receiving the cutoff reference line. Default: 'y'.
        unit: Measurement or display unit. Default: 'kb'.

    Returns:
        None.
    """
    if cutoff_bp is None or unit not in ('bp', 'kb'):
        return
    value = cutoff_bp / (1000 if unit == 'kb' else 1)
    shape = dict(type='line', name='short-telomere-cutoff',
                 line=dict(color='#b45309', width=1.5, dash='dash'))
    annotation = dict(name='short-telomere-cutoff-label', showarrow=False,
                      text=f'Short telomeres: < {cutoff_bp / 1000:g} kb', font=dict(size=12, color='#92400e'))
    if axis == 'y':
        shape.update(xref='paper', x0=0, x1=1, yref='y', y0=value, y1=value)
        annotation.update(xref='paper', x=1, xanchor='right', yref='y', y=value, yanchor='bottom')
    else:
        shape.update(xref='x', x0=value, x1=value, yref='paper', y0=0, y1=1)
        annotation.update(xref='x', x=value, xanchor='left', yref='paper', y=1, yanchor='top')
    layout['shapes'] = list(layout.get('shapes') or []) + [shape]
    layout['annotations'] = list(layout.get('annotations') or []) + [annotation]
