(() => {
  const overview = document.getElementById('run-overview');
  const pages = [...document.querySelectorAll('.barcode-page')];
  const title = document.querySelector('header h1');
  const missing = document.getElementById('unknown-barcode');
  // Standard populations reuse saved NanoTel figures. Table subsets display
  // source measurements directly; they never rerun telomere detection/filtering.
  function tableLengthFigure(page, section, selected, rows) {
    const method=page.dataset.mismatchEnabled==='true'?'mismatch_length':'exact_length';
    const numeric=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0;
    const layout=JSON.parse(JSON.stringify(selected.figure.layout));
    delete layout.updatemenus;delete layout.xaxis.range;delete layout.yaxis.range;
    layout.xaxis.autorange=true;layout.yaxis.autorange=true;
    layout.annotations=[];
    const label=method==='mismatch_length'?'including mismatch':'canonical';
    let note=`Table filters: ${rows.length.toLocaleString()} matching reads. Telomere lengths: ${label}. `;
    let data;
    if(section.dataset.lengthPopulationChart==='histogram') {
      const lengths=rows.map(r=>r[method]).filter(v=>numeric(v)&&v>0);
      data=[{type:'histogram',x:lengths,name:'Telomeric reads',marker:{color:'#dbe7f6'},histnorm:'',nbinsx:50}];
      layout.yaxis.title={text:'Read count'};
      layout.updatemenus=[{buttons:[
        {label:'Read count',args:[{histnorm:''},{'yaxis.title.text':'Read count'}]},
        {label:'Percentage',args:[{histnorm:'percent'},{'yaxis.title.text':'Percentage (%)'}]}
      ]}];
      note+=`${lengths.length} measured of ${rows.length} reads; missing or non-positive lengths omitted. Histogram of matching reads; original NanoTel smoothing is not recalculated for table filters.`;
    } else {
      const ordered=rows.slice().sort((a,b)=>(numeric(b.length)?b.length:0)-(numeric(a.length)?a.length:0));
      const x=ordered.map((_,i)=>i+1);
      data=[['length','Total read length','#e8735a'],[method,`Telomere length (${label})`,'#228b22']].map(([key,name,color])=>({
        type:'scatter',x,y:ordered.map(r=>numeric(r[key])?r[key]/1000:null),mode:'lines+markers',
        name,line:{color},marker:{size:4},meta:'read-links',customdata:ordered.map(r=>[page.id,r.id]),
        text:ordered.map(r=>r.label),hovertemplate:`%{text}<br>${name}: %{y:.3f} kb<extra></extra>`
      }));
      // Two heaps keep the cumulative median fast even for large selections.
      const low=[],high=[];
      const push=(heap,value,less)=>{heap.push(value);let i=heap.length-1;while(i){const p=(i-1)>>1;if(!less(heap[i],heap[p]))break;[heap[i],heap[p]]=[heap[p],heap[i]];i=p;}};
      const pop=(heap,less)=>{const top=heap[0],last=heap.pop();if(heap.length){heap[0]=last;let i=0;while(2*i+1<heap.length){let c=2*i+1;if(c+1<heap.length&&less(heap[c+1],heap[c]))c++;if(!less(heap[c],heap[i]))break;[heap[i],heap[c]]=[heap[c],heap[i]];i=c;}}return top;};
      const greater=(a,b)=>a>b,less=(a,b)=>a<b;
      const median=ordered.map(r=>{
        if(!numeric(r[method]))return null;
        const v=r[method]/1000;
        if(!low.length||v<=low[0])push(low,v,greater);else push(high,v,less);
        if(low.length>high.length+1)push(high,pop(low,greater),less);
        if(high.length>low.length)push(low,pop(high,less),greater);
        return low.length===high.length?(low[0]+high[0])/2:low[0];
      });
      data.push({type:'scatter',x,y:median,mode:'lines',name:'Running median telomere length',line:{color:'#4169e1',width:2.5},hovertemplate:'Running median telomere length: %{y:.3f} kb<extra></extra>'});
      note+='Sorted by total read length. Running median uses measured telomere lengths in this order; missing values are excluded. Summary cards remain after filtering.';
    }
    if(!rows.length)layout.annotations=[{text:'No reads match these table filters',x:.5,y:.5,xref:'paper',yref:'paper',showarrow:false}];
    return {figure:{data,layout},note};
  }
  function updateLengthPlot(plot, page) {
    plot.populationRender = (plot.populationRender || Promise.resolve()).then(async () => {
      const population = page.dataset.lengthPopulation || 'filtered';
      const selection=page.readLengthSelection;
      const renderKey=population+(selection?':'+selection.key:'')+':cutoff:'+page.dataset.shortCutoffBp;
      if (plot.dataset.population === renderKey && plot._fullLayout) {
        if (!page.hidden) Plotly.Plots.resize(plot);
        return;
      }
      const section = plot.closest('[data-length-population-chart]');
      const variants = JSON.parse(section.querySelector('.length-population-figures').textContent);
      let selected = variants[population];
      if(selection&&selected?.figure)selected=tableLengthFigure(page,section,selected,selection.rows);
      const figure = selected?.figure || {data:[], layout:{}};
      // Clone because Plotly mutates arrays and layout metadata during rendering.
      const copy = JSON.parse(JSON.stringify(figure));
      window.reportShortCutoff?.transform(copy, page, section.dataset.lengthPopulationChart);
      const controls = section.querySelector('.histogram-controls');
      const oldUnit = controls.querySelector('button[aria-pressed="true"]')?.textContent || 'Read count';
      controls.replaceChildren();
      const menu = (copy.layout.updatemenus || []).find(m => m.buttons?.some(b => b.label === 'Read count'));
      if (menu) menu.visible = false;
      if (plot._fullLayout) await Plotly.react(plot, copy.data, copy.layout, {...copy.config, responsive:true});
      else {
        await Plotly.newPlot(plot, copy.data, copy.layout, {...copy.config, responsive:true});
        plot.on('plotly_click', event => {
          const point = event.points[0];
          if (document.body.dataset.summaryOnly !== 'true' && point?.data.meta === 'read-links' && point.customdata?.[1])
            location.hash = '#/barcode/' + point.customdata[0] + '/read/' + point.customdata[1];
        });
      }
      if (menu) {
        for (const saved of menu.buttons) {
          const button = document.createElement('button');
          button.type = 'button'; button.textContent = saved.label;
          button.setAttribute('aria-pressed', String(saved.label === oldUnit));
          button.onclick = () => Plotly.update(plot, ...saved.args).then(() => {
            controls.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
          });
          controls.appendChild(button);
        }
        const active = menu.buttons.find(b => b.label === oldUnit);
        if (active) await Plotly.update(plot, ...active.args);
      }
      section.querySelector(':scope > p.note').textContent = selected?.note || 'Selected population is unavailable.';
      // The live graph is also the PNG/interactive export source.
      plot.dataset.population = renderKey;
    }).catch(() => {
      delete plot.dataset.population;
      plot.closest('section').querySelector(':scope > p.note').textContent = 'This population could not be displayed. Select it again to retry.';
    });
  }
  document.addEventListener('short-cutoff-change', event => {
    for(const page of pages)if(!page.hidden)page.querySelectorAll('[data-length-population-chart] .saved-histogram').forEach(plot=>{
      updateLengthPlot(plot,page);event.detail?.waitUntil(plot.populationRender);
    });
  });
  document.addEventListener('read-population-change', event => {
    const page = event.target.closest('.barcode-page');
    if (page && !page.hidden) page.querySelectorAll('[data-length-population-chart] .saved-histogram').forEach(plot => updateLengthPlot(plot, page));
  });
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
    document.title = title.textContent + (document.body.dataset.runLabel ? ' | ' + document.body.dataset.runLabel : '');
    // Render the source-saved histogram only once its barcode is visible, so
    // Plotly measures the correct width. No bins or scientific values change.
    if (page) page.querySelectorAll('.saved-histogram').forEach(plot => {
      if (plot.closest('[data-length-population-chart]')) { updateLengthPlot(plot, page); return; }
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
      window.reportShortCutoff?.transform(figure, page);
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
