/* Presentation aggregates of exported hits; no repeat search or new calling. */
window.readRepeatSummary = data => {
  const interval = data?.intervals?.tvr_inclusive;
  if (!interval || !Array.isArray(data.motifs)) return null;
  const [start, end] = interval, groups = [], events = new Map();
  if (!(end > start)) return null;
  const event = (position, index, delta) => {
    if (!events.has(position)) events.set(position, []);
    events.get(position).push([index, delta]);
  };
  const regions = [], unassignedRegions = [];
  data.motifs.forEach((motif, index) => {
    const positions = motif.positions.map(([a, b]) => [Math.max(start, a), Math.min(end, b)])
      .filter(([a, b]) => b > a).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    groups.push({label: motif.label, color: motif.color, bases: 0});
    let region = null;
    positions.forEach(([a, b]) => {
      event(a, index, 1); event(b, index, -1);
      if (motif.role !== 'tvr') return;
      // Merge touching/overlapping hits only within the same motif. The count
      // records exported matches, not an inferred number of perfect repeats.
      if (region && a <= region.end) {
        region.end = Math.max(region.end, b); region.matches++;
      } else {
        region = {start: a, end: b, matches: 1, motif: motif.label, color: motif.color};
        regions.push(region);
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
        else unassignedRegions.push({start:previous,end:position,matches:null,motif:'Unassigned bases',color:'#697586'});
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
  if (overlap) groups.push({label: 'Overlapping motifs', color: '#806b93', bases: overlap});
  if (unassigned) groups.push({label: 'Unassigned bases', color: '#b5bdc7', bases: unassigned});
  regions.sort((a, b) => a.start - b.start || a.end - b.end || a.motif.localeCompare(b.motif));
  return {start, end, regions, unassignedRegions, composition: groups.filter(g => g.bases > 0)};
};

window.renderReadRepeats = (parent, read) => {
  const add = (tag, text, target) => {const e = document.createElement(tag); e.textContent = text; target.appendChild(e); return e;};
  let data = read.track_data;
  if (!data) {
    try { data = JSON.parse(document.getElementById('read-tracks-' + read.id)?.textContent || 'null'); } catch (_) {}
  }
  const summary = window.readRepeatSummary(data);
  const grid = add('div', '', parent); grid.className = 'read-repeat-panels';
  const detected = add('section', '', grid), composition = add('section', '', grid);
  add('h3', 'TVRs and unassigned regions' + (summary ? ' (' + summary.regions.length.toLocaleString() + ' TVRs, ' + summary.unassignedRegions.length.toLocaleString() + ' unassigned)' : ''), detected);
  add('h3', 'Repeat composition in telomere region', composition);
  if (!summary) {
    [detected, composition].forEach(panel => add('p', 'Complete motif positions and a TVR-inclusive telomere interval are required.', panel).className = 'note');
    return grid;
  }
  const span = summary.end - summary.start;
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
  const updateFilter=()=>{
    filterTitle.textContent='Filter motifs / categories ('+selectedMotifs.size+' of '+byMotif.size+')';
    page=0;render();
  };
  [['Select all',true],['Clear',false]].forEach(([label,checked])=>{
    const button=add('button',label,filterActions);button.type='button';
    button.onclick=()=>{filterBoxes.forEach(([motif,box])=>{box.checked=checked;checked?selectedMotifs.add(motif):selectedMotifs.delete(motif);});updateFilter();};
  });
  byMotif.forEach((regions,motif)=>{
    const label=add('label','',filterValues),box=add('input','',label);box.type='checkbox';box.checked=true;
    add('span',motif+' ('+regions.length+')',label);filterBoxes.push([motif,box]);
    box.onchange=()=>{box.checked?selectedMotifs.add(motif):selectedMotifs.delete(motif);updateFilter();};
  });
  const scroll = add('div', '', detected); scroll.className = 'reads-scroll';
  const table = add('table', '', scroll); table.className = 'reads-table read-tvr-table';
  const heading = add('tr', '', add('thead', '', table));
  const columns=[['Motif / category','motif'],['Region','number'],['Start (bp)','start'],['End (bp)','end'],['Length (bp)','length'],['Repeats (matches)','matches'],['Relative position','start']];
  let sortKey=null,ascending=true;
  columns.forEach(([label,key])=>{
    const th=add('th','',heading),button=add('button',label+' \u2195',th);button.type='button';button.className='read-column-filter';
    button.title='Sort '+label;
    button.onclick=()=>{ascending=sortKey===key?!ascending:true;sortKey=key;page=0;render();};
    th.dataset.sortKey=key;
  });
  const body = add('tbody', '', table), nav = add('nav', '', detected); nav.className = 'read-pagination';
  nav.setAttribute('aria-label', 'Detected TVR regions');
  let page = 0;
  const render = () => {
    body.replaceChildren(); nav.replaceChildren();
    const sorted=tableRegions.filter(region=>selectedMotifs.has(region.motif));
    if(sortKey) sorted.sort((a,b)=>{
      const value=r=>sortKey==='length'?r.end-r.start:r[sortKey];
      const av=value(a),bv=value(b);
      if(av==null||bv==null)return av==null&&bv==null?0:av==null?1:-1;
      const comparison=typeof av==='number'?av-bv:String(av).localeCompare(String(bv),undefined,{numeric:true});
      return (ascending?1:-1)*comparison;
    });
    heading.querySelectorAll('th').forEach(th=>th.setAttribute('aria-sort',th.dataset.sortKey===sortKey?(ascending?'ascending':'descending'):'none'));
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
        button.onclick = () => {page += change; render();};
      });
    }
  };
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
