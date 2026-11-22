"""Offline barcode navigation and summary cards; no new scientific calculations."""
from html import escape
from pathlib import Path
from dorado_workflow.reports.overview.comparisons import comparison_data
from dorado_workflow.reports.barcode.repeats import composition_section, positions_section
from dorado_workflow.reports.barcode.chromosomes import chromosome_section
from dorado_workflow.reports.barcode.tsq_tandems import tsq_tandem_section
from dorado_workflow.reports.barcode.completeness import results_section
from dorado_workflow.reports.reads.browser import reads_section, READ_SCRIPT
from dorado_workflow.reports.reads.density import mismatch_enabled, tvr_enabled
from dorado_workflow.reports.shared.repeat_categories import tsq_enabled, tsq_read_count, variants_enabled, variant_panel_title
from dorado_workflow.reports.shared.organism import show_km
from dorado_workflow.reports.shared.short_telomeres import short_summary_html, short_cutoff_bp


def barcode_views(run, icons, histograms=None, results_root=None, summary_only=False, comparisons=None):
    """Render six cards per barcode from exported facts and existing aggregates.

    TVR counts require complete motif coverage of the post-filtered population.
    Chromosome counts use the same unambiguous assignments as the heatmap.
    Missing coverage remains unavailable, never zero or 100% canonical.

    Args:
        run: Imported run model containing barcodes, reads and source evidence.
        icons: SVG/icon markup indexed by statistic name.
        histograms: Saved histogram sections indexed by barcode. Default: None.
        results_root: Results directory used to resolve saved scientific exports. Default: None.
        summary_only: Whether to omit individual-read pages from the report. Default: False.
        comparisons: Precomputed report comparisons; reused when supplied. Default: None.

    Returns:
        Tuple containing barcode navigation HTML and all barcode-page HTML.
    """
    comparisons = comparison_data(run) if comparisons is None else comparisons
    km_enabled = show_km(run)
    mismatch = mismatch_enabled(run.settings)
    mismatch_attribute = 'unknown' if mismatch is None else str(mismatch).lower()
    tvr = tvr_enabled(run.settings)
    tsq = tsq_enabled(run.settings)
    repeats_requested = variants_enabled(run.settings)
    mismatch_panels = repeats_requested is False and mismatch is True
    repeat_method = 'mismatch' if mismatch_panels else 'tvr_inclusive'
    repeat_composition = {
        row['barcode']: row for row in comparisons.get('mismatch_composition', [])
    } if mismatch_panels else None
    tvr_attribute = 'unknown' if tvr is None else str(tvr).lower()
    histograms = histograms or {}
    composition = {row['barcode']: row for row in comparisons['composition']}
    pages, links = [], []
    for barcode in run.barcodes:
        label = barcode.label.replace('barcode', 'Barcode ')
        route = '#/barcode/' + barcode.id
        links.append(f'<a class="barcode-link" href="{route}">{escape(label)}</a>')
        from ..shared.barcode_statistics import barcode_key_statistics, mismatch_statistics, median_summary_html
        motifs = composition.get(barcode.label)
        repeat_row = repeat_composition.get(barcode.label) if mismatch_panels else motifs
        stats = barcode_key_statistics(barcode, run.settings, comparisons['cells'], motifs)
        total, telomeric = stats['total_reads'], stats['post_filtered_reads']
        empty = telomeric == 0
        med = stats['median_length_bp']
        tvr_stats = {'with_tvr': stats['reads_with_tvr'], 'motifs': stats['tvr_motifs']}
        if mismatch_panels:
            mismatch_stats = mismatch_statistics(barcode, repeat_row)
            tvr_stats = {'with_tvr': mismatch_stats['reads_with_mismatch'],
                         'motifs': mismatch_stats['mismatch_patterns']}
        percent = f'{100*telomeric/total:.1f}% of input reads' if total and telomeric is not None and telomeric <= total else 'Post-filtered reads'
        tvr_note = ('No post-filtered telomeric reads' if empty else
                    f"{100*tvr_stats['with_tvr']/telomeric:.2f}% of post-filtered reads" if telomeric and isinstance(tvr_stats['with_tvr'],int) else 'Complete coverage required')
        specs = [
            ('Total number of reads', total, 'Input reads', icons[0]),
            ('Number of telomeric reads', telomeric, 'After filtering · ' + percent, icons[2]),
            ('Median telomere length (kb)', med, 'Retained telomeric reads after filtration', icons[4]),
            ('Reads with mismatches' if mismatch_panels else 'Reads with TVRs', tvr_stats['with_tvr'] if isinstance(tvr_stats['with_tvr'],int) else None, tvr_note,
             '<path d="M8 40V23M19 40V8M30 40V17M41 40V4"/>'),
            ('Mismatch patterns' if mismatch_panels else 'TVR motifs', tvr_stats['motifs'] if isinstance(tvr_stats['motifs'],int) else None,
             'Distinct mismatch sequences in post-filtered telomeres' if mismatch_panels else 'Noncanonical motifs overlapping TVR-inclusive telomeres',
             '<circle cx="24" cy="10" r="6"/><circle cx="10" cy="36" r="6"/><circle cx="38" cy="36" r="6"/><path d="m21 16-8 14m14-14 8 14M16 36h16"/>'),
            ('Number of Chromosomes end found', stats['chromosomes'],
             'Unambiguous mapped post-filtered reads', icons[5]),
        ]
        cards = []
        for index, (title, number, note, icon) in enumerate(specs):
            if index == 2:
                cards.append(median_summary_html(barcode, run.settings, icon))
                continue
            if title == 'Reads with TVRs':
                continue
            display = 'Unavailable' if number is None else f'{number:,}'
            if tvr is False and not mismatch_panels and index in (3, 4):
                display = 'Off'
                note = 'No TVR patterns selected'
                number = None
            cards.append(f'<article class="stat stat-{index}"><svg aria-hidden="true" viewBox="0 0 48 48">{icon}</svg>'
                f'<div><h3>{title}</h3><strong class="{"missing" if number is None else ""}">{display}</strong><p>{escape(note)}</p></div></article>')
        if tsq is True:
            tsq_reads = tsq_read_count(barcode, run.settings)
            tsq_display = f'{tsq_reads:,}' if tsq_reads is not None else '\u2014'
            cards.insert(-1, '<article class="stat stat-tsq"><svg aria-hidden="true" viewBox="0 0 48 48"><path d="M16 5h16M20 5v14L8 39q-1 4 4 4h24q5 0 4-4L28 19V5M14 31h20"/></svg><div><h3>Reads containing TSQ</h3><strong>'
                         + tsq_display + '</strong><p>After filtering</p></div></article>')
        if tvr is False and not mismatch_panels:
            cards = [card for card in cards if '<h3>TVR motifs</h3>' not in card]
        cards.insert(3, short_summary_html(barcode, run.settings))
        cutoff = short_cutoff_bp(run.settings, barcode)
        cutoff_attribute = f'{cutoff:g}' if cutoff is not None else ''
        key_heading = '<span class="number">1</span>Key Statistics (' + escape(label) + ')'
        pages.append(f'<div class="barcode-page" id="{barcode.id}" data-barcode-id="{escape(barcode.label, quote=True)}" data-short-cutoff-bp="{cutoff_attribute}" data-km-enabled="{str(km_enabled).lower()}" data-mismatch-enabled="{mismatch_attribute}" data-tvr-enabled="{tvr_attribute}" data-tsq-enabled="{str(tsq is True).lower()}" data-label="{escape(label, quote=True)}" data-chart-label="{escape(barcode.label.replace("barcode", "BC"), quote=True)}" hidden>'
            f'<nav class="breadcrumbs" aria-label="Breadcrumb"><a href="#/">All Barcodes</a> <span>› {escape(label)}</span></nav>'
            f'<section class="barcode-key-statistics"><h2>{key_heading}</h2><div class="stats barcode-stat-cards">{"".join(cards)}</div></section>'
            + ('<p class="note">One-mismatch analysis: repeat composition shows exported canonical and mismatch hits.</p>' if mismatch_panels else
               '<p class="note">TVR analysis was not requested: no TVR patterns were selected.</p>' if repeats_requested is False else
               '<p class="note">TVR counts use exported noncanonical matches overlapping TVR-inclusive telomere intervals of post-filtered reads. Missing details remain unavailable.</p>')
            + (results_section(barcode, results_root) if km_enabled else '') + histograms.get(barcode.id, '') + '<div class="charts">'
            + composition_section(repeat_row, title='Mismatch patterns' if mismatch_panels else variant_panel_title(run.settings),
                                  requested=True if mismatch_panels else repeats_requested, method=repeat_method)
            + positions_section(motifs, requested=repeats_requested, title=variant_panel_title(run.settings).replace(' patterns', ' Position Along Telomeres')) + '</div>'
            + chromosome_section([c for c in comparisons['cells'] if c['barcode'] == barcode.label], cutoff_bp=short_cutoff_bp(run.settings, barcode))
            + reads_section(barcode, results_root, show_completeness=km_enabled,summary_only=summary_only)
            + tsq_tandem_section(barcode, run.settings) + '</div>')
    navigation = '<nav class="barcode-navigation" aria-label="Choose a barcode"><strong>Explore a barcode</strong>' + ''.join(links) + '</nav>'
    return navigation, ''.join(pages)


def barcode_summary_section(run, comparisons):
    """Render the same Key Statistics as the barcode cards in a single table.

    Args:
        run: Imported run model containing barcodes, reads and source evidence.
        comparisons: Precomputed report comparisons; reused when supplied.

    Returns:
        HTML for the per-barcode Key Statistics table.
    """
    from ..shared.barcode_statistics import barcode_key_statistics, mismatch_statistics
    from ..shared.short_telomeres import short_table_summary_html
    composition={r['barcode']:r for r in comparisons['composition']}
    mismatch_mode = tvr_enabled(run.settings) is False and tsq_enabled(run.settings) is not True and mismatch_enabled(run.settings) is True
    mismatch_rows = {r['barcode']: r for r in comparisons.get('mismatch_composition', [])}
    headers = ['Barcode', 'Total number of reads', 'Number of telomeric reads after filtration',
               'Telomeric reads after filtration (%)',
               'Median telomere length after filtration (kb)',
               'Short telomeres (%)',
               *(['Mismatch patterns'] if mismatch_mode else ['TVR motifs'] if tvr_enabled(run.settings) is not False else []),
               *(['Reads containing TSQ after filtration'] if tsq_enabled(run.settings) is True else []),
               'Number of Chromosomes end found']
    cells = comparisons['cells']; rows = []
    for barcode in run.barcodes:
        stats = barcode_key_statistics(barcode, run.settings, cells, composition.get(barcode.label))
        motif_count = (mismatch_statistics(barcode, mismatch_rows.get(barcode.label))['mismatch_patterns']
                       if mismatch_mode else stats['tvr_motifs'])
        values = [stats['total_reads'], stats['post_filtered_reads'],
                  f"{100 * stats['post_filtered_reads'] / stats['total_reads']:.2f}%"
                  if stats['total_reads'] and stats['post_filtered_reads'] is not None
                  and stats['post_filtered_reads'] <= stats['total_reads'] else None,
                  f"{stats['median_length_bp']/1000:.2f}" if stats['median_length_bp'] is not None else None,
                  None,  # Replaced by the shared three-method short-telomere cell below.
                  *([motif_count] if mismatch_mode or tvr_enabled(run.settings) is not False else []),
                  *([tsq_read_count(barcode, run.settings)] if tsq_enabled(run.settings) is True else []),
                  stats['chromosomes']]
        row = '<tr><td><a class="barcode-stat-link" href="#/barcode/'+barcode.id+'"><span class="barcode-stat-dot" aria-hidden="true"></span><span class="barcode-stat-name">'+escape(barcode.label.replace('barcode', 'Barcode '))+'</span></a></td>'
        for index, value in enumerate(values, 1):
            if index == 5:
                row += '<td class="short-summary-cell">' + short_table_summary_html(barcode, run.settings) + '</td>'
            else:
                text = escape('Unavailable' if value is None else f'{value:,}' if isinstance(value, int) else str(value))
                row += '<td>'+text+'</td>'
        rows.append(row+'</tr>')
    heading = '<span class="number">1</span>Barcode summary'
    icon_paths = [
        '<path d="M3 5v14m4-14v14m3-14v14m4-14v14m3-14v14m4-14v14"/>',
        '<path d="M5 3h10l4 4v14H5zM14 3v6h5M8 12h8M8 16h6"/>',
        '<path d="M3 4h18l-7 8v9l-4-2v-7z"/>',
        '<path d="m3 16 13-13 5 5L8 21zM12 7l3 3M8 11l3 3"/>',
        '<circle cx="12" cy="12" r="9"/><path d="m8 16 8-8"/><circle cx="8" cy="8" r="1.2"/><circle cx="16" cy="16" r="1.2"/>',
        '<path d="M5 2c0 9 14 11 14 20M19 2C19 11 5 13 5 22M6 4h12M7 7h10M10 10h4M10 14h4M7 17h10M6 20h12"/>',
        '<path d="m12 3 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z"/>',
        '<path d="M7 3c-7 7 9 11 2 18M17 3c7 7-9 11-2 18M9 3c-4 7 8 11 4 18M15 3c4 7-8 11-4 18"/>',
    ]
    short_icon = '<path d="M3 10a9 9 0 0 1 15-6l3 3M21 2v5h-5M21 14a9 9 0 0 1-15 6l-3-3M3 22v-5h5"/><path d="M9 14v-3M12 14V8M15 14v-4"/>'
    header_cells = ''.join('<th'+(' class="short-summary-heading"' if title == 'Short telomeres (%)' else '')+'><span class="stat-column-heading"><svg viewBox="0 0 24 24" aria-hidden="true">'+(short_icon if title == 'Short telomeres (%)' else icon)+'</svg><span>'+escape(title)+'</span></span></th>' for title, icon in zip(headers, (icon_paths + icon_paths)[:len(headers)]))
    table = ('<section class="barcode-statistics-section"><div class="barcode-statistics-heading"><div><h2>'+heading+'</h2>'
             '</div></div>'
             '<div class="reads-scroll barcode-statistics-wrap"><table class="barcode-statistics-table"><thead><tr>'+header_cells+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div></section>')
    return table


# Fragment routing requires no server, fetch requests or external assets.
# Labels are read from escaped DOM attributes rather than interpolated into JS.
ROUTER = READ_SCRIPT + '<script>\n' + (
    Path(__file__).parents[1] / 'assets' / 'barcode_router.js'
).read_text(encoding='utf-8') + '\n</script>'
