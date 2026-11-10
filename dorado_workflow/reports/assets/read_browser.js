(() => {
  const summaryOnly=document.body.dataset.summaryOnly==='true';
  const detail = document.createElement('section');
  detail.id = 'read-detail'; detail.hidden = true;
  if(!summaryOnly)document.querySelector('main').appendChild(detail);
  const browsers = new Map();
  // Function: node.
  // Inputs: tag (HTML tag name); text (displayed text); parent (parent element)
  // Outputs: Created DOM element, appended to the supplied parent.
  function node(tag, text, parent) {
    const el = document.createElement(tag); el.textContent = text;
    if (parent) parent.appendChild(el); return el;
  }
  // Function: kb.
  // Inputs: value (value to inspect or format)
  // Outputs: Formatted length in kilobases, or Unavailable for a missing value.
  function kb(value) { return value == null ? 'Unavailable' : (value / 1000).toLocaleString(undefined, {maximumFractionDigits:3}); }
  // Function: pct.
  // Inputs: value (value to inspect or format)
  // Outputs: Formatted percentage text, retaining the small-positive-value marker.
  function pct(value) { return value == null ? 'Unavailable' : (value > 0 && value < .1 ? '<0.1%' : value.toFixed(summaryOnly?2:1) + '%'); }
  // Function: formatCount.
  // Inputs: value (value to inspect or format)
  // Outputs: Formatted count text, or Unavailable.
  function formatCount(value) { return value == null ? 'Unavailable' : value.toLocaleString(); }
  document.querySelectorAll('.read-browser').forEach(section => {
    const page = section.closest('.barcode-page');
    const showCompleteness = page.dataset.kmEnabled === 'true';
    if(!showCompleteness)page.querySelectorAll('.barcode-results').forEach(panel=>panel.remove());
    const noTvr = page.dataset.tvrEnabled === 'false';
    const withMismatch = page.dataset.mismatchEnabled === 'true';
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
    const filteredRows = JSON.parse(section.querySelector('.read-data').textContent);
    let rows=filteredRows;
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
          // Function: value.
          // Inputs: pattern (statistic-heading matcher)
          // Outputs: Selected measurement or table value for the current row.
          const value = pattern => { const found = pattern.exec(text); return found ? Number(found[1].replaceAll(',', '')) : null; };
          detailRows.push({id:'saved-'+encodeURIComponent(match[1]),header:match[1],label:savedLabels[match[1]] || shortLabels.get(match[1]) || 'Read '+match[1],
            length:value(/Read length: ([\d,]+) bp/),exact_length:value(/Telomere length \(exact\): ([\d,]+) bp/),
            plot_only:true,telomere:null,tvr_length:null,canonical:null,tvr:null,tvr_bp:null,overlap:null,unassigned:null,
            chromosomes:[],motifs:null,
            source_note:'Saved pre-final-filter plot record. '+(/Edge filter: Removed/.test(text)?'Removed by the edge filter. ':'')+'Only measurements exported in this plot are available here.'});
        });
      });
    });
    detailRows.forEach(read => {
      const keys=[read.header,read.header.split(/\s+/)[0]];
      read.censored = showCompleteness && (read.completeness === 'censored' || keys.some(key=>censoredHeaders.has(key)));
      const complete=read.completeness === 'complete' || keys.some(key=>completeHeaders.has(key));
      read.completeness_label = showCompleteness
        ? read.censored ? 'Censored (incomplete)' : complete ? 'Complete' : 'Completeness unknown'
        : null;
      read.excluded = !!read.source_note || !!read.plot_only;
      read.read_status = read.plot_only ? 'Data unavailable' : showCompleteness
        ? (read.excluded ? 'Excluded by filtering; ' : '') + read.completeness_label
        : (read.excluded ? 'Excluded by filtering' : 'Included');
      read.filter_status=read.excluded?'Not in filtered results':'Passed filters';
      read.telomere_start = withMismatch ? read.mismatch_start : read.canonical_start;
      read.filter_reason = !read.excluded ? '-' : read.filtration_reason || (keys.some(key=>edgeRemoved.has(key)) ? 'Removed by the NanoTel edge filter: read length minus running median telomere length did not exceed the configured edge-distance threshold.' :
        (read.nanotel_filter_reason && read.nanotel_filter_reason!=='Passed NanoTel filters' ? read.nanotel_filter_reason : 'Outside the displayed filtered population; specific filter reason unavailable.'));
    });
    browsers.set(page.id, {page, rows:detailRows});
    section.querySelector('.read-total').textContent = rows ? `(${rows.length.toLocaleString()} telomeric reads)` : '';
    if (rows === null && !summaryOnly) {
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
    let populationSelect=null;
    {
      const label=node('label','Population ',controls);populationSelect=node('select','',label);
      [['all','All reads'],['filtered','Included only'],['excluded','Excluded only']].forEach(([v,t])=>{const o=node('option',t,populationSelect);o.value=v;});
      const all=[...detailRows].sort((a,b)=>a.label.localeCompare(b.label,undefined,{numeric:true}));
      const excluded=all.filter(read=>read.excluded);
      rows=all;
      // Function: populationSelect.onchange.
      // Inputs: None; uses the current report/browser state.
      // Outputs: Handles the UI action and updates the associated report controls.
      populationSelect.onchange=()=>{rows=populationSelect.value==='all'?all:populationSelect.value==='excluded'?excluded:filteredRows||[];columnFilters.clear();current=1;render();};
      // Function: reset.onclick.
      // Inputs: None; uses the current report/browser state.
      // Outputs: Handles the UI action and updates the associated report controls.
      const reset=node('button','Reset filters and sorting',controls);reset.type='button';reset.onclick=()=>{columnFilters.clear();sort.value='original';search.value='';current=1;render();};
    }
    const search=section.querySelector('.read-search');
    const limit=section.querySelector('.read-limit');
    if(summaryOnly)limit.value='25';
    const sort={value:'original'},direction={value:'desc'};
    const originalOrder=new Map(detailRows.map((r,index)=>[r,index]));
    const columnFilters=new Map();
    // Function: column.
    // Inputs: key (measurement/column key); title (displayed heading); format (display-value
    // formatter); exportValue (export-value formatter)
    // Outputs: Column descriptor with display and export-value formatters.
    const column = (key,title,format=value=>value??'Unavailable',exportValue=value=>value??'Unavailable') => ({key,title,format,exportValue});
    // Function: lengthColumn.
    // Inputs: key (measurement/column key); title (displayed heading)
    // Outputs: Column descriptor converting base pairs to kilobases.
    const lengthColumn = (key,title) => column(key,title,kb,value=>value==null?'Unavailable':value/1000);
    // Function: densityColumn.
    // Inputs: key (measurement/column key); title (displayed heading)
    // Outputs: Column descriptor converting fractional density to a percentage.
    const densityColumn = (key,title) => column(key,title,value=>value==null?'Unavailable':pct(100*value),value=>value==null?'Unavailable':100*value);
    const columns = [column('label','Read number'), lengthColumn('length','Total read length (kb)'),
      column('telomere_start','Telomere start (bp)',formatCount,value=>value==null?'Unavailable':value),
      ...(!noTvr?[column('tvr','TVR%',pct)]:[]),
      lengthColumn('exact_length','Canonical telomere length (kb)'),
      ...(withMismatch?[lengthColumn('mismatch_length','Telomere length including mismatch (kb)')]:[]),
      ...(!noTvr?[lengthColumn('tvr_length','Telomere length including TVRs (kb)')]:[]),
      ...(noTvr?[densityColumn('exact_density','Canonical repeat (%)')]:[column('canonical','Canonical repeat (%)',pct)]),
      column('read_status','Status'),
      column('filter_reason','Filtration reason'),
      column('chromosomes','Chromosome',value=>value.join(', ')||'Unavailable',value=>value.join(', ')||'Unavailable'),
      ...(!noTvr?[column('tvr_patterns','TVR patterns',value=>Array.isArray(value)?value.join(', '):'Unavailable')]:[])];
    tableHead.replaceChildren(...columns.map(c=>{const th=node('th',c.title);th.dataset.columnKey=c.key;return th;}));
    const readTableNote =
      (noTvr?'Canonical repeat % is the exported canonical repeat density within the canonical telomere call. ':'Canonical repeat % is the source-exported unique canonical base coverage within the TVR-inclusive telomere interval. ')+
      'Telomere start is 1-based and uses the '+(withMismatch?'mismatch-inclusive':'canonical')+' call. All reads shows included and excluded telomeric reads together, with their status and saved filtration reasons.';
    const columnKeys=columns.map(c=>c.key);
    const exportHeaders=[...section.querySelectorAll('.reads-table thead th')].map(th=>th.textContent.replace(/\s*[▾↕]$/,'').trim());
    // Function: columnValues.
    // Inputs: r (r)
    // Outputs: Ordered displayed cell values for one read.
    const columnValues=r=>columns.map(c=>{
      const value=c.format(r[c.key]);
      return r.plot_only&&value==='Unavailable'?'\u2014':value;
    });
    const numericKeys=new Set(['label','telomere','exact_length','mismatch_length','tvr_length','length','canonical','tvr','exact_density','mismatch_density','telomere_start']);
    // Size columns from the current filtered population, independently of
    // pagination. Long headings and text values wrap within compact columns.
    const readTable=section.querySelector('.reads-table');
    readTable.classList.add('read-values-table');
    readTable.querySelector('colgroup')?.remove();
    const colgroup=document.createElement('colgroup');
    readTable.prepend(colgroup);
    const scroll=readTable.closest('.reads-scroll');
    const measure=document.createElement('canvas').getContext('2d');
    let columnSizes=[];
    const fitColumns=()=>{
      if(!columnSizes.length||!scroll.clientWidth)return;
      const minimum=columnSizes.reduce((sum,c)=>sum+c.minimum,0);
      const preferred=columnSizes.reduce((sum,c)=>sum+c.preferred,0);
      const target=Math.max(minimum,scroll.clientWidth-1);
      const widths=columnSizes.map(c=>target<preferred
        ? c.minimum+(c.preferred-c.minimum)*(target-minimum)/Math.max(1,preferred-minimum)
        : c.preferred+(target-preferred)*c.weight/columnSizes.reduce((sum,c)=>sum+c.weight,0));
      colgroup.replaceChildren(...widths.map(width=>{
        const col=document.createElement('col');col.style.width=width+'px';return col;
      }));
      readTable.style.width=target+'px';
    };
    const sizeColumns=records=>{
      columnSizes=columns.map(c=>{
        measure.font='700 14px "Segoe UI", Arial, sans-serif';
        let wordWidth=Math.max(...c.title.split(/\s+/).map(word=>measure.measureText(word).width));
        measure.font='14px "Segoe UI", Arial, sans-serif';
        let contentWidth=0;
        for(const read of records){
          const text=String(c.format(read[c.key]));
          contentWidth=Math.max(contentWidth,measure.measureText(text).width);
          const units=c.key==='chromosomes'?text.split(/,\s*/):text.split(/\s+/);
          for(const word of units)wordWidth=Math.max(wordWidth,measure.measureText(word).width);
        }
        const numeric=numericKeys.has(c.key);
        const maximum=c.key==='read_status'?128:
          c.key==='filter_reason'||c.key==='chromosomes'?120:
          numeric?140:220;
        const minimum=Math.ceil(Math.max(64,wordWidth+26));
        return {minimum,preferred:Math.max(minimum,Math.min(maximum,contentWidth+24)),
          weight:numeric&&c.key!=='label'?1:0.2};
      });
      fitColumns();
    };
    new ResizeObserver(fitColumns).observe(scroll);
    // Compare unrounded values in the units displayed in the column heading.
    // Function: numericValue.
    // Inputs: read (embedded read record); index (zero-based index)
    // Outputs: Unrounded value in the column's displayed units, or null when unavailable.
    const numericValue=(read,index)=>{
      const c=columns[index];
      if(c.key==='label'){
        const match=String(read.label).match(/\d+/);
        return match?Number(match[0]):null;
      }
      const value=c.exportValue(read[c.key]);
      return typeof value==='number'&&Number.isFinite(value)?value:null;
    };
    // Function: matchesColumnFilter.
    // Inputs: read (embedded read record); index (zero-based index); filter (selected
    // categorical/numeric filter)
    // Outputs: True when the read satisfies the selected categorical or numeric filter.
    const matchesColumnFilter=(read,index,filter)=>{
      if(filter instanceof Set)return filter.has(columnValues(read)[index]);
      const value=numericValue(read,index);
      return value!==null&&(filter.operator==='above'?value>filter.threshold:value<filter.threshold);
    };
    let openMenu=null;
    section.querySelectorAll('.reads-table thead th').forEach((th,index)=>{
      const title=th.textContent;th.textContent='';
      const trigger=node('button',title+' \u25be',th);trigger.type='button';trigger.className='read-column-filter';trigger.setAttribute('aria-expanded','false');
      // Function: trigger.onclick.
      // Inputs: None; uses the current report/browser state.
      // Outputs: Handles the UI action and updates the associated report controls.
      trigger.onclick=()=>{
        if(openMenu){openMenu();}
        const menu=node('div','',document.body);menu.className='read-filter-menu';menu.setAttribute('role','dialog');menu.setAttribute('aria-label','Filter '+title);trigger.setAttribute('aria-expanded','true');
        const isStatus=columnKeys[index]==='read_status';
        const sortActions=node('div','',menu);sortActions.className='read-column-sort';if(isStatus)sortActions.hidden=true;
        const numeric=numericKeys.has(columnKeys[index]);
        [['asc',numeric?'Sort smallest to largest':'Sort A to Z'],['desc',numeric?'Sort largest to smallest':'Sort Z to A']].forEach(([order,label])=>{
          const button=node('button',label,sortActions);button.type='button';
          button.setAttribute('aria-pressed',String(sort.value===columnKeys[index]&&direction.value===order));
          // Function: button.onclick.
          // Inputs: None; uses the current report/browser state.
          // Outputs: Handles the UI action and updates the associated report controls.
          button.onclick=()=>{sort.value=columnKeys[index];direction.value=order;close();current=1;render();};
        });
        let focusInput,applyFilter;
        if(numeric){
          const saved=columnFilters.get(index);
          const label=node('label','Show values',menu);label.className='read-numeric-filter';
          const operator=node('select','',label);operator.setAttribute('aria-label','Comparison for '+title);
          [['above','Above'],['below','Below']].forEach(([value,text])=>{const option=node('option',text,operator);option.value=value;});
          const cutoffBp=Number(page.dataset.shortCutoffBp);
          const shortPreset=['exact_length','mismatch_length','tvr_length','telomere'].includes(columnKeys[index])&&Number.isFinite(cutoffBp)&&cutoffBp>0;
          if(shortPreset){
            const option=node('option','Below '+(cutoffBp/1000).toLocaleString(undefined,{maximumFractionDigits:10})+' kb (short telomeres)',operator);
            option.value='short';
          }
          operator.value=saved?.preset==='short'&&shortPreset?'short':saved?.operator||'above';
          const input=node('input','',label);input.type='number';input.step='any';input.placeholder='Enter threshold';input.setAttribute('aria-label','Threshold for '+title);
          if(saved&&!(saved instanceof Set))input.value=String(saved.threshold);
          const updatePreset=()=>{
            input.disabled=operator.value==='short';
            if(input.disabled){input.value=String(cutoffBp/1000);input.setCustomValidity('');}
          };
          operator.onchange=updatePreset;updatePreset();
          const note=node('p','Use the units shown in the column title. Values equal to the threshold and unavailable values are excluded.',menu);note.className='note';
          // Function: clear.onclick.
          // Inputs: None; uses the current report/browser state.
          // Outputs: Handles the UI action and updates the associated report controls.
          const clear=node('button','Clear filter',menu);clear.type='button';clear.onclick=()=>{columnFilters.delete(index);close();current=1;render();};
          // Function: applyFilter.
          // Inputs: None; uses the current report/browser state.
          // Outputs: Applies the current column-filter selection and refreshes the table.
          applyFilter=()=>{
            if(!input.value.trim()||!input.checkValidity()||!Number.isFinite(Number(input.value))){input.setCustomValidity('Enter a valid numeric threshold.');input.reportValidity();input.focus();return false;}
            columnFilters.set(index,{operator:operator.value==='short'?'below':operator.value,
              threshold:Number(input.value),preset:operator.value==='short'?'short':undefined});return true;
          };
          // Function: input.oninput.
          // Inputs: None; uses the current report/browser state.
          // Outputs: Handles the UI action and updates the associated report controls.
          input.oninput=()=>input.setCustomValidity('');
          focusInput=input;
        }else{
        const values=[...new Set(rows.map(r=>columnValues(r)[index]))].sort((a,b)=>String(a).localeCompare(String(b),undefined,{numeric:true}));
        const chosen=new Set(columnFilters.has(index)?columnFilters.get(index):values);
        const searchInput=node('input','',menu);searchInput.type='search';searchInput.placeholder='Search values';searchInput.setAttribute('aria-label','Search '+title);
        if (isStatus) searchInput.hidden=true;
        const actions=node('div','',menu),list=node('div','',menu);list.className='read-filter-values';
        // Function: draw.
        // Inputs: None; uses the current report/browser state.
        // Outputs: Rebuilds the visible filter choices from the current search text.
        const draw=()=>{list.replaceChildren();values.filter(v=>String(v).toLowerCase().includes(searchInput.value.toLowerCase())).forEach(value=>{
          const label=node('label','',list),box=node('input','',label);box.type='checkbox';box.checked=chosen.has(value);node('span',value,label);
          // Function: box.onchange.
          // Inputs: None; uses the current report/browser state.
          // Outputs: Handles the UI action and updates the associated report controls.
          box.onchange=()=>box.checked?chosen.add(value):chosen.delete(value);
        });};
        // Function: b.onclick.
        // Inputs: None; uses the current report/browser state.
        // Outputs: Handles the UI action and updates the associated report controls.
        [['Select all',true],['Clear',false]].forEach(([label,check])=>{const b=node('button',label,actions);b.type='button';b.onclick=()=>{values.filter(v=>String(v).toLowerCase().includes(searchInput.value.toLowerCase())).forEach(v=>check?chosen.add(v):chosen.delete(v));draw();};});
          searchInput.oninput=draw;draw();
          focusInput=isStatus?list.querySelector('input'):searchInput;
          // Function: applyFilter.
          // Inputs: None; uses the current report/browser state.
          // Outputs: Applies the current column-filter selection and refreshes the table.
          applyFilter=()=>{if(chosen.size===values.length)columnFilters.delete(index);else columnFilters.set(index,chosen);return true;};
        }
        // Function: close.
        // Inputs: None; uses the current report/browser state.
        // Outputs: Closes the filter popup and removes temporary event listeners.
        const close=()=>{menu.remove();trigger.setAttribute('aria-expanded','false');openMenu=null;document.removeEventListener('pointerdown',outside);window.removeEventListener('hashchange',close);window.removeEventListener('resize',close);};
        // Function: outside.
        // Inputs: e (browser event object)
        // Outputs: Handles an outside pointer event, closing the active filter popup when
        // appropriate.
        const outside=e=>{if(!th.contains(e.target)&&!menu.contains(e.target))close();};document.addEventListener('pointerdown',outside);window.addEventListener('hashchange',close);window.addEventListener('resize',close);openMenu=close;
        // Function: apply.onclick.
        // Inputs: None; uses the current report/browser state.
        // Outputs: Handles the UI action and updates the associated report controls.
        const apply=node('button','Apply',menu);apply.type='button';apply.onclick=()=>{if(!applyFilter())return;close();current=1;render();};
        const cancel=node('button','Cancel',menu);cancel.type='button';cancel.onclick=close;
        // Function: menu.onkeydown.
        // Inputs: e (browser event object)
        // Outputs: Handles the UI action and updates the associated report controls.
        menu.onkeydown=e=>{if(e.key==='Escape'){close();trigger.focus();}else if(e.key==='Enter'&&numeric){e.preventDefault();apply.click();}};
        const anchor=trigger.getBoundingClientRect();
        menu.style.left=Math.max(8,Math.min(anchor.left,window.innerWidth-menu.offsetWidth-8))+'px';
        menu.style.top=Math.max(8,Math.min(anchor.bottom+4,window.innerHeight-menu.offsetHeight-8))+'px';
        focusInput?.focus();
      };
    });
    let current = 1;
    // Function: render.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Rebuilds the visible table/page using the current filters, sort and pagination.
    function render() {
      {
        section.querySelector('.read-total').textContent='('+rows.length.toLocaleString()+' reads)';
        const scope=populationSelect?.value==='all'?'All detected telomeric reads, including retained and excluded reads. ':
          populationSelect?.value==='excluded'?'Reads not retained after filtering. ':'Reads retained after filtering. ';
        section.querySelector(':scope > p.note').textContent=scope+readTableNote+
          (rows.some(read=>read.plot_only)?' Rows marked Data unavailable are counted here, but their full table records were not exported. Any measurements shown come from saved plots; missing values are not included in summary statistics.':'');
      }
      const filtered = rows.filter(r => (r.label+' '+r.header+' '+columnValues(r).join(' ')).toLowerCase().includes(search.value.toLowerCase()) && [...columnFilters].every(([index,filter])=>matchesColumnFilter(r,index,filter)));
      sizeColumns(filtered);
      direction.disabled = sort.value === 'original';
      section.querySelectorAll('.reads-table thead th').forEach((th,index)=>{
        th.querySelector('.read-column-filter').classList.toggle('active',columnFilters.has(index));
        th.setAttribute('aria-sort',sort.value===columnKeys[index]?(direction.value==='asc'?'ascending':'descending'):'none');
      });
      if (sort.value !== 'original') {
        const key = sort.value, sign = direction.value === 'asc' ? 1 : -1;
        // Sort the filtered copy, never the source population or plotted records.
        // Missing values stay last in either direction; equal values keep source order.
        // Function: value.
        // Inputs: read (embedded read record)
        // Outputs: Selected measurement or table value for the current row.
        const value = read => Array.isArray(read[key]) ? read[key].join(', ') || null : read[key];
        filtered.sort((a,b) => {
          const av=value(a), bv=value(b);
          if (av == null || bv == null) return av == null && bv == null ? originalOrder.get(a)-originalOrder.get(b) : av == null ? 1 : -1;
          const comparison = typeof av === 'number' && typeof bv === 'number' ? av-bv : String(av).localeCompare(String(bv),undefined,{numeric:true});
          return sign*comparison || originalOrder.get(a)-originalOrder.get(b);
        });
      }
      browsers.get(page.id).orderedRows=filtered;
      // Function: section.querySelector('.reads-table').reportExportData.
      // Inputs: None; uses the current report/browser state.
      // Outputs: Headers and current filtered/sorted table rows for export.
      section.querySelector('.reads-table').reportExportData=()=>({name:page.dataset.label+' Reads',
        headers:exportHeaders,rows:filtered.map(r=>columns.map(c=>c.exportValue(r[c.key])))});
      const size = Number(limit.value), count = Math.max(1,Math.ceil(filtered.length/size));
      current = Math.min(current,count);
      const body = section.querySelector('tbody'); body.replaceChildren();
      filtered.slice((current-1)*size,current*size).forEach(r => {
        const tr = node('tr','',body), td = node('td','',tr);
        if(r.plot_only){
          tr.className='read-data-unavailable';
          tr.title='Full read data unavailable. This read is listed in a saved plot; only exported measurements can be shown.';
        }
        const href = '#/barcode/' + page.id + '/read/' + r.id;
        if (r.id && !summaryOnly) { const a = node('a',r.label,td); a.href = href; a.title = r.header; }
        else node('span',r.label,td);
        if(r.plot_only){
          const marker=node('span',' \u24d8',td);marker.className='read-missing-marker';
          marker.title=tr.title;marker.setAttribute('aria-label','Read data unavailable');
        }
        columnValues(r).slice(1).forEach((text,index) => {
          const td=node('td',text,tr);td.dataset.columnKey=columns[index+1].key;
          if(columns[index+1].key==='chromosomes'){
            td.textContent='';
            String(text).split(/,\s*/).forEach((arm,i,arms)=>{
              if(i)td.appendChild(document.createTextNode(' '));
              const item=node('span',arm+(i<arms.length-1?',':''),td);
              item.style.whiteSpace='nowrap';
            });
          }
          if(columns[index+1].key==='filter_reason')td.title=text;
        });

      });
      section.querySelector('.read-status').textContent = filtered.length ? `${(current-1)*size+1}–${Math.min(current*size,filtered.length)} of ${filtered.length.toLocaleString()} reads` : 'No reads match these filters.';
      const nav = section.querySelector('.read-pagination'); nav.replaceChildren();
      // Function: button.
      // Inputs: text (displayed text); target (destination element or navigation target); disabled
      // (whether navigation is disabled)
      // Outputs: Creates and attaches a navigation button with the selected target and enabled
      // state.
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
    // Function: browsers.get(page.id).findRead.
    // Inputs: id (stable barcode/read identity)
    // Outputs: Finds the read, changes pagination and highlights its table row.
    if(summaryOnly)browsers.get(page.id).findRead=id=>{
      const target=detailRows.find(r=>r.id===id);if(!target)return;
      if(populationSelect.value!=='all')populationSelect.value=filteredRows?.some(r=>r.id===id)?'filtered':'excluded';
      populationSelect.onchange();
      search.value='';columnFilters.clear();sort.value='original';
      const position=rows.findIndex(r=>r.id===id);current=Math.floor(position/Number(limit.value))+1;render();
      const tr=section.querySelector('tbody').rows[position%Number(limit.value)];
      if(tr){tr.style.background='#fff2b3';tr.tabIndex=-1;tr.focus({preventScroll:true});tr.scrollIntoView({behavior:'smooth',block:'center'});}
    };
    render();
  });
  // Function: window.findSummaryRead.
  // Inputs: barcode (stable barcode identity); id (stable barcode/read identity)
  // Outputs: Locates the read in its summary table and invokes its existing find handler.
  window.findSummaryRead=(barcode,id)=>browsers.get(barcode)?.findRead?.(id);
  // Function: window.reportReadRows.
  // Inputs: id (stable barcode/read identity)
  // Outputs: Embedded read-table records for the requested barcode.
  window.reportReadRows = id => browsers.get(id)?.rows || [];
  // One reusable detail shell avoids generating thousands of hidden pages.
  // Function: window.showReadDetail.
  // Inputs: hash (hash)
  // Outputs: True when the hash identifies an available read screen; false otherwise.
  window.showReadDetail = hash => {
    if(summaryOnly)return false;
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
    // Follow the displayed table order, including retained and excluded reads.
    const ordered=source.orderedRows||[];
    const position=ordered.findIndex(row=>row.id===read.id);
    const controls=node('div','',nav);controls.className='read-navigation';
    const previous=position>0?ordered[position-1]:null;
    const previousButton=node('button','Previous read',controls);previousButton.type='button';previousButton.className='read-next';previousButton.disabled=!previous;
    previousButton.title=previous?'Open '+previous.label+' in the current table order':position<0?'This read is outside the current table selection':'First read in the current table selection';
    // Function: previousButton.onclick.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Handles the UI action and updates the associated report controls.
    previousButton.onclick=()=>{if(previous)location.hash='#/barcode/'+match[1]+'/read/'+previous.id;};
    const next=position>=0?ordered[position+1]:null;
    const nextButton=node('button','Next read',controls);nextButton.type='button';nextButton.className='read-next';nextButton.disabled=!next;
    nextButton.title=next?'Open '+next.label+' in the current table order':position<0?'This read is outside the current table selection':'Last read in the current table selection';
    // Function: nextButton.onclick.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Handles the UI action and updates the associated report controls.
    nextButton.onclick=()=>{if(next)location.hash='#/barcode/'+match[1]+'/read/'+next.id;};
    // Keep the source read number independent of table sorting and plot rank.
    const summary=node('div','',detail); summary.className='read-summary-header';
    const identity=node('div','',summary); identity.className='read-summary-identity';
    node('h2',read.label.startsWith('Read ')?read.label:'Read: '+read.label,identity);
    const statsTitle=node('h2','',summary);statsTitle.className='read-statistics-title';
    node('span','1',statsTitle).className='number';
    statsTitle.appendChild(document.createTextNode('Key Statistics ('+read.label+')'));
    const iconIndices=[0,2,1,3,1,4,5];let cardIndex=0;
    // Function: summaryCard.
    // Inputs: label (displayed label); value (value to inspect or format); note (note); color
    // (display color)
    // Outputs: Creates and attaches one read-summary statistic card.
    function summaryCard(label,value,note,color) {
      const card=node('article','',summary);card.className='read-summary-card '+color;
      const originalIcon=source.page.querySelector('.stat-'+iconIndices[cardIndex++]+' svg');
      if(originalIcon)card.appendChild(originalIcon.cloneNode(true));
      const content=node('div','',card);content.className='read-summary-values';
      const title=node('h3','',content);
      label.split('\n').forEach((line,index)=>{
        if(index)title.appendChild(document.createElement('br'));
        title.appendChild(document.createTextNode(line));
      });
      node('strong',value,content);
      if(note)node('p',note,content);
    }
    // The TVR-inclusive call provides the interval used for TVR coverage.
    // Use exported covered bases rather than multiplying rounded percentages.
    const tvrBases=read.tvr_bp;
    // Function: bp.
    // Inputs: value (value to inspect or format)
    // Outputs: Formatted base-pair value.
    const bp=value=>value == null ? 'Unavailable' : formatCount(value)+' bp';
    summaryCard('Total read length',read.length == null ? 'Unavailable' : kb(read.length)+' kb','Full analyzed read','read-summary-blue');
    const exactNote=read.telomere == null ? 'Canonical call; filtered telomere length unavailable' :
      read.telomere === read.exact_length ? 'Before final filtering' : 'Filtered: '+bp(read.telomere);
    summaryCard('Canonical telomere length',read.exact_length == null ? 'Unavailable' : kb(read.exact_length)+' kb',exactNote,'read-summary-pink');
    const noTvr = source.page.dataset.tvrEnabled === 'false';
    const withMismatch = source.page.dataset.mismatchEnabled === 'true';
    if (noTvr) {
      // Function: density.
      // Inputs: value (value to inspect or format)
      // Outputs: Formatted repeat-density value.
      const density = value => value == null ? 'Unavailable' : pct(100 * value);
      if (withMismatch) {
        summaryCard('Telomere length\n(1 mismatch)',read.mismatch_length == null ? 'Unavailable' : kb(read.mismatch_length)+' kb','Canonical repeat call allowing one mismatch','read-summary-pink');
      } else {
        summaryCard('Filtered telomere length',read.telomere == null ? 'Unavailable' : kb(read.telomere)+' kb','Exported post-filtered telomere length','read-summary-pink');
      }
      summaryCard('Canonical repeat density',density(read.exact_density),'Canonical repeat density in the exact telomere interval','read-summary-green');
      if (withMismatch) {
        summaryCard('Repeat density\n(1 mismatch)',density(read.mismatch_density),'Canonical repeat density in the mismatch telomere interval','read-summary-blue');
      } else {
        summaryCard('TVR analysis','Off','No TVR patterns selected','read-summary-purple');
      }
    } else {
    summaryCard('Telomere length with TVRs',read.tvr_length == null ? 'Unavailable' : kb(read.tvr_length)+' kb','Includes detected variant repeats','read-summary-pink');
    summaryCard('TVR content',pct(read.tvr),bp(tvrBases)+' · Share of telomere bases','read-summary-blue');
    summaryCard('Canonical content',pct(read.canonical),'Share matching the standard repeat','read-summary-green');
    }
    // Keep separate assignments separate rather than invent chromosome-arm pairs.
    const chromosome=read.chromosomes.join(', ')||'Unavailable';
    summaryCard('Mapping',chromosome,'Chromosome end assigned by alignment','read-summary-green');
    const statusText=read.plot_only?'Data unavailable':source.page.dataset.kmEnabled==='true'?read.read_status:
      read.excluded?'Excluded by filtering':null;
    if (statusText && statusText !== 'Included') {
      const statusLabel=node('p',statusText,identity);statusLabel.className='read-state-label';
      statusLabel.title=read.filter_reason;
    }

    if(read.source_note) node('p',read.source_note,detail).className='note';
    if(read.censored) {
      const status=node('div','',detail);status.className='read-censor-notice';status.setAttribute('role','note');
      summary.insertBefore(status,statsTitle);
      node('strong','Censored read (incomplete telomere)',status);
      node('p','NanoTel marked this read as censored. Its observed telomere length is a lower bound: the full telomere may be longer. Censoring does not mean the read failed filtering. These observations are accounted for in the Kaplan-Meier estimate.',status);
    }
    window.renderReadTracks(detail, read, {mismatchEnabled: source.page.dataset.mismatchEnabled === 'true',
      tvrEnabled: source.page.dataset.tvrEnabled === 'false' ? false : undefined});
    window.renderReadRepeats(detail, read);
    let tracks=read.track_data;
    if(!tracks){try{tracks=JSON.parse(document.getElementById('read-tracks-'+read.id)?.textContent||'null');}catch(_){tracks=null;}}
    const info=node('section','',detail);info.className='read-extra-information';
    node('h3','Telomere coordinates',info);
    const coordinateTable=node('table','',info);coordinateTable.className='reads-table';
    const coordinateHead=node('tr','',node('thead','',coordinateTable));
    ['Telomere','Start (bp)','End (bp)'].forEach(label=>node('th',label,coordinateHead));
    const coordinateBody=node('tbody','',coordinateTable);
    [['Canonical','exact'],...(withMismatch?[['Allowing one mismatch','mismatch']]:[]),...(!noTvr?[['Including TVRs','tvr_inclusive']]:[])].forEach(([label,key])=>{
      const interval=tracks?.intervals?.[key],row=node('tr','',coordinateBody);
      node('th',label,row).scope='row';
      node('td',interval?formatCount(interval[0]+1):'Unavailable',row);
      node('td',interval?formatCount(interval[1]):'Unavailable',row);
    });
    node('p','Coordinates are 1-based inclusive on the NanoTel analyzed sequence.',info).className='note';
    let information;
    // Function: entry.
    // Inputs: label (displayed label); value (value to inspect or format)
    // Outputs: Creates and attaches one labeled read-detail entry.
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

    const measurementNote = noTvr
      ? 'Lengths and repeat densities use the exported canonical repeat calls. Canonical and mismatch densities use their respective telomere intervals. No TVR patterns were selected for this run.'
      : 'Lengths use exported post-filtered telomere records and source read lengths. Repeat percentages use the source-exported TVR-inclusive interval, which may differ from the filtered telomere length above. Overlapping categories are reported explicitly. Unavailable values are not inferred.';
    node('p',read.plot_only ? 'Lengths shown here come from the saved pre-final-filter plot. This read is not added to the filtered table or summary statistics.' : measurementNote,detail).className='note';
    if (!noTvr && read.tvr == null && !read.plot_only) {
      node('p','TVR base coverage is unavailable for the TVR-inclusive interval. Older coverage exports may need regeneration; unavailable does not mean zero TVRs.',detail).className='note';
    }

    document.querySelector('header h1').textContent='Telomere Analysis Summary - '+(read.label.startsWith('Read ')?read.label:'Read '+read.label);
    return true;
  };
})();
