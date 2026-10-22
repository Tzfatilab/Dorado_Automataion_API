"""Offline barcode navigation and summary cards; no new scientific calculations."""
from html import escape
from dorado_workflow.reports.overview.comparisons import comparison_data
from dorado_workflow.reports.barcode.composition import composition_section
from dorado_workflow.reports.barcode.positions import positions_section
from dorado_workflow.reports.barcode.chromosomes import chromosome_section
from dorado_workflow.reports.barcode.completeness import results_section
from dorado_workflow.reports.reads.browser import reads_section, READ_SCRIPT
from dorado_workflow.reports.reads.density import mismatch_enabled
from dorado_workflow.reports.shared.organism import show_km


def barcode_views(run, icons, histograms=None, results_root=None):
    """Render six cards per barcode from exported facts and existing aggregates.

    TVR counts require complete motif coverage of the post-filtered population.
    Chromosome counts use the same unambiguous assignments as the heatmap.
    Missing coverage remains unavailable, never zero or 100% canonical.
    """
    comparisons = comparison_data(run)
    km_enabled = show_km(run)
    mismatch = mismatch_enabled(run.settings)
    mismatch_attribute = 'unknown' if mismatch is None else str(mismatch).lower()
    histograms = histograms or {}
    composition = {row['barcode']: row for row in comparisons['composition']}
    pages, links = [], []
    for barcode in run.barcodes:
        label = barcode.label.replace('barcode', 'Barcode ')
        route = '#/barcode/' + barcode.id
        links.append(f'<a class="barcode-link" href="{route}">{escape(label)}</a>')
        def value(key):
            fact = barcode.metrics.get(key)
            return fact.value if fact and fact.status == 'available' else None
        total, telomeric = value('total_reads'), value('amount_of_telomeres')
        empty = telomeric == 0
        med = value('median_telomere_length')
        motifs = composition.get(barcode.label)
        chromosomes = {c['chromosome'] for c in comparisons['cells'] if c['barcode'] == barcode.label}
        percent = f'{100*telomeric/total:.1f}% of input reads' if total and telomeric is not None and telomeric <= total else 'Post-filtered reads'
        tvr_note = ('No post-filtered telomeric reads' if empty else
                    f"{100*motifs['with_tvr']/motifs['total']:.1f}% of post-filtered reads" if motifs else 'Complete motif exports required')
        specs = [
            ('Total reads', total, 'Input reads', icons[0]),
            ('Telomeric reads', telomeric, percent, icons[2]),
            ('Median length', med, 'Post-filtered reads', icons[4]),
            ('Reads with TVRs', 0 if empty else motifs['with_tvr'] if motifs else None, tvr_note,
             '<path d="M8 40V23M19 40V8M30 40V17M41 40V4"/>'),
            ('TVR motifs', 0 if empty else len(motifs['motifs']) if motifs else None,
             'Noncanonical motifs overlapping TVR-inclusive telomeres',
             '<circle cx="24" cy="10" r="6"/><circle cx="10" cy="36" r="6"/><circle cx="38" cy="36" r="6"/><path d="m21 16-8 14m14-14 8 14M16 36h16"/>'),
            ('Chromosomes', 0 if empty else len(chromosomes) if chromosomes else None,
             'Unambiguous mapped post-filtered reads', icons[5]),
        ]
        cards = []
        for index, (title, number, note, icon) in enumerate(specs):
            display = 'Unavailable' if number is None else f'{number/1000:,.2f} kb' if index == 2 else f'{number:,}'
            if empty and index == 2:
                display = 'No reads'
                note = 'No post-filtered telomeric reads'
            cards.append(f'<article class="stat stat-{index}"><svg aria-hidden="true" viewBox="0 0 48 48">{icon}</svg>'
                f'<div><h3>{title}</h3><strong class="{"missing" if number is None else ""}">{display}</strong><p>{escape(note)}</p></div></article>')
        pages.append(f'<div class="barcode-page" id="{barcode.id}" data-km-enabled="{str(km_enabled).lower()}" data-mismatch-enabled="{mismatch_attribute}" data-label="{escape(label, quote=True)}" data-chart-label="{escape(barcode.label.replace("barcode", "BC"), quote=True)}" hidden>'
            f'<nav class="breadcrumbs" aria-label="Breadcrumb"><a href="#/">All Barcodes</a> <span>› {escape(label)}</span></nav>'
            f'<section><h2><span class="number">1</span>Key Statistics ({escape(label)})</h2><div class="stats">{"".join(cards)}</div></section>'
            '<p class="note">TVR counts use exported noncanonical matches overlapping TVR-inclusive telomere intervals of post-filtered reads. Missing details remain unavailable.</p>'
            + (results_section(barcode, results_root) if km_enabled else '') + histograms.get(barcode.id, '') + '<div class="charts">' + composition_section(motifs)
            + positions_section(motifs) + '</div>'
            + chromosome_section([c for c in comparisons['cells'] if c['barcode'] == barcode.label])
            + reads_section(barcode, results_root, show_completeness=km_enabled) + '</div>')
    navigation = '<nav class="barcode-navigation" aria-label="Choose a barcode"><strong>Explore a barcode</strong>' + ''.join(links) + '</nav>'
    return navigation, ''.join(pages)


# Fragment routing requires no server, fetch requests or external assets.
# Labels are read from escaped DOM attributes rather than interpolated into JS.
ROUTER = READ_SCRIPT + """<script>
(() => {
  const overview = document.getElementById('run-overview');
  const pages = [...document.querySelectorAll('.barcode-page')];
  const title = document.querySelector('header h1');
  const missing = document.getElementById('unknown-barcode');
  function route() {
    const hash = location.hash || '#/';
    const page = pages.find(p => hash === '#/barcode/' + p.id);
    overview.hidden = hash !== '#/';
    pages.forEach(p => p.hidden = p !== page);
    const readVisible = window.showReadDetail(hash);
    // Saved barcode files belong to the overview/barcode pages, not a read.
    document.querySelectorAll('.saved-barcode-reports').forEach(el => el.hidden = readVisible);
    missing.hidden = hash === '#/' || !!page || readVisible;
    if (!readVisible) title.textContent = 'Telomere Analysis Summary - ' + (page ? page.dataset.label : 'All Barcodes');
    document.title = title.textContent;
    // Render the source-saved histogram only once its barcode is visible, so
    // Plotly measures the correct width. No bins or scientific values change.
    if (page) page.querySelectorAll('.saved-histogram').forEach(plot => {
      if (plot.dataset.started) { if (plot._fullLayout) Plotly.Plots.resize(plot); return; }
      plot.dataset.started = 'true';
      let figure;
      try { figure = JSON.parse(plot.nextElementSibling.textContent); }
      catch (_) { plot.textContent = 'Saved chart data is invalid.'; return; }
      // Display source serial numbers while keeping stable read IDs separately
      // for navigation. Do not infer identity from point rank or measured length.
      const readIndex = new Map();
      (window.reportReadRows ? window.reportReadRows(page.id) : []).forEach(read => {
        [read.header, read.header.split(/\s+/)[0]].forEach(key => {
          if (!readIndex.has(key)) readIndex.set(key, read);
          else if (readIndex.get(key)?.id !== read.id) readIndex.set(key, null);
        });
      });
      (figure.data || []).forEach(trace => {
        if (!Array.isArray(trace.text) || trace.meta === 'read-links') return;
        const links = [];
        let matched = false;
        trace.text = trace.text.map(text => {
          const match = /^Read: (.*?)<br>/.exec(text);
          const read = readIndex.get(match ? match[1] : text);
          links.push(read ? [page.id, read.id] : null);
          if (!read) return text;
          matched = true;
          return match ? read.label + text.slice(match[0].length - 4) : read.label;
        });
        // Smoothed/median curves represent statistics, not individual reads.
        if (matched && !/median|smoothed/i.test(trace.name || '')) {
          trace.meta = 'read-links';
          trace.customdata = links;
        }
      });
      // Move only the existing count/percentage menu into the section header.
      // Its saved update arguments supply every value: no binning or conversion.
      const menu = (figure.layout.updatemenus || []).find(m =>
        m.buttons && ['Read count', 'Percentage'].every(label =>
          m.buttons.some(b => b.label === label && b.method === 'update')));
      const controls = plot.closest('section').querySelector('.histogram-controls');
      if (menu && controls) menu.visible = false;
      Plotly.newPlot(plot, figure.data, figure.layout, {...figure.config, responsive:true})
        .then(() => {
          plot.on('plotly_click', event => {
            const point = event.points[0];
            // Saved NanoTel traces retain read identities in hover text. Resolve
            // against this barcode's actual read pages, never rank or length alone.
            const payload = page.querySelector('.read-data');
            const reads = window.reportReadRows ? window.reportReadRows(page.id) : (payload ? (JSON.parse(payload.textContent) || []) : []);
            const goRead = read => { location.hash = '#/barcode/' + page.id + '/read/' + read.id; };
            const resolve = identity => {
              const matches = reads.filter(r => r.header === identity || r.header.split(/\s+/)[0] === identity);
              return matches.length === 1 ? matches[0] : null;
            };
            if (point && point.data.meta !== 'read-links' && !/median|smoothed/i.test(point.data.name || '')) {
              const text = typeof point.text === 'string' ? point.text : '';
              const match = /^Read: (.*?)<br>/.exec(text);
              const read = resolve(match ? match[1] : text);
              if (read) { goRead(read); return; }
            }
            if (point && point.data.meta === 'read-links' && point.customdata) {
              location.hash = '#/barcode/' + point.customdata[0] + '/read/' + point.customdata[1];
            }
          });
          if (!menu || !controls) return;
          menu.buttons.forEach((saved, index) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = saved.label;
            button.setAttribute('aria-pressed', String(index === (menu.active ?? 0)));
            button.addEventListener('click', () => {
              Plotly.update(plot, ...saved.args).then(() => {
                controls.querySelectorAll('button').forEach(b =>
                  b.setAttribute('aria-pressed', String(b === button)));
              });
            });
            controls.appendChild(button);
          });
        })
        .catch(() => { delete plot.dataset.started; plot.textContent = 'This chart could not be displayed. Return to this barcode to retry.'; });
    });
    if (!overview.hidden) overview.querySelectorAll('.js-plotly-plot').forEach(p => Plotly.Plots.resize(p));
    window.scrollTo(0, 0);
  }
  document.querySelectorAll('.js-plotly-plot').forEach(plot => {
    plot.on('plotly_click', event => {
      const point = event.points[0];
      if (!point) return;
      // Box-summary clicks have no individual observation index. Only a dot
      // with a joined source read may navigate to the read dashboard.
      if (point.data.type === 'box' && Number.isInteger(point.pointNumber)) {
        const identity = (point.data.customdata || [])[point.pointNumber];
        if (identity && identity[1]) {
          location.hash = '#/barcode/' + identity[0] + '/read/' + identity[1];
          return;
        }
      }
      const label = point.data.type === 'heatmap' ? point.y : point.data.type === 'box' ? point.data.name : point.x;
      const page = pages.find(p => p.dataset.chartLabel === label);
      if (page) location.hash = '#/barcode/' + page.id;
    });
  });
  window.addEventListener('hashchange', route);
  route();
})();
</script>"""
