(() => {
  const overview = document.getElementById('run-overview');
  const pages = [...document.querySelectorAll('.barcode-page')];
  const title = document.querySelector('header h1');
  const missing = document.getElementById('unknown-barcode');
  // Function: route.
  // Inputs: None; uses the current report/browser state.
  // Outputs: Shows the page selected by the URL hash and lazily renders its figures.
  function route() {
    let hash = location.hash || '#/';
    // Summary reports have barcode tables but no individual-read screens.
    const summaryRead=document.body.dataset.summaryOnly==='true'&&/^#\/barcode\/([^/]+)\/read\/([^/]+)$/.exec(hash);
    if(summaryRead){hash='#/barcode/'+summaryRead[1];history.replaceState(null,'',hash);}

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
            // Function: goRead.
            // Inputs: read (embedded read record)
            // Outputs: Navigates to the selected read using stable barcode and read identities.
            const goRead = read => { location.hash = '#/barcode/' + page.id + '/read/' + read.id; };
            // Function: resolve.
            // Inputs: identity (source read identity)
            // Outputs: Resolved stable identity, or no match when the source is ambiguous.
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
    if(summaryRead)window.findSummaryRead?.(summaryRead[1],summaryRead[2]);else window.scrollTo(0, 0);
  }
  document.querySelectorAll('.js-plotly-plot').forEach(plot => {
    plot.on('plotly_click', event => {
      const point = event.points[0];
      if (!point) return;
      if(point.data.meta==='barcode-links'){
        const id=point.customdata??point.data.customdata?.[point.pointNumber];
        if(pages.some(page=>page.id===id))location.hash='#/barcode/'+id;
        return;
      }
      // Box-summary clicks have no individual observation index. Only a dot
      // with a joined source read may navigate to the read dashboard.
      if (['box','violin','scatter'].includes(point.data.type) && Number.isInteger(point.pointNumber)) {
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
  overview.addEventListener('click',event=>{
    const tick=event.target.closest?.('.xtick');
    const plot=tick?.closest('.js-plotly-plot');
    const trace=plot?.data?.find(trace=>trace.meta==='barcode-links');
    if(!trace)return;
    const label=tick.textContent.trim();
    const index=trace.x.findIndex(value=>String(value)===label);
    const id=trace.customdata?.[index];
    if(pages.some(page=>page.id===id))location.hash='#/barcode/'+id;
  });
  window.addEventListener('hashchange', route);
  route();
})();
