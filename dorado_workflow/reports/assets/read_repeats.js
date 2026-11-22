/* Presentation aggregates of exported hits; no repeat search or new calling. */
// Function: window.readRepeatSummary.
// Inputs: data (source/presentation data)
// Outputs: Base composition and merged region summaries, or null without a usable interval.
window.readRepeatSummary = data => {
  data = window.reportObservedMotifs?.(data) || data;
  const interval = data?.intervals?.tvr_inclusive;
  if (!interval || !Array.isArray(data.motifs)) return null;
  const [start, end] = interval, groups = [], events = new Map();
  if (!(end > start)) return null;
  // Function: event.
  // Inputs: position (coordinate-label position); index (zero-based index); delta (change in active
  // match count)
  // Outputs: Registers an interval-edge event used by the motif-coverage sweep.
  const event = (position, index, delta) => {
    if (!events.has(position)) events.set(position, []);
    events.get(position).push([index, delta]);
  };
  const regions = [], unassignedRegions = [];
  data.motifs.forEach(motif => {
    const positions = motif.positions.map(([a, b]) => {
      // Read the complete exported match before clipping it to the interval.
      // Keep the shared composition category, but name table regions by the
      // actual observed sequence when that sequence is available.
      const observed=motif.label==='Mismatch'&&typeof data.sequence==='string'
        &&Number.isInteger(a)&&Number.isInteger(b)&&a>=0&&b>a&&b<=data.sequence.length
        ? data.sequence.slice(a,b):null;
      const label=observed&&/^[ACGT]+$/.test(observed)?observed+' (mismatch)':motif.label;
      return {start:Math.max(start,a),end:Math.min(end,b),label};
    }).filter(p=>p.end>p.start).sort((a,b)=>a.start-b.start||a.end-b.end);
    // Multiple searched motifs can contribute to the shared Mismatch category.
    // Treat their overlapping spans as one category, counting each base once.
    let index = groups.findIndex(group => group.label === motif.label);
    if (index < 0) { index = groups.length; groups.push({label: motif.label, color: motif.color, bases: 0}); }
    const lastRegions=new Map();
    positions.forEach(({start:a,end:b,label}) => {
      event(a, index, 1); event(b, index, -1);
      if (motif.role !== 'tvr') return;
      // Merge touching/overlapping hits only within the same motif. The count
      // records exported matches, not an inferred number of perfect repeats.
      let region=lastRegions.get(label);
      if (region && a <= region.end) {
        region.end = Math.max(region.end, b); region.matches++;
      } else {
        region = {start: a, end: b, matches: 1, motif: label, color: motif.color};
        regions.push(region);
        lastRegions.set(label,region);
      }
    });
  });
  // Sweep interval edges to assign each base once. Multiple different motifs
  // become an explicit overlap slice; unmatched bases remain unassigned.
  event(start, -1, 0); event(end, -1, 0);
  const active = new Map(); let previous = start, overlap = 0, unassigned = 0;
  [...events.keys()].sort((a, b) => a - b).forEach(position => {
    const width = position - previous;
    if (!active.size) {
      unassigned += width;
      if (width > 0) {
        const last=unassignedRegions[unassignedRegions.length-1];
        if(last && last.end===previous) last.end=position;
        else unassignedRegions.push({start:previous,end:position,matches:null,motif:'Unassigned bases',color:'#b5bdc7'});
      }
    }
    else if (active.size === 1) groups[active.keys().next().value].bases += width;
    else overlap += width;
    events.get(position).forEach(([index, delta]) => {
      if (index < 0) return;
      const count = (active.get(index) || 0) + delta;
      if (count) active.set(index, count); else active.delete(index);
    });
    previous = position;
  });
  if (overlap) groups.push({label: 'Overlapping motifs', color: '#5F6875', bases: overlap});
  if (unassigned) groups.push({label: 'Unassigned bases', color: '#b5bdc7', bases: unassigned});
  regions.sort((a, b) => a.start - b.start || a.end - b.end || a.motif.localeCompare(b.motif));
  return {start, end, regions, unassignedRegions, composition: groups.filter(g => g.bases > 0)};
};

// Function: window.renderReadRepeats.
// Inputs: parent (parent element); read (embedded read record)
// Outputs: Renders the composition and region table from saved repeat data.
window.renderReadRepeats = (parent, read) => {
  // Function: add.
  // Inputs: tag (HTML tag name); text (displayed text); target (destination element or navigation
  // target)
  // Outputs: Created DOM element, appended to its target.
  const add = (tag, text, target) => {const e = document.createElement(tag); e.textContent = text; target.appendChild(e); return e;};
  let data = read.track_data;
  if (!data) {
    try { data = JSON.parse(document.getElementById('read-tracks-' + read.id)?.textContent || 'null'); } catch (_) {}
  }
  const summary = window.readRepeatSummary(data);
  const grid = add('div', '', parent); grid.className = 'read-repeat-panels';
  const detected = add('section', '', grid), composition = add('section', '', grid);
  const regionsHeading=add('h3', 'TVRs and unassigned regions', detected);
  add('h3', 'Repeat composition in telomere region', composition);
  if (!summary) {
    [detected, composition].forEach(panel => add('p', 'Complete motif positions and a TVR-inclusive telomere interval are required.', panel).className = 'note');
    return grid;
  }
  const span = summary.end - summary.start;
  const shortUnassigned=summary.unassignedRegions.filter(region=>region.end-region.start<4);
  const hiddenBases=shortUnassigned.reduce((total,region)=>total+region.end-region.start,0);
  let showAllUnassigned=false;
  const gapNote=add('p','',detected);gapNote.className='note read-short-gap-note';gapNote.setAttribute('role','status');
  const gapToggle=shortUnassigned.length?add('button','Show all',detected):null;
  if(gapToggle){gapToggle.type='button';gapToggle.className='read-short-gap-toggle';gapToggle.setAttribute('aria-label','Show all unassigned regions, including gaps shorter than 4 bp');}
  // Group by motif, retaining genomic order within each motif and stable region
  // numbers across pages. Only presentation order changes, never source values.
  const byMotif = new Map();
  [...summary.regions,...summary.unassignedRegions].forEach(region => {
    if (!byMotif.has(region.motif)) byMotif.set(region.motif, []);
    byMotif.get(region.motif).push(region);
  });
  const tableRegions = [...byMotif.values()].flatMap(regions =>
    regions.map((region, index) => ({...region, number: index + 1})));
  const filter=add('details','',detected);filter.className='read-motif-filter';
  const filterTitle=add('summary','Filter motifs / categories',filter);
  const selectedMotifs=new Set(byMotif.keys());
  const filterActions=add('div','',filter),filterValues=add('div','',filter);
  const filterBoxes=[];
  // Function: updateFilter.
  // Inputs: None; uses the current report/browser state.
  // Outputs: Applies the selected motif categories to the region table.
  const updateFilter=()=>{
    filterTitle.textContent='Filter motifs / categories ('+selectedMotifs.size+' of '+byMotif.size+')';
    page=0;render();
  };
  [['Select all',true],['Clear',false]].forEach(([label,checked])=>{
    const button=add('button',label,filterActions);button.type='button';
    // Function: button.onclick.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Handles the UI action and updates the associated report controls.
    button.onclick=()=>{filterBoxes.forEach(([motif,box])=>{box.checked=checked;checked?selectedMotifs.add(motif):selectedMotifs.delete(motif);});updateFilter();};
  });
  byMotif.forEach((regions,motif)=>{
    const label=add('label','',filterValues),box=add('input','',label);box.type='checkbox';box.checked=true;
    add('span',motif+' ('+regions.length+')',label);filterBoxes.push([motif,box]);
    // Function: box.onchange.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Handles the UI action and updates the associated report controls.
    box.onchange=()=>{box.checked?selectedMotifs.add(motif):selectedMotifs.delete(motif);updateFilter();};
  });
  const scroll = add('div', '', detected); scroll.className = 'reads-scroll';
  const table = add('table', '', scroll); table.className = 'reads-table read-tvr-table';
  const heading = add('tr', '', add('thead', '', table));
  const columns=[['Motif / category','motif'],['Region','number'],['Start (bp)','start'],['End (bp)','end'],['Region length (bp)','length'],['Repeats (matches)','matches'],['Relative position','start']];
  let sortKey=null,ascending=true;
  columns.forEach(([label,key])=>{
    const th=add('th','',heading),button=add('button',label+' \u2195',th);button.type='button';button.className='read-column-filter';
    button.title='Sort '+label;
    // Function: button.onclick.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Handles the UI action and updates the associated report controls.
    button.onclick=()=>{ascending=sortKey===key?!ascending:true;sortKey=key;page=0;render();};
    th.dataset.sortKey=key;
  });
  const body = add('tbody', '', table), nav = add('nav', '', detected); nav.className = 'read-pagination';
  nav.setAttribute('aria-label', 'Detected TVR regions');
  let page = 0;
  // Function: render.
  // Inputs: None; uses the current report/browser state.
  // Outputs: Rebuilds the visible table/page using the current filters, sort and pagination.
  const render = () => {
    body.replaceChildren(); nav.replaceChildren();
    const shownCount=summary.unassignedRegions.length-(showAllUnassigned?0:shortUnassigned.length);
    regionsHeading.textContent='TVRs and unassigned regions ('+summary.regions.length.toLocaleString()+' TVRs, '+shownCount.toLocaleString()+' unassigned shown)';
    gapNote.textContent=showAllUnassigned?'All unassigned regions are listed. Base composition and percentages include every base.':
      shortUnassigned.length?shortUnassigned.length.toLocaleString()+' short unassigned regions (1\u20133 bp), totaling '+hiddenBases.toLocaleString()+' bp, are hidden. Base composition and percentages include these bases.':
      'No unassigned regions shorter than 4 bp. All unassigned regions are listed.';
    if(gapToggle){gapToggle.textContent=showAllUnassigned?'Show 4 bp and above':'Show all';gapToggle.setAttribute('aria-pressed',String(showAllUnassigned));}
    const sorted=tableRegions.filter(region=>selectedMotifs.has(region.motif)
      &&(showAllUnassigned||region.motif!=='Unassigned bases'||region.end-region.start>=4));
    if(sortKey) sorted.sort((a,b)=>{
      // Function: value.
      // Inputs: r (r)
      // Outputs: Selected measurement or table value for the current row.
      const value=r=>sortKey==='length'?r.end-r.start:r[sortKey];
      const av=value(a),bv=value(b);
      if(av==null||bv==null)return av==null&&bv==null?0:av==null?1:-1;
      const comparison=typeof av==='number'?av-bv:String(av).localeCompare(String(bv),undefined,{numeric:true});
      return (ascending?1:-1)*comparison;
    });
    heading.querySelectorAll('th').forEach(th=>th.setAttribute('aria-sort',th.dataset.sortKey===sortKey?(ascending?'ascending':'descending'):'none'));
    // Function: table.reportExportData.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Headers and current filtered/sorted table rows for export.
    table.reportExportData=()=>({name:'TVR and unassigned regions',
      headers:columns.map(([label],index)=>index===6?label+' (%)':label),
      rows:sorted.map(region=>[region.motif,'Region '+region.number,region.start+1,region.end,
        region.end-region.start,region.matches??'Not applicable',100*(region.start-summary.start)/span])});
    if(!sorted.length){const row=add('tr','',body);add('td','No regions match the selected motifs / categories.',row).colSpan=columns.length;}
    const visible = sorted.slice(page * 25, (page + 1) * 25);
    visible.forEach((region, i) => {
      const row = add('tr', '', body);
      // A motif appears once for its visible group, including on continuation
      // pages. Limit rowspan to this page so the table remains well formed.
      if (i === 0 || visible[i - 1].motif !== region.motif) {
        const motif = add('td', region.motif, row);
        let groupEnd=i+1;
        while(groupEnd<visible.length && visible[groupEnd].motif===region.motif)groupEnd++;
        motif.rowSpan=groupEnd-i;
        motif.style.color = region.color; motif.style.fontWeight = '600'; motif.style.verticalAlign = 'middle';
      }
      const regionCell=add('td','',row);
      const zoom=add('button','Region '+region.number,regionCell);zoom.type='button';zoom.className='read-region-zoom';
      zoom.title='Zoom to '+(region.start+1).toLocaleString()+' - '+region.end.toLocaleString()+' bp';
      // Function: zoom.onclick.
      // Inputs: None; uses the current report/browser state.
      // Outputs: Handles the UI action and updates the associated report controls.
      zoom.onclick=()=>{
        const chart=parent.querySelector('.read-density-chart');
        if (chart?._fullLayout) {
          Plotly.relayout(chart, {'xaxis2.range':[region.start/1000,region.end/1000]});
          chart.scrollIntoView({behavior:'smooth',block:'center'});
        }
      };
      [region.start + 1, region.end, region.end - region.start].forEach(value => add('td', value.toLocaleString(), row));
      add('td', region.matches == null ? 'Not applicable' : region.matches.toLocaleString(), row);
      add('td', (100 * (region.start - summary.start) / span).toFixed(1) + '%', row);
    });
    if (sorted.length > 25) {
      [['Previous', -1, page === 0], ['Next', 1, (page + 1) * 25 >= sorted.length]].forEach(([label, change, disabled]) => {
        const button = add('button', label, nav); button.type = 'button'; button.disabled = disabled;
        // Function: button.onclick.
        // Inputs: None; uses the current report/browser state.
        // Outputs: Handles the UI action and updates the associated report controls.
        button.onclick = () => {page += change; render();};
      });
    }
  };
  if(gapToggle)gapToggle.onclick=()=>{showAllUnassigned=!showAllUnassigned;page=0;render();};
  render();
  if (!summary.regions.length) add('p', 'No exported TVR matches in this telomere interval.', detected);
  add('p', 'Adjacent or overlapping matches of the same motif form one row. Positions are 1-based inclusive, clipped to the TVR-inclusive telomere. Unassigned regions have no exported motif match and are not TVRs. Repeats counts exported matches; relative position is the row start within that interval.', detected).className = 'note';

  const layout = add('div', '', composition); layout.className = 'read-composition-layout';
  const plot = add('div', '', layout); plot.className = 'read-composition-donut'; plot.style.height = '270px';
  const legend = add('ul', '', layout); legend.className = 'read-composition-legend';
  summary.composition.forEach(item => {
    const entry = add('li', '', legend), swatch = add('span', '', entry);
    swatch.className = 'motif-swatch'; swatch.style.backgroundColor = item.color;
    add('span', item.label, entry);
    add('strong', (item.bases > 0 && 100 * item.bases / span < .1 ? '<0.1%' : (100 * item.bases / span).toFixed(1) + '%'), entry);
  });
  if (window.Plotly) Plotly.newPlot(plot, [{type: 'pie', labels: summary.composition.map(i => i.label),
    values: summary.composition.map(i => i.bases), marker: {colors: summary.composition.map(i => i.color)},
    hole: 0.68, sort: false, textinfo: 'none', hovertemplate: '%{label}<br>%{value:,} bp (%{percent})<extra></extra>'}],
    {height: 270, margin: {l: 5, r: 5, t: 10, b: 10}, showlegend: false,
      annotations: [{xref: 'paper', yref: 'paper', x: 0.5, y: 0.5, showarrow: false,
        text: '<b>' + (span / 1000).toFixed(3) + ' kb</b><br>telomere', font: {size: 16, color: '#14263c'}}]},
    {responsive: true, displaylogo: false}).catch(() => {plot.textContent = 'Composition chart unavailable; percentages are listed alongside.';});
  add('p', 'Percent of bases in the TVR-inclusive interval. Each base is counted once; different motifs sharing bases form the overlap slice. Unassigned bases are shown separately. These percentages may differ from overlapping coverage percentages in Key Statistics.', composition).className = 'note';
  return grid;
};
