(() => {
  const detail = document.createElement('section');
  detail.id = 'read-detail'; detail.hidden = true;
  document.querySelector('main').appendChild(detail);
  const browsers = new Map();
  function node(tag, text, parent) {
    const el = document.createElement(tag); el.textContent = text;
    if (parent) parent.appendChild(el); return el;
  }
  function kb(value) { return value == null ? 'Unavailable' : (value / 1000).toLocaleString(undefined, {maximumFractionDigits:3}); }
  function pct(value) { return value == null ? 'Unavailable' : (value > 0 && value < .1 ? '<0.1%' : value.toFixed(1) + '%'); }
  function formatCount(value) { return value == null ? 'Unavailable' : value.toLocaleString(); }
  document.querySelectorAll('.read-browser').forEach(section => {
    const page = section.closest('.barcode-page');
    const showCompleteness = page.dataset.kmEnabled !== 'false';
    const tableHead=section.querySelector('.reads-table thead tr');
    // Saved dashboards can initialize again after a renderer update. Restore
    // plain headers before rebuilding controls, rather than nesting buttons.
    tableHead?.querySelectorAll('th').forEach(th=>{
      th.textContent=th.textContent.replace(/[\s\u25be\u2195]+$/g,'');
    });
    [...(tableHead?.children||[])].find(th=>th.textContent.trim()==='Arm')?.remove();
    if (!showCompleteness && tableHead) {
      [...tableHead.children].find(th=>th.textContent==='Status')?.remove();
    }
    if (showCompleteness && tableHead && ![...tableHead.children].some(th=>th.textContent==='Status')) {
      const th=node('th','Status');tableHead.insertBefore(th,tableHead.children[1]);
    }
    const rows = JSON.parse(section.querySelector('.read-data').textContent);
    // Saved plots may include reads removed by final filtering. Keep these
    // detail-only records out of the filtered read table and its statistics.
    const labelData = section.querySelector('.read-labels');
    const savedLabels = labelData ? JSON.parse(labelData.textContent) : {};
    const shortLabels = new Map();
    Object.entries(savedLabels).forEach(([header,label]) => {
      const key = header.split(/\s+/)[0];
      shortLabels.set(key, shortLabels.has(key) && shortLabels.get(key) !== label ? null : label);
    });
    const extraData = section.querySelector('.read-details');
    const detailRows = [...(rows || []), ...(extraData ? JSON.parse(extraData.textContent) : [])];
    const censoredHeaders = new Set(), completeHeaders = new Set(), edgeRemoved = new Set();
    const knownHeaders = new Set(detailRows.flatMap(r => [r.header, r.header.split(/\s+/)[0]]));
    page.querySelectorAll('.histogram-figure').forEach(script => {
      let figure; try { figure = JSON.parse(script.textContent); } catch (_) { return; }
      (figure.layout?.meta?.read_completeness || []).forEach(item => {
        if (item.event === 1) completeHeaders.add(item.read_id);
        if (item.event === 0) censoredHeaders.add(item.read_id);
      });
      (figure.data || []).forEach(trace => {
        // Censoring is a source status, not the same as exclusion by a filter.
        // Use NanoTel's explicitly exported censored-read trace; do not infer
        // completeness from lengths or absence from this trace.
        if (trace.name === 'Censored reads (observed lengths)' && Array.isArray(trace.text)) {
          trace.text.forEach(header => censoredHeaders.add(header));
        }
        (Array.isArray(trace.text) ? trace.text : []).forEach(text => {
          const match = /^Read: (.*?)<br>/.exec(text);
          if (match && /Edge filter: Removed/.test(text)) edgeRemoved.add(match[1]);
          if (!match || knownHeaders.has(match[1])) return;
          knownHeaders.add(match[1]);
          const value = pattern => { const found = pattern.exec(text); return found ? Number(found[1].replaceAll(',', '')) : null; };
          detailRows.push({id:'saved-'+encodeURIComponent(match[1]),header:match[1],label:savedLabels[match[1]] || shortLabels.get(match[1]) || 'Read '+match[1],
            length:value(/Read length: ([\d,]+) bp/),exact_length:value(/Telomere length \(exact\): ([\d,]+) bp/),
            plot_only:true,telomere:null,tvr_length:null,canonical:null,tvr:null,blocks:null,overlap:null,unassigned:null,
            chromosomes:[],arms:[],motifs:null,regions:null,
            source_note:'Saved pre-final-filter plot record. '+(/Edge filter: Removed/.test(text)?'Removed by the edge filter. ':'')+'Only measurements exported in this plot are available here.'});
        });
      });
    });
    detailRows.forEach(read => {
      const keys=[read.header,read.header.split(/\s+/)[0]];
      read.censored = showCompleteness && (read.completeness === 'censored' || keys.some(key=>censoredHeaders.has(key)));
      const complete=read.completeness === 'complete' || keys.some(key=>completeHeaders.has(key));
      read.completeness_label = read.censored ? 'Censored (incomplete)' : complete ? 'Complete' : 'Completeness unknown';
      read.excluded = !!read.source_note || !!read.plot_only;
      read.read_status = showCompleteness
        ? (read.excluded ? 'Excluded by filtering; ' : '') + read.completeness_label
        : (read.excluded ? 'Excluded by filtering' : 'Included in filtered reads');
      read.filter_reason = keys.some(key=>edgeRemoved.has(key)) ? 'Removed by the NanoTel edge filter: read length minus running median telomere length did not exceed the configured edge-distance threshold.' :
        read.excluded ? (read.nanotel_filter_reason && read.nanotel_filter_reason!=='Passed NanoTel filters' ? read.nanotel_filter_reason : 'Outside the displayed filtered population; specific filter reason unavailable.') : 'Included in the filtered read table.';
    });
    browsers.set(page.id, {page, rows:detailRows});
    section.querySelector('.read-total').textContent = rows ? `(${rows.length.toLocaleString()} telomeric reads)` : '';
    if (rows === null) {
      section.querySelector('.read-status').textContent = 'Post-filtered read records were not exported.';
      section.querySelectorAll('input,select').forEach(el => el.disabled = true); return;
    }
    section.querySelectorAll('.read-controls label').forEach(label=>{
      if (!label.querySelector('.read-limit,.read-search')) label.remove();
    });
    const controls=section.querySelector('.read-controls');
    if (!section.querySelector('.read-search')) {
      const label=node('label','Search ',null),input=node('input','',label);
      input.className='read-search';input.type='search';input.placeholder='Search reads...';controls.prepend(label);
    }
    const search=section.querySelector('.read-search');
    const limit=section.querySelector('.read-limit');
    const sort={value:'original'},direction={value:'desc'};
    const originalOrder=new Map(rows.map((r,index)=>[r,index]));
    const columnFilters=new Map();
    const columnKeys=['label',...(showCompleteness?['read_status']:[]),'telomere','tvr_length','length','canonical','tvr','blocks','chromosomes'];
    const exportHeaders=[...section.querySelectorAll('.reads-table thead th')].map(th=>th.textContent.replace(/\s*[▾↕]$/,'').trim());
    const columnValues=r=>[r.label,...(showCompleteness?[r.read_status]:[]),kb(r.telomere),kb(r.tvr_length),kb(r.length),pct(r.canonical),pct(r.tvr),formatCount(r.blocks),r.chromosomes.join(', ')||'Unavailable'];
    let openMenu=null;
    section.querySelectorAll('.reads-table thead th').forEach((th,index)=>{
      const title=th.textContent;th.textContent='';
      const trigger=node('button',title+' \u25be',th);trigger.type='button';trigger.className='read-column-filter';trigger.setAttribute('aria-expanded','false');
      trigger.onclick=()=>{
        if(openMenu){openMenu();}
        const menu=node('div','',document.body);menu.className='read-filter-menu';menu.setAttribute('role','dialog');menu.setAttribute('aria-label','Filter '+title);trigger.setAttribute('aria-expanded','true');
        const isStatus=columnKeys[index]==='read_status';
        const sortActions=node('div','',menu);sortActions.className='read-column-sort';if(isStatus)sortActions.hidden=true;
        const numeric=['label','telomere','tvr_length','length','canonical','tvr','blocks'].includes(columnKeys[index]);
        [['asc',numeric?'Sort smallest to largest':'Sort A to Z'],['desc',numeric?'Sort largest to smallest':'Sort Z to A']].forEach(([order,label])=>{
          const button=node('button',label,sortActions);button.type='button';
          button.setAttribute('aria-pressed',String(sort.value===columnKeys[index]&&direction.value===order));
          button.onclick=()=>{sort.value=columnKeys[index];direction.value=order;close();current=1;render();};
        });
        const values=[...new Set(rows.map(r=>columnValues(r)[index]))].sort((a,b)=>String(a).localeCompare(String(b),undefined,{numeric:true}));
        const chosen=new Set(columnFilters.has(index)?columnFilters.get(index):values);
        const searchInput=node('input','',menu);searchInput.type='search';searchInput.placeholder='Search values';searchInput.setAttribute('aria-label','Search '+title);
        if (isStatus) searchInput.hidden=true;
        const actions=node('div','',menu),list=node('div','',menu);list.className='read-filter-values';
        const draw=()=>{list.replaceChildren();values.filter(v=>String(v).toLowerCase().includes(searchInput.value.toLowerCase())).forEach(value=>{
          const label=node('label','',list),box=node('input','',label);box.type='checkbox';box.checked=chosen.has(value);node('span',value,label);
          box.onchange=()=>box.checked?chosen.add(value):chosen.delete(value);
        });};
        [['Select all',true],['Clear',false]].forEach(([label,check])=>{const b=node('button',label,actions);b.type='button';b.onclick=()=>{values.filter(v=>String(v).toLowerCase().includes(searchInput.value.toLowerCase())).forEach(v=>check?chosen.add(v):chosen.delete(v));draw();};});
        const close=()=>{menu.remove();trigger.setAttribute('aria-expanded','false');openMenu=null;document.removeEventListener('pointerdown',outside);window.removeEventListener('hashchange',close);window.removeEventListener('resize',close);};
        const outside=e=>{if(!th.contains(e.target)&&!menu.contains(e.target))close();};document.addEventListener('pointerdown',outside);window.addEventListener('hashchange',close);window.addEventListener('resize',close);openMenu=close;
        const apply=node('button','Apply',menu);apply.type='button';apply.onclick=()=>{if(chosen.size===values.length)columnFilters.delete(index);else columnFilters.set(index,chosen);trigger.classList.toggle('active',columnFilters.has(index));close();current=1;render();};
        const cancel=node('button','Cancel',menu);cancel.type='button';cancel.onclick=close;
        menu.onkeydown=e=>{if(e.key==='Escape'){close();trigger.focus();}};
        searchInput.oninput=draw;draw();
        const anchor=trigger.getBoundingClientRect();
        menu.style.left=Math.max(8,Math.min(anchor.left,window.innerWidth-menu.offsetWidth-8))+'px';
        menu.style.top=Math.max(8,Math.min(anchor.bottom+4,window.innerHeight-menu.offsetHeight-8))+'px';
        if(isStatus) list.querySelector('input')?.focus();else searchInput.focus();
      };
    });
    let current = 1;
    function render() {
      const filtered = rows.filter(r => (r.label+' '+r.header).toLowerCase().includes(search.value.toLowerCase()) && [...columnFilters].every(([index,values])=>values.has(columnValues(r)[index])));
      direction.disabled = sort.value === 'original';
      section.querySelectorAll('.reads-table thead th').forEach((th,index)=>{
        th.setAttribute('aria-sort',sort.value===columnKeys[index]?(direction.value==='asc'?'ascending':'descending'):'none');
      });
      if (sort.value !== 'original') {
        const key = sort.value, sign = direction.value === 'asc' ? 1 : -1;
        // Sort the filtered copy, never the source population or plotted records.
        // Missing values stay last in either direction; equal values keep source order.
        const value = read => Array.isArray(read[key]) ? read[key].join(', ') || null : read[key];
        filtered.sort((a,b) => {
          const av=value(a), bv=value(b);
          if (av == null || bv == null) return av == null && bv == null ? originalOrder.get(a)-originalOrder.get(b) : av == null ? 1 : -1;
          const comparison = typeof av === 'number' && typeof bv === 'number' ? av-bv : String(av).localeCompare(String(bv),undefined,{numeric:true});
          return sign*comparison || originalOrder.get(a)-originalOrder.get(b);
        });
      }
      browsers.get(page.id).orderedRows=filtered;
      section.querySelector('.reads-table').reportExportData=()=>({name:page.dataset.label+' Reads',
        headers:exportHeaders,rows:filtered.map(r=>[r.label,...(showCompleteness?[r.read_status]:[]),
          ...[r.telomere,r.tvr_length,r.length].map(value=>value==null?'Unavailable':value/1000),
          ...[r.canonical,r.tvr,r.blocks].map(value=>value??'Unavailable'),
          r.chromosomes.join(', ')||'Unavailable'])});
      const size = Number(limit.value), count = Math.max(1,Math.ceil(filtered.length/size));
      current = Math.min(current,count);
      const body = section.querySelector('tbody'); body.replaceChildren();
      filtered.slice((current-1)*size,current*size).forEach(r => {
        const tr = node('tr','',body), td = node('td','',tr);
        const href = '#/barcode/' + page.id + '/read/' + r.id;
        if (r.id) { const a = node('a',r.label,td); a.href = href; a.title = r.header; }
        else node('span',r.label,td);
        columnValues(r).slice(1).forEach(text => node('td',text,tr));

      });
      section.querySelector('.read-status').textContent = filtered.length ? `${(current-1)*size+1}–${Math.min(current*size,filtered.length)} of ${filtered.length.toLocaleString()} reads` : 'No reads match these filters.';
      const nav = section.querySelector('.read-pagination'); nav.replaceChildren();
      function button(text,target,disabled) {
        const b = node('button',text,nav); b.type='button'; b.disabled=disabled;
        if(target===current) b.setAttribute('aria-current','page');
        b.addEventListener('click',()=>{current=target;render();});
      }
      button('Previous',current-1,current===1);
      // Keep pagination bounded even for millions of reads.
      const numbers = [...new Set([1,current-1,current,current+1,count])].filter(n=>n>=1&&n<=count).sort((a,b)=>a-b);
      numbers.forEach((n,i)=>{if(i&&n>numbers[i-1]+1)node('span','...',nav);button(String(n),n,false);});
      button('Next',current+1,current===count);
    }
    search.addEventListener('input',()=>{current=1;render();});
    limit.addEventListener('change',()=>{current=1;render();});
    render();
  });
  window.reportReadRows = id => browsers.get(id)?.rows || [];
  // One reusable detail shell avoids generating thousands of hidden pages.
  window.showReadDetail = hash => {
    detail.hidden=true;
    const match = /^#\/barcode\/([^/]+)\/read\/([^/]+)$/.exec(hash);
    if(!match)return false;
    const source=browsers.get(match[1]);
    let read=source && source.rows.find(r=>r.id===match[2]);
    // Preserve bookmarked fallback routes created by older reports.
    if(!read && source && match[2].startsWith('saved-')) {
      try { const header=decodeURIComponent(match[2].slice(6));read=source.rows.find(r=>r.header===header || r.header.split(/\s+/)[0]===header); } catch (_) {}
    }
    if(!read)return false;
    // Release the previous read's interactive chart before reusing this shell.
    detail.querySelectorAll('.js-plotly-plot').forEach(plot=>window.Plotly?.purge(plot));
    detail.replaceChildren(); detail.hidden=false;
    detail.dataset.barcodeLabel=source.page.dataset.label;detail.dataset.readLabel=read.label;
    const nav=node('nav','',detail); nav.className='breadcrumbs';
    node('a','All Barcodes',nav).href='#/'; node('span','›',nav);
    node('a',source.page.dataset.label,nav).href='#/barcode/'+match[1]; node('span','› '+read.label,nav);
    const ordered=source.orderedRows||[];
    const position=ordered.findIndex(row=>row.id===read.id);
    const controls=node('div','',nav);controls.className='read-navigation';
    const previous=position>0?ordered[position-1]:null;
    const previousButton=node('button','Previous read',controls);previousButton.type='button';previousButton.className='read-next';previousButton.disabled=!previous;
    previousButton.title=previous?'Open '+previous.label+' in the current table order':position<0?'This read is outside the current table selection':'First read in the current table selection';
    previousButton.onclick=()=>{if(previous)location.hash='#/barcode/'+match[1]+'/read/'+previous.id;};
    const next=position>=0?ordered[position+1]:null;
    const nextButton=node('button','Next read',controls);nextButton.type='button';nextButton.className='read-next';nextButton.disabled=!next;
    nextButton.title=next?'Open '+next.label+' in the current table order':position<0?'This read is outside the current table selection':'Last read in the current table selection';
    nextButton.onclick=()=>{if(next)location.hash='#/barcode/'+match[1]+'/read/'+next.id;};
    // Keep the source read number independent of table sorting and plot rank.
    const summary=node('div','',detail); summary.className='read-summary-header';
    const identity=node('div','',summary); identity.className='read-summary-identity';
    node('h2',read.label.startsWith('Read ')?read.label:'Read: '+read.label,identity);
    node('p',source.page.dataset.label+' | Read length: '+formatCount(read.length)+(read.length == null ? '' : ' bp'),identity);
    const statsTitle=node('h2','',summary);statsTitle.className='read-statistics-title';
    node('span','1',statsTitle).className='number';
    statsTitle.appendChild(document.createTextNode('Key Statistics ('+read.label+')'));
    const iconIndices=[2,1,3,1,4,5];let cardIndex=0;
    function summaryCard(label,value,note,color) {
      const card=node('article','',summary);card.className='read-summary-card '+color;
      const originalIcon=source.page.querySelector('.stat-'+iconIndices[cardIndex++]+' svg');
      if(originalIcon)card.appendChild(originalIcon.cloneNode(true));
      const content=node('div','',card);content.className='read-summary-values';
      node('h3',label,content);node('strong',value,content);
      if(note)node('p',note,content);
    }
    // The TVR-inclusive call provides the interval used for TVR coverage.
    // Sum exported union blocks for bases rather than multiplying rounded percentages.
    const tvrBases=Array.isArray(read.regions) ? read.regions.reduce((sum,b)=>sum+b.end-b.start,0) : null;
    const bp=value=>value == null ? 'Unavailable' : formatCount(value)+' bp';
    const exactNote=read.telomere == null ? 'Exact call; filtered length unavailable' :
      read.telomere === read.exact_length ? 'Before final filtering' : 'Filtered: '+bp(read.telomere);
    summaryCard('Exact telomere length',read.exact_length == null ? 'Unavailable' : kb(read.exact_length)+' kb',exactNote,'read-summary-pink');
    summaryCard('Telomere length with TVRs',read.tvr_length == null ? 'Unavailable' : kb(read.tvr_length)+' kb','Includes detected variant repeats','read-summary-pink');
    summaryCard('TVR content',pct(read.tvr),bp(tvrBases)+' · Share of telomere bases','read-summary-blue');
    summaryCard('Canonical content',pct(read.canonical),'Share matching the standard repeat','read-summary-green');
    summaryCard('TVR blocks',formatCount(read.blocks),'Adjacent variant matches grouped together','read-summary-purple');
    // Keep separate assignments separate rather than invent chromosome-arm pairs.
    const chromosome=read.chromosomes.join(', ')||'Unavailable';
    summaryCard('Mapping',chromosome,'Chromosome assigned by alignment','read-summary-green');
    if (read.read_status !== 'Included in filtered reads') {
      const statusLabel=node('p',read.read_status,identity);statusLabel.className='read-state-label';
      statusLabel.title=read.filter_reason;
    }

    if(read.source_note) node('p',read.source_note,detail).className='note';
    if(read.censored) {
      const status=node('div','',detail);status.className='read-censor-notice';status.setAttribute('role','note');
      summary.insertBefore(status,statsTitle);
      node('strong','Censored read (incomplete telomere)',status);
      node('p','NanoTel marked this read as censored. Its observed telomere length is a lower bound: the full telomere may be longer. Censoring does not mean the read failed filtering. These observations are accounted for in the Kaplan-Meier estimate.',status);
    }
    window.renderReadTracks(detail, read, {mismatchEnabled: source.page.dataset.mismatchEnabled === 'true'});
    window.renderReadRepeats(detail, read);
    let tracks=read.track_data;
    if(!tracks){try{tracks=JSON.parse(document.getElementById('read-tracks-'+read.id)?.textContent||'null');}catch(_){tracks=null;}}
    const info=node('section','',detail);info.className='read-extra-information';
    node('h3','Telomere coordinates',info);
    const coordinateTable=node('table','',info);coordinateTable.className='reads-table';
    const coordinateHead=node('tr','',node('thead','',coordinateTable));
    ['Telomere','Start (bp)','End (bp)'].forEach(label=>node('th',label,coordinateHead));
    const coordinateBody=node('tbody','',coordinateTable);
    [['Exact','exact'],['Including TVRs','tvr_inclusive']].forEach(([label,key])=>{
      const interval=tracks?.intervals?.[key],row=node('tr','',coordinateBody);
      node('th',label,row).scope='row';
      node('td',interval?formatCount(interval[0]+1):'Unavailable',row);
      node('td',interval?formatCount(interval[1]):'Unavailable',row);
    });
    node('p','Coordinates are 1-based inclusive on the NanoTel analyzed sequence.',info).className='note';
    let information;
    const entry=(label,value)=>{
      if(!information)information=node('dl','',info);
      node('dt',label,information);node('dd',value,information);
    };
    if(read.excluded) {
      entry('Exclusion reason',read.filter_reason);
      if(read.nanotel_filter_reason && read.nanotel_filter_reason!==read.filter_reason)
        entry('NanoTel filter result',read.nanotel_filter_reason);
    }
    if(tracks?.mean_read_quality!=null)entry('Mean read quality',String(tracks.mean_read_quality));
    const alignments=tracks?.alignments||[];
    alignments.forEach((alignment,index)=>{
      const prefix=alignments.length>1?'Alignment '+(index+1)+(alignment.reference?' ('+alignment.reference+')':'')+' - ':'';
      if(alignment.reference)entry(prefix+'Reference',alignment.reference);
      if(alignment.strand)entry(prefix+'Mapping strand',alignment.strand);
      const reference=alignment.normalized||alignment.raw;
      if(reference && reference.start!=null && reference.end!=null) {
        const start=alignment.normalized?reference.start+1:reference.start;
        entry(prefix+'Reference interval',formatCount(Number(start))+'–'+formatCount(Number(reference.end))+' bp'+
          (alignment.normalized?' (1-based inclusive)':' (source coordinates)'));
      }
      if(alignment.query_interval)entry(prefix+'Aligned span within read',
        formatCount(alignment.query_interval.start+1)+'–'+formatCount(alignment.query_interval.end)+' bp (1-based inclusive)');
    });

    node('p',read.plot_only ? 'Lengths shown here come from the saved pre-final-filter plot. This read is not added to the filtered table or summary statistics.' : 'Lengths use exported post-filtered telomere records and source read lengths. Repeat percentages use the source-exported TVR-inclusive interval, which may differ from the filtered telomere length above. Overlapping categories are reported explicitly. Unavailable values are not inferred.',detail).className='note';
    if (read.tvr == null && !read.plot_only) {
      node('p','TVR base coverage is unavailable for the TVR-inclusive interval. Older coverage exports may need regeneration; unavailable does not mean zero TVRs.',detail).className='note';
    }
    if (read.regions !== null && read.regions !== undefined) {
      const blockDetails=node('details','',detail);
      node('summary','Merged TVR blocks in the TVR-inclusive telomere interval',blockDetails);
      const table=node('table','',blockDetails); table.className='reads-table';
      const head=node('tr','',node('thead','',table));
      ['Start (bp)','End (bp)','Length (bp)'].forEach(label=>node('th',label,head));
      const body=node('tbody','',table);
      read.regions.forEach(block=>{
        const row=node('tr','',body);
        [block.start+1,block.end,block.end-block.start].forEach(value=>node('td',String(value),row));
      });
      node('p','Positions are 1-based inclusive on the analyzed read. Adjacent or overlapping TVR hits form one block; a block may contain multiple motifs.',blockDetails).className='note';
    }
    const full=node('details','',detail);node('summary','Full source read header',full);node('p',read.header,full);
    document.querySelector('header h1').textContent='Telomere Analysis Summary - '+(read.label.startsWith('Read ')?read.label:'Read '+read.label);
    return true;
  };
})();
