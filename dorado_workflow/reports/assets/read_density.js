/* Read density presentation. Source calls and exported samples are not recomputed. */
window.readMappingSummary = (read, data) => {
  const escape = value => String(value).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
  const alignments = (data.alignments || []).filter(a => a.reference && a.reference !== '*');
  const descriptions = alignments.map(a => {
    const interval = a.normalized || a.raw;
    const start = a.normalized ? a.normalized.start + 1 : interval?.start;
    const end = interval?.end;
    const coordinates = start != null && end != null
      ? ' | reference: ' + escape(start) + '–' + escape(end) + ' bp' : '';
    return escape(a.reference) + coordinates + (a.strand ? ' | strand: ' + escape(a.strand) : '');
  });
  const spans = alignments.filter(a => {
    const q = a.query_interval;
    return q?.space === 'nanotel_analyzed_read' && q.convention === 'zero_based_half_open' &&
      Number.isInteger(q.start) && Number.isInteger(q.end) && q.start >= 0 && q.end > q.start && q.end <= read.length;
  });
  const assigned = descriptions.length ? descriptions.join('<br>') :
    (read.chromosomes || []).length ? 'Assigned: ' + read.chromosomes.map(escape).join(', ') : 'No chromosome assignment exported';
  return {spans, text: assigned + (spans.length ? '' : '<br>Aligned span within read not exported')};
};

window.renderReadTracks = (parent, read, options = {}) => {
  const add = (tag, text, target) => {
    const element = document.createElement(tag);
    element.textContent = text;
    target.appendChild(element);
    return element;
  };
  const saved = document.getElementById('read-tracks-' + read.id);
  let data = read.track_data;
  if (!data && saved) {
    try { data = JSON.parse(saved.textContent); } catch (_) { data = null; }
  }
  const panel = add('section', '', parent);
  panel.className = 'read-density-panel';
  add('h3', 'Telomeric repeat density', panel);
  if (!data || !read.length || !window.Plotly) {
    add('p', 'Detailed read tracks are unavailable.', panel).className = 'note';
    return;
  }
  const chart = add('div', '', panel);
  chart.reportInteractiveRead={...read,track_data:data};
  chart.className = 'read-density-chart';
  const traces = [], shapes = [], annotations = [];
  const extent = read.length / 1000;
  const exact = data.intervals.exact, inclusive = data.intervals.tvr_inclusive;
  // Configured motifs with no exported hits do not belong in this read's legend.
  const motifs = (data.motifs || []).filter(m => Array.isArray(m.positions) && m.positions.length > 0).sort((a, b) =>
    Number(a.role !== 'canonical') - Number(b.role !== 'canonical') || a.label.localeCompare(b.label));
  const canonicalName = motifs.filter(m => m.role === 'canonical').map(m => m.label.replace(' (canonical)', '')).join(', ');

  // Area layers retain the original exact, mismatch and TVR-inclusive series.
  // TVR-inclusive density is not a TVR-only density: overlaps forbid subtraction.
  const series = [
    ['tvr_inclusive', 'Density + TVR', '#b88719', 'rgba(245,199,64,0.19)'],
    ['exact', 'Telomere density' + (canonicalName ? ' (' + canonicalName + ')' : ''), '#dc413b', 'rgba(234,99,98,0.20)'],
    ['mismatch', 'Density with mismatches', '#8962b3', null]
  ];
  series.forEach(([method, name, color, fill]) => {
    // NanoTel can export exact values under the mismatch name when disabled.
    // Require explicit run-setting evidence, including for the legend entry.
    if (method === 'mismatch' && options.mismatchEnabled !== true) return;
    const samples = (data.density || {})[method];
    if (!samples || !samples.length) return;
    const x = samples.map(s => (s[0] + 1) / 1000), y = samples.map(s => s[2]);
    // NanoTel extends the last observed density to the end of the read.
    if (x[x.length - 1] < extent) { x.push(extent); y.push(y[y.length - 1]); }
    traces.push({type: 'scatter', mode: 'lines', name, x, y,
      line: {color, width: method === 'exact' ? 2.2 : 1.4},
      fill: fill ? 'tozeroy' : 'none', fillcolor: fill || undefined,
      visible: method === 'mismatch' ? 'legendonly' : true,
      hovertemplate: 'Position: %{x:.3f} kb<br>Density: %{y:.3f}<extra>%{fullData.name}</extra>'});
  });
  const shade = (start, end, color) => {
    if (end > start) shapes.push({type: 'rect', xref: 'x', yref: 'y',
      x0: start / 1000, x1: end / 1000, y0: 0, y1: 1, layer: 'below',
      line: {width: 0}, fillcolor: color});
  };
  if (exact) shade(exact[0], exact[1], 'rgba(238,136,140,0.10)');
  if (inclusive && exact) {
    shade(inclusive[0], Math.min(exact[0], inclusive[1]), 'rgba(251,213,88,0.22)');
    shade(Math.max(exact[1], inclusive[0]), inclusive[1], 'rgba(251,213,88,0.22)');
  }
  // NanoTel labels sequence outside the called interval as sub-telomere.
  // This is a source-call context, not a genomic mapping inference.
  const called = inclusive || exact;
  if (called) {
    const x = [], y = [];
    [[0, called[0]], [called[1], read.length]].forEach(([start, end]) => {
      if (end > start) { x.push(start / 1000, end / 1000, null); y.push(0, 0, null); }
    });
    traces.push({type: 'scatter', mode: 'lines', name: 'Sub-telomere (NanoTel)', x, y,
      line: {color: '#4267ca', width: 4}, hovertemplate: 'Outside called telomere<br>%{x:.3f} kb<extra></extra>'});
    shapes.push({type: 'line', xref: 'x', yref: 'y', x0: called[1] / 1000,
      x1: called[1] / 1000, y0: 0, y1: 1.05, line: {color: '#243750', width: 1.5, dash: 'dash'}});
    annotations.push({xref: 'x', yref: 'y', x: called[1] / 1000, y: 1.06,
      text: 'Telomere end' + (inclusive ? ' (including TVRs)' : ' (exact)') + '<br>' + (called[1] / 1000).toFixed(3) + ' kb',
      showarrow: false, xanchor: called[1] > read.length * 0.75 ? 'right' : 'left',
      xshift: called[1] > read.length * 0.75 ? -8 : 8, yanchor: 'bottom', font: {size: 12, color: '#243750'}});
    if (exact && inclusive && exact[1] !== inclusive[1]) {
      shapes.push({type: 'line', xref: 'x', yref: 'y', x0: exact[1] / 1000,
        x1: exact[1] / 1000, y0: 0, y1: 1, line: {color: '#dc413b', width: 1, dash: 'dot'}});
    }
  }

  // Compact shared lanes match the reference layout. Canonical intervals are
  // drawn first; overlapping variants remain available through legend toggles.
  function intervalTrace(motif, positions, lane, showlegend) {
    return {type: 'bar', orientation: 'h', xaxis: 'x2', yaxis: 'y2',
      name: motif.label, legendgroup: motif.label, legend: 'legend2', showlegend,
      base: positions.map(p => p[0] / 1000), x: positions.map(p => (p[1] - p[0]) / 1000),
      y: positions.map(() => lane), width: 0.56,
      marker: {color: motif.color, line: {width: 0}},
      customdata: positions.map(p => [p[0] + 1, p[1]]),
      hovertemplate: '%{fullData.name}<br>%{customdata[0]:,}–%{customdata[1]:,} bp<extra></extra>'};
  }
  // Unassigned means no exported motif hit within the TVR-inclusive interval,
  // using the same denominator as the composition chart, not missing exports.
  if (inclusive && Array.isArray(data.motifs)) {
    const spans=motifs.flatMap(m=>m.positions).map(([a,b])=>[Math.max(a,inclusive[0]),Math.min(b,inclusive[1])])
      .filter(([a,b])=>b>a).sort((a,b)=>a[0]-b[0]||a[1]-b[1]);
    const gaps=[];let cursor=inclusive[0];
    spans.forEach(([a,b])=>{if(a>cursor)gaps.push([cursor,a]);cursor=Math.max(cursor,b);});
    if(cursor<inclusive[1])gaps.push([cursor,inclusive[1]]);
    if(gaps.length)traces.push(intervalTrace({label:'Unassigned bases',color:'#b5bdc7'},gaps,2,true));
  }
  motifs.forEach(m => {
    traces.push(intervalTrace(m, m.positions, 2, true));
  });
  [[2, 'Motif type'], [1, 'Sequence'], [0, 'Mapping to genome']].forEach(([y, text]) =>
    annotations.push({xref: 'paper', yref: 'y2', x: 0, y, text, showarrow: false,
      xanchor: 'right', xshift: -12, font: {size: 12, color: '#243750'}}));
  const mapping = window.readMappingSummary(read, data);
  const mappingPixels = Math.max(100, parent.clientWidth - (parent.clientWidth < 850 ? 155 : 400));
  if (mapping.spans.length) {
    traces.push({type:'scatter',mode:'lines',xaxis:'x2',yaxis:'y2',
      x:[0,extent,extent,0,0],y:[-.6,-.6,.6,.6,-.6],
      fill:'toself',fillcolor:'#e0e5ed',line:{width:0},showlegend:false,
      hoverinfo:'skip',name:'Outside mapped region'});
    let covered = 0;
    const gapLabel = (start,end) => {
      if ((end-start)/extent*mappingPixels > 170) annotations.push({xref:'x2',yref:'y2',
        x:(start+end)/2,y:0,text:'Outside mapped region',showarrow:false,font:{size:14,color:'#64748b'}});
    };
    [...mapping.spans].sort((a,b)=>a.query_interval.start-b.query_interval.start).forEach(a=>{
      const start=a.query_interval.start/1000,end=a.query_interval.end/1000;
      gapLabel(covered,start); covered=Math.max(covered,end);
    });
    gapLabel(covered,extent);
  }
  mapping.spans.forEach(alignment => {
    const q = alignment.query_interval;
    const reference = String(alignment.reference).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
    const start = q.start / 1000, end = q.end / 1000;
    traces.push({type:'scatter', mode:'lines', xaxis:'x2', yaxis:'y2',
      x:[start,end,end,start,start], y:[-.6,-.6,.6,.6,-.6],
      fill:'toself', fillcolor:'#276bd1',
      line:{color:'#276bd1',width:0}, hoverinfo:'skip',
      showlegend:false, name:'Aligned read span'});
    const strand = alignment.query_strand;
    const mapq = Number.isFinite(alignment.mapq) && alignment.mapq >= 0 && alignment.mapq < 255
      ? ' | MAPQ '+alignment.mapq : '';
    const label = reference + (strand === '+' || strand === '-'
      ? ' | strand '+(strand === '-' ? '−' : '+') : '') + mapq +
      (strand === '+' ? ' →' : strand === '-' ? ' ←' : '');
    const availablePixels=(end-start)/extent*mappingPixels;
    const strandLabel=strand === '+' || strand === '-'
      ? 'strand '+(strand === '-' ? '− ←' : '+ →') : '';
    const wrappedLabel=reference+mapq+(strandLabel ? '<br>'+strandLabel : '');
    const visibleLabel=availablePixels > label.length*8+12 ? label : wrappedLabel;
    annotations.push({xref:'x2',yref:'y2',x:(start+end)/2,y:0,
      text:visibleLabel,showarrow:false,font:{size:14,color:'#ffffff'}});
    // Put endpoint coordinates below the track, keeping labels inside the frame.
    const coordinateLabel=(position,anchor)=>annotations.push({xref:'x2',yref:'y2',
      x:position,y:-.72,yanchor:'top',xanchor:anchor,
      text:position.toFixed(2)+' kb',showarrow:false,font:{size:12,color:'#243750'}});
    if (availablePixels > 120) { coordinateLabel(start,'left'); coordinateLabel(end,'right'); }
    else annotations.push({xref:'x2',yref:'y2',x:(start+end)/2,y:-.72,yanchor:'top',
      xanchor:start > extent*.75 ? 'right' : 'left',text:start.toFixed(2)+'–'+end.toFixed(2)+' kb',
      showarrow:false,font:{size:12,color:'#243750'}});
  });
  if (!mapping.spans.length) annotations.push({xref: 'x2', yref: 'y2', x: extent / 2, y: 0, text: mapping.text,
    showarrow: false, font: {size: 12, color: '#738292'}});
  if (!(data.density || {}).exact?.length && !(data.density || {}).tvr_inclusive?.length) {
    annotations.push({xref: 'paper', yref: 'y', x: 0.5, y: 0.5,
      text: 'Density samples unavailable', showarrow: false});
  }
  if (!motifs.length) annotations.push({xref: 'x2', yref: 'y2', x: extent / 2, y: 2,
    text: data.motifs === null ? 'Motif positions unavailable' : 'No exported motif matches', showarrow: false});
  const narrow = parent.clientWidth < 850;
  const height = narrow ? 820 : 580;
  // Plotly's inner container uses height:100%; give it a definite parent height
  // to prevent a large empty area beneath the SVG in the reusable read shell.
  chart.style.height = height + 'px';
  const sequence = typeof data.sequence === 'string' && data.sequence.length === read.length ? data.sequence : null;
  if (!sequence) annotations.push({xref:'x2', yref:'y2', x:extent/2, y:1,
    text:'Sequence unavailable (matching analyzed FASTA required)', showarrow:false,
    font:{size:12,color:'#738292'}});
  let updateSelection = () => {};
  if (sequence) {
    const controls=add('div','',panel);controls.className='read-sequence-controls';
    const scopeLabel=add('label','Sequence: ',controls),scope=add('select','',scopeLabel);
    [['whole','Whole read'],['region','Selected region']].forEach(([value,label])=>{const option=add('option',label,scope);option.value=value;});
    const startLabel=add('label','Start (bp) ',controls),startInput=add('input','',startLabel);
    const endLabel=add('label','End (bp) ',controls),endInput=add('input','',endLabel);
    [startInput,endInput].forEach(input=>{input.type='number';input.min=1;input.max=sequence.length;input.step=1;});
    startInput.value=1;endInput.value=sequence.length;
    const zoomButton=add('button','Zoom to region',controls);zoomButton.type='button';
    const copy=add('button','Copy sequence',controls);copy.type='button';
    const download=add('button','Download FASTA',controls);download.type='button';
    const message=add('span','',controls);message.setAttribute('role','status');
    const selection=()=>{
      const start=scope.value==='whole'?1:Number(startInput.value),end=scope.value==='whole'?sequence.length:Number(endInput.value);
      if (!Number.isInteger(start)||!Number.isInteger(end)||start<1||end<start||end>sequence.length) {
        message.textContent='Enter valid 1-based coordinates within this read.';return null;
      }
      return {start,end,text:sequence.slice(start-1,end)};
    };
    [startInput,endInput].forEach(input=>input.addEventListener('input',()=>{scope.value='region';message.textContent='';}));
    scope.onchange=()=>{message.textContent='';};
    zoomButton.onclick=()=>{scope.value='region';const selected=selection();if(selected&&chart._fullLayout)Plotly.relayout(chart,{'xaxis2.range':[(selected.start-1)/1000,selected.end/1000]});};
    copy.onclick=async()=>{
      const selected=selection();if(!selected)return;
      try {
        if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
        await navigator.clipboard.writeText(selected.text);
        message.textContent='Copied '+selected.text.length.toLocaleString()+' bases ('+selected.start+' - '+selected.end+' bp).';
      } catch (_) {
        let manual=panel.querySelector('.read-sequence-copy');
        if(!manual){manual=add('textarea','',panel);manual.className='read-sequence-copy';manual.readOnly=true;manual.setAttribute('aria-label','Selected sequence for manual copying');}
        manual.value=selected.text;manual.focus();manual.select();
        message.textContent='Automatic copy unavailable. Press Ctrl+C to copy the selected sequence.';
      }
    };
    download.onclick=()=>{
      const selected=selection();if(!selected)return;
      const header=(read.header||read.id).replace(/[\r\n]/g,' ')+' | '+read.label+' | analyzed_orientation | '+selected.start+'-'+selected.end+' bp';
      const wrapped=selected.text.match(/.{1,80}/g).join('\n');
      const url=URL.createObjectURL(new Blob(['>'+header+'\n'+wrapped+'\n'],{type:'text/plain'}));
      const link=add('a','',controls);link.href=url;
      link.download=(read.label||read.id).replace(/[^a-zA-Z0-9_-]/g,'_')+'_'+selected.start+'-'+selected.end+'.fasta';link.click();link.remove();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
      message.textContent='Downloaded '+selected.text.length.toLocaleString()+' bases.';
    };
    updateSelection=event=>{
      if(!event || !Object.keys(event).some(key=>/^xaxis2?\.(range|autorange)/.test(key)))return;
      const range=chart._fullLayout?.xaxis2?.range;if(!range)return;
      const lo=Math.min(...range),hi=Math.max(...range);
      startInput.value=Math.max(1,Math.min(sequence.length,Math.floor(lo*1000+1e-7)+1));
      endInput.value=Math.max(Number(startInput.value),Math.min(sequence.length,Math.ceil(hi*1000-1e-7)));
      scope.value=Number(startInput.value)===1&&Number(endInput.value)===sequence.length?'whole':'region';
      message.textContent='';
    };
  }
  Plotly.newPlot(chart, traces, {
    template: 'plotly_white', height, barmode: 'overlay',
    margin: {l: 130, r: narrow ? 25 : 270, t: 55, b: narrow ? 220 : 55},
    font: {family: 'Segoe UI, Arial', color: '#14263c'},
    xaxis: {domain: [0, 1], range: [0, extent], anchor: 'y', showticklabels: false, matches: 'x2'},
    yaxis: {domain: [0.4, 1], range: [-0.035, 1.18], title: {text: 'Density'}, dtick: 0.2},
    xaxis2: {domain: [0, 1], range: [0, extent], anchor: 'y2', title: {text: 'Position (kb)'}, zeroline: false},
    yaxis2: {domain: [0, 0.32], range: [-1.5, 2.5], showticklabels: false, showgrid: false, zeroline: false, fixedrange: true},
    legend: narrow ? {orientation: 'h', x: 0, y: -0.18, font: {size: 11}} :
      {x: 1.02, y: 1, font: {size: 12}, bgcolor: 'rgba(255,255,255,0.9)'},
    // Keep motif colors next to the motif strip, separate from density curves.
    legend2: narrow ? {orientation: 'h', x: 0, y: -0.42, font: {size: 11}} :
      {x: 1.02, y: 0.24, yanchor: 'top', maxheight: 0.3,
        font: {size: 12}, bgcolor: 'rgba(255,255,255,0.9)'},
    shapes, annotations
  }, {responsive: true, displaylogo: false}).then(() => {
    if (!sequence) return;
    chart.on('plotly_relayout', updateSelection);
    // Canvas avoids creating thousands of DOM nodes or extra per-base JSON.
    // Both zoom and resize use Plotly's current shared position axis.
    const canvas = add('canvas', '', chart);
    canvas.className = 'read-sequence-canvas';
    canvas.setAttribute('aria-label', 'Analyzed read sequence; zoom in to see nucleotide letters');
    chart.style.position = 'relative';
    Object.assign(canvas.style, {position:'absolute', pointerEvents:'none', zIndex:'2'});
    const colors = {A:'#35a56f', C:'#387bd4', G:'#c89820', T:'#d85365'};
    const paintSequence = (target, scale, layout = chart._fullLayout) => {
      if (!chart.isConnected || !chart._fullLayout) return;
      const x = layout.xaxis2, y = layout.yaxis2;
      const width = Math.max(1, Math.round(x._length)), height = 23;
      target.width = Math.ceil(width * scale); target.height = Math.ceil(height * scale);
      Object.assign(target.style, {left:x._offset+'px', top:(y._offset+y.l2p(1)-height/2)+'px',
        width:width+'px', height:height+'px'});
      const ctx = target.getContext('2d');ctx.scale(scale,scale);
      const lo = Math.max(0, Math.floor(Math.min(...x.range)*1000));
      const hi = Math.min(sequence.length, Math.ceil(Math.max(...x.range)*1000));
      const baseWidth = Math.abs(x.l2p(.001)-x.l2p(0));
      ctx.font = 'bold 14px monospace';ctx.textAlign='center';ctx.textBaseline='middle';
      for (let i=lo; i<hi; i++) {
        const left=x.l2p(i/1000), right=x.l2p((i+1)/1000);
        ctx.fillStyle=colors[sequence[i]] || '#929baa';
        ctx.fillRect(Math.min(left,right),0,Math.max(1,Math.abs(right-left)),height);
        if (baseWidth >= 10) {ctx.fillStyle='#fff';ctx.fillText(sequence[i],(left+right)/2,height/2);}
      }
      return {x:x._offset,y:y._offset+y.l2p(1)-height/2,width,height};
    };
    const drawSequence = () => paintSequence(canvas, window.devicePixelRatio || 1);
    chart.reportExportOverlay = (scale, layout) => {
      const exported=document.createElement('canvas');
      const bounds=paintSequence(exported,scale,layout);
      return bounds ? {...bounds,href:exported.toDataURL('image/png')} : null;
    };
    chart.on('plotly_afterplot', drawSequence);
    chart.on('plotly_relayout', drawSequence);
    drawSequence();
  }).catch(() => {
    chart.textContent = 'The exported density graph could not be displayed.';
  });
  if (sequence) add('p', 'Sequence: analyzed NanoTel orientation. Zoom in to see A, C, G and T letters (green, blue, gold and red); ambiguous bases are gray.', panel).className = 'note';
  add('p', 'NanoTel-exported window densities and call boundaries; no new detection. Density + TVR includes canonical and variant matches. Motif colors can overlap; toggle the legend to inspect them. Unmarked bases are not classified as genomic sequence.', panel).className = 'note';
};
