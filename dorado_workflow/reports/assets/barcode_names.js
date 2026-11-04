/* Display metadata only: stable barcode/read IDs and scientific values never change. */
(() => {
  if (window.reportBarcodeNames) return;
  // Function: start.
  // Inputs: None; uses the current report/browser state.
  // Outputs: Initializes this report feature and registers its event listeners.
  const start=()=>{
    const pages=[...document.querySelectorAll('.barcode-page')];
    if(!pages.length)return;
    const originals=new Map(pages.map(p=>[p.id,{label:p.dataset.label,chart:p.dataset.chartLabel,
      id:p.dataset.barcodeId||p.dataset.label.replace(/^Barcode\s*/i,'barcode').replace(/\s/g,'')}]));
    const storageKey='telomere-barcode-names-v1:'+location.pathname+':'+pages.map(p=>p.id).join(',');
    let names={};
    try{names=JSON.parse(localStorage.getItem(storageKey)||'{}');}catch{}
    // Function: clean.
    // Inputs: value (value to inspect or format)
    // Outputs: Trimmed display-name text within the configured length limit.
    const clean=value=>typeof value==='string'?value.trim().slice(0,100):'';
    names=Object.fromEntries(pages.map(p=>[p.id,clean(names?.[p.id])]));
    // Function: display.
    // Inputs: id (stable barcode/read identity)
    // Outputs: Display name combined with the original barcode label.
    const display=id=>names[id]?names[id]+' \u00b7 '+originals.get(id).label:originals.get(id).label;
    // Function: html.
    // Inputs: value (value to inspect or format)
    // Outputs: HTML-escaped label text.
    const html=value=>value.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const inputs=new Map(),graphs=new WeakSet(),previous=new Map(),history=new Map(pages.map(p=>[p.id,new Set()]));
    const status=document.createElement('p');status.setAttribute('role','status');
    // Function: metadata.
    // Inputs: page (barcode page element)
    // Outputs: Original barcode ID and custom name, or null when no barcode page is selected.
    const metadata=page=>page?{id:originals.get(page.id)?.id||'',name:names[page.id]||''}:null;
    // Function: exportData.
    // Inputs: table (table element); data (source/presentation data)
    // Outputs: Table data enriched with original barcode ID and display name.
    const exportData=(table,data)=>{
      const detail=table.closest('#read-detail');
      const route=detail?.querySelector('.breadcrumbs a[href^="#/barcode/"]')?.getAttribute('href');
      const page=table.closest('.barcode-page')||document.getElementById(route?.split('/')[2]);
      const info=metadata(page);
      if(!info||data.headers.includes('Barcode ID'))return data;
      return {...data,headers:['Barcode ID','Barcode display name',...data.headers],
        rows:data.rows.map(row=>[info.id,info.name,...row])};
    };
    // Function: aliases.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Map of current and previous labels to current display labels.
    const aliases=()=>{
      // Keep prior labels resolvable so repeated renames update existing plots.
      const result=new Map();
      for(const [id,original] of originals){
        const label=html(display(id));
        for(const value of [original.id,original.label,original.chart,previous.get(id),...history.get(id)])if(value)result.set(value,label);
      }
      return result;
    };
    // Function: updateGraph.
    // Inputs: graph (Plotly graph element)
    // Outputs: Promise completing after applicable graph labels have been updated.
    const updateGraph=async graph=>{
      if(!graph.data)return;
      if(graph.reportNamingBusy){graph.reportNamingPending=true;return;}
      const labels=aliases();let changed=false;
      // Function: replace.
      // Inputs: value (value to inspect or format)
      // Outputs: Value with recognized label aliases replaced; arrays are processed recursively.
      const replace=value=>{
        if(typeof value==='string'&&labels.has(value)&&labels.get(value)!==value){changed=true;return labels.get(value);}
        if(Array.isArray(value))return value.map(replace);
        return value;
      };
      for(const trace of graph.data){
        // customdata keeps stable identities for navigation and exclusion.
        for(const key of ['name','x','y','text','labels'])if(trace[key]!=null)trace[key]=replace(trace[key]);
      }
      for(const key of ['xaxis','yaxis']){
        const axis=graph.layout?.[key];
        if(axis)for(const field of ['ticktext','tickvals','categoryarray'])if(axis[field])axis[field]=replace(axis[field]);
      }
      for(const a of graph.layout?.annotations||[])for(const key of ['text','x','y'])a[key]=replace(a[key]);
      if(changed){graph.reportNamingBusy=true;try{await Plotly.redraw(graph);}finally{graph.reportNamingBusy=false;if(graph.reportNamingPending){graph.reportNamingPending=false;await updateGraph(graph);}}}
      if(!graphs.has(graph)&&graph.on){graphs.add(graph);graph.on('plotly_afterplot',()=>updateGraph(graph));}
    };
    // Function: sync.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Synchronizes labels, input controls and rendered graph captions.
    const sync=()=>{
      for(const page of pages){
        const original=originals.get(page.id),label=display(page.id);
        page.dataset.label=label;page.dataset.barcodeId=original.id;page.dataset.displayName=names[page.id]||'';
        for(const input of inputs.get(page.id)||[])if(input!==document.activeElement)input.value=names[page.id]||'';
        document.querySelectorAll('a[href="#/barcode/'+page.id+'"]').forEach(a=>{const target=a.querySelector('.barcode-stat-name')||a;if(target.textContent!==label)target.textContent=label;});
        const h=page.querySelector('section h2');
        if(h){const text=[...h.childNodes].find(n=>n.nodeType===3);if(text)text.textContent='Key Statistics ('+label+')';}
        const crumb=page.querySelector('.breadcrumbs>span:not(.barcode-step-navigation)');
        if(crumb)crumb.textContent=' › '+label;
      }
      const detail=document.querySelector('#read-detail');
      const id=location.hash.split('/')[2];
      if(detail&&originals.has(id))detail.dataset.barcodeLabel=display(id);
      document.querySelectorAll('.js-plotly-plot').forEach(updateGraph);
    };
    // Function: save.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Saves the selected data or setting using this feature's existing destination.
    const save=()=>{
      for(const page of pages){history.get(page.id).add(html(page.dataset.label));history.get(page.id).add(html(display(page.id)));}
      try{localStorage.setItem(storageKey,JSON.stringify(names));status.textContent='Names saved in this browser. Export the name list to keep a portable copy.';}
      catch{status.textContent='Browser storage is unavailable. Export the name list to keep your names.';}
      sync();
      for(const page of pages)previous.set(page.id,html(display(page.id)));
    };
    // Function: set.
    // Inputs: id (stable barcode/read identity); value (value to inspect or format)
    // Outputs: Updates the selected barcode setting and propagates the change.
    const set=(id,value)=>{if(!originals.has(id))throw Error('Unknown barcode');names[id]=clean(value);save();};
    // Function: field.
    // Inputs: id (stable barcode/read identity)
    // Outputs: Created barcode-control DOM element with its event listeners attached.
    const field=id=>{
      const input=document.createElement('input');input.type='text';input.maxLength=100;
      input.placeholder='Add a display name';input.value=names[id]||'';
      input.setAttribute('aria-label','Display name for '+originals.get(id).label);
      input.style.cssText='padding:8px;max-width:100%;width:250px;border:1px solid #bdcde0;border-radius:6px';
      input.addEventListener('change',()=>set(id,input.value));
      input.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();input.blur();}});
      if(!inputs.has(id))inputs.set(id,[]);inputs.get(id).push(input);return input;
    };
    const section=document.createElement('details');section.className='barcode-names';
    section.style.cssText='margin:18px 0;padding:16px;border:1px solid #dbe4ef;border-radius:10px';
    const summary=document.createElement('summary');summary.textContent='Barcode display names';section.appendChild(summary);
    const note=document.createElement('p');note.textContent='Add or edit a name, then press Enter or leave the field. Original barcode IDs stay visible. Clear a name to restore the original label.';section.appendChild(note);
    const table=document.createElement('table');table.innerHTML='<thead><tr><th>Barcode ID</th><th>Display name</th></tr></thead><tbody></tbody>';
    for(const page of pages){
      const row=table.tBodies[0].insertRow();row.insertCell().textContent=originals.get(page.id).id;row.insertCell().appendChild(field(page.id));
      const editor=document.createElement('label');editor.className='barcode-name-editor';
      editor.style.cssText='display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:14px 0';
      editor.append('Display name · '+originals.get(page.id).id+' ',field(page.id));
      page.querySelector('.breadcrumbs')?.after(editor);
    }
    // Function: table.reportExportData.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Headers and current filtered/sorted table rows for export.
    table.reportExportData=()=>({name:'Barcode names',headers:['Barcode ID','Display name'],rows:pages.map(p=>[originals.get(p.id).id,names[p.id]||''])});
    section.appendChild(table);
    const button=document.createElement('button');button.type='button';button.textContent='Export name list';
    // Function: button.onclick.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Handles the UI action and updates the associated report controls.
    button.onclick=()=>{
      const blob=new Blob([JSON.stringify({version:1,barcodes:pages.map(p=>({barcode_id:originals.get(p.id).id,display_name:names[p.id]||''}))},null,2)],{type:'application/json'});
      const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='barcode-names.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    };section.appendChild(button);
    const upload=document.createElement('input');upload.type='file';upload.accept='.json,application/json';upload.setAttribute('aria-label','Import barcode name list');
    // Function: upload.onchange.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Promise completing after the selected UI action finishes.
    upload.onchange=async()=>{
      try{
        const file=upload.files[0];if(!file)return;if(file.size>1000000)throw Error('Name list is too large.');
        const data=JSON.parse(await file.text());if(data.version!==1||!Array.isArray(data.barcodes))throw Error('Invalid name list.');
        let matched=0;const next={...names};
        for(const row of data.barcodes){const page=pages.find(p=>originals.get(p.id).id===row.barcode_id);if(page){next[page.id]=clean(row.display_name);matched++;}}
        if(!matched)throw Error('No matching barcode IDs in this name list.');names=next;save();status.textContent=matched+' barcode names imported.';
      }catch(error){status.textContent=error.message;}finally{upload.value='';}
    };section.append(' Import name list: ',upload,status);
    document.querySelector('.barcode-navigation')?.after(section);
    // Function: entries.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Barcode name records containing original IDs and current custom labels.
    window.reportBarcodeNames={set,display,exportData,entries:()=>pages.map(p=>metadata(p))};
    for(const page of pages)history.get(page.id).add(html(display(page.id)));
    sync();for(const page of pages)previous.set(page.id,html(display(page.id)));
    let pending=false;
    const observer=new MutationObserver(records=>{
      if(pending||!records.some(r=>(r.type==='attributes'&&r.target.matches('.js-plotly-plot'))||[...r.addedNodes].some(n=>n.nodeType===1&&(n.matches?.('.js-plotly-plot,#read-detail,.read-summary-identity')||n.querySelector?.('.js-plotly-plot,.read-summary-identity')))))return;
      pending=true;requestAnimationFrame(()=>{pending=false;sync();});
    });observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});
    window.addEventListener('hashchange',()=>requestAnimationFrame(sync));
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
