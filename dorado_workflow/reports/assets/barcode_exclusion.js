/* Reversible overview selection. Individual barcode pages and source calls stay intact. */
(() => {
  if(window.reportBarcodeExclusion)return;
  // Function: start.
  // Inputs: None; uses the current report/browser state.
  // Outputs: Initializes this report feature and registers its event listeners.
  const start=()=>{
    if(window.reportBarcodeExclusion)return;
    const overview=document.getElementById('run-overview');
    const pages=[...document.querySelectorAll('.barcode-page')];
    if(!overview||!pages.length)return;
    // Function: clone.
    // Inputs: v (value to inspect or format)
    // Outputs: Independent JSON-compatible copy of the value.
    const clone=v=>JSON.parse(JSON.stringify(v));
    // Function: numeric.
    // Inputs: v (value to inspect or format)
    // Outputs: True for a finite nonnegative number; false otherwise.
    const numeric=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0;
    // Function: countText.
    // Inputs: el (el)
    // Outputs: Parsed integer count, or null when the element has no valid count.
    const countText=el=>{const s=el?.textContent.trim().replace(/,/g,'');return s&&/^\d+$/.test(s)?Number(s):null;};
    // Function: card.
    // Inputs: root (DOM/data root); title (displayed heading)
    // Outputs: Matching statistic card element, or undefined when absent.
    const card=(root,title)=>[...root.querySelectorAll('.stats>.stat')].find(c=>c.querySelector('h3')?.textContent.trim()===title);
    let supplied=[];
    try{supplied=JSON.parse(document.getElementById('barcode-exclusion-data')?.textContent||'[]');}catch{}
    const facts=new Map();
    for(const page of pages){
      let fact=supplied.find(row=>row.id===page.id);
      if(!fact){
        // Older reports: use only explicitly exported filtered rows and source count cards.
        let rows=null;try{rows=JSON.parse(page.querySelector('script.read-data')?.textContent||'null');}catch{}
        const filtered=countText((card(page,'Post-filtered telomeric reads')||card(page,'NanoTel final-filtered telomeric reads'))?.querySelector('strong'));
        const short=page.querySelector('.short-telomere-stat');
        const cutoff=Number(page.dataset.shortCutoffBp||short?.dataset.cutoffBp);
        const lengths=Array.isArray(rows)&&rows.every(r=>numeric(r.telomere))&&rows.length===filtered?rows.map(r=>r.telomere):null;
        let composition=null;
        const section=page.querySelector('.composition-plot')?.closest('section');
        try{
          const pie=JSON.parse(section?.querySelector('script.histogram-figure')?.textContent||'null')?.data.find(t=>t.type==='pie');
          const withTVR=countText(card(page,'Reads with TVRs')?.querySelector('strong'));
          if(pie&&Array.isArray(pie.labels)&&Array.isArray(pie.values)&&pie.labels.length===pie.values.length&&pie.values.every(numeric)&&numeric(withTVR)&&lengths&&withTVR<=lengths.length)composition={base_counts:Object.fromEntries(pie.labels.map((label,i)=>[label,pie.values[i]])),total:lengths.length,with_tvr:withTVR};
        }catch{}
        fact={id:page.id,barcode_id:page.dataset.barcodeId||page.dataset.label.replace(/^Barcode\s*/i,'barcode'),
          total:countText(card(page,'Total barcode reads')?.querySelector('strong')),filtered,
          lengths,cutoff:cutoff>0?cutoff:null,composition,
          chromosomes:[...new Set((rows||[]).flatMap(r=>r.chromosomes?.length===1?r.chromosomes:[]))]};
      }
      facts.set(page.id,fact);
    }
    const key='telomere-barcode-exclusion-v1:'+location.pathname+':'+pages.map(p=>p.id).join(',');
    let excluded=new Set();try{excluded=new Set(JSON.parse(localStorage.getItem(key)||'[]').filter(id=>facts.has(id)));}catch{}
    const inputs=new Map(),snapshots=new Map(),messages=new Map();
    const originals=[...overview.querySelectorAll('.stats>.stat')].map(el=>({el,strong:el.querySelector('strong')?.textContent,strongClass:el.querySelector('strong')?.className,note:el.querySelector('p')?.textContent||'',title:el.title}));
    const heading=overview.querySelector('.stats')?.closest('section')?.querySelector('h2');
    const headingText=heading?[...heading.childNodes].find(n=>n.nodeType===3):null,originalHeading=headingText?.textContent;
    // Function: label.
    // Inputs: id (stable barcode/read identity)
    // Outputs: Current barcode display label.
    const label=id=>document.getElementById(id)?.dataset.label||facts.get(id).barcode_id;
    // Function: safe.
    // Inputs: s (source text)
    // Outputs: HTML-escaped text.
    const safe=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    // Function: resolve.
    // Inputs: value (value to inspect or format)
    // Outputs: Resolved stable identity, or no match when the source is ambiguous.
    const resolve=value=>{
      if(typeof value!=='string')return null;
      if(facts.has(value))return value;
      for(const page of pages){
        const f=facts.get(page.id);
        if([page.dataset.label,page.dataset.chartLabel,f.barcode_id].includes(value))return page.id;
        const number=f.barcode_id.match(/^barcode(\d+)$/i)?.[1];
        if(number&&new RegExp('(?:Barcode\\s*|BC)0*'+Number(number)+'(?:\\b|$)','i').test(value))return page.id;
      }
      return null;
    };
    // Function: included.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Source records for the currently included barcodes.
    const included=()=>pages.filter(p=>!excluded.has(p.id)).map(p=>facts.get(p.id));
    // Function: totals.
    // Inputs: rows (source records)
    // Outputs: Comparable pooled counts, lengths and short-telomere statistics.
    const totals=rows=>{
      // Function: sum.
      // Inputs: k (k)
      // Outputs: Sum of complete numeric inputs, or null when any required value is missing.
      const sum=k=>rows.length&&rows.every(r=>numeric(r[k]))?rows.reduce((n,r)=>n+r[k],0):null;
      // Function: compatible.
      // Inputs: k (k)
      // Outputs: True when the selected records use at most one nonmissing value for this field.
      const compatible=k=>new Set(rows.map(r=>r[k]).filter(v=>v!=null)).size<=1;
      const total=sum('total'),filtered=compatible('population')?sum('filtered'):null;
      const lengths=rows.length&&compatible('length_population')&&rows.every(r=>Array.isArray(r.lengths)&&r.lengths.every(numeric))?rows.flatMap(r=>r.lengths).sort((a,b)=>a-b):null;
      const median=lengths?.length?(lengths[Math.floor((lengths.length-1)/2)]+lengths[Math.floor(lengths.length/2)])/2:null;
      const cutoffs=new Set(rows.filter(r=>r.lengths?.length).map(r=>r.cutoff));
      const cutoff=cutoffs.size===1?[...cutoffs][0]:null;
      const short=lengths?.length&&numeric(cutoff)&&cutoff>0?lengths.filter(v=>v<cutoff).length:null;
      return {total,filtered,median,lengths,cutoff,short,
        percent:numeric(total)&&total>0&&numeric(filtered)&&filtered<=total?100*filtered/total:null,
        chromosomes:new Set(rows.flatMap(r=>r.chromosomes||[])).size};
    };
    // Function: updateStats.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Updates overview statistics for the current barcode selection.
    const updateStats=()=>{
      if(headingText)headingText.textContent=excluded.size?'Key Statistics (Included Barcodes)':originalHeading;
      if(!excluded.size){for(const {el,strong,strongClass,note,title} of originals){el.querySelector('strong').textContent=strong;el.querySelector('strong').className=strongClass;let p=el.querySelector('p');if(p)p.textContent=note;el.title=title;}return;}
      const rows=included(),t=totals(rows);
      // Function: format.
      // Inputs: v (value to inspect or format); suffix (display-unit suffix); digits (decimal
      // precision)
      // Outputs: Formatted value with the selected precision and suffix, or Unavailable.
      const format=(v,suffix='',digits=0)=>v==null?'Unavailable':v.toLocaleString('en-US',{minimumFractionDigits:digits,maximumFractionDigits:digits})+suffix;
      for(const {el} of originals){
        const title=el.querySelector('h3').textContent.trim();let value=null,note='Included barcodes only.';
        if(title==='Total barcodes'){value=String(rows.length);note=rows.length+' of '+pages.length+' barcodes included';}
        else if(!rows.length){value='No barcodes selected';note='Include a barcode to show pooled statistics.';}
        else if(title==='Total barcode reads'){value=format(t.total);note='Input reads · included barcodes';}
        else if(title==='Post-filtered telomeric reads'){value=format(t.filtered);note='Post-filtered reads · included barcodes';}
        else if(title==='% telomeric reads'){value=format(t.percent,'%',2);note='Included post-filtered reads / included input reads';}
        else if(title==='Median length'){value=format(t.median==null?null:t.median/1000,' kb',2);note='Pooled individual post-filtered reads · included barcodes';}
        else if((title==='Number of Chromosomes end found'||title==='Chromosomes')){value=t.chromosomes?format(t.chromosomes):'Unavailable';note='Distinct unambiguous mapped post-filtered chromosomes · included barcodes';}
        else if(title==='Short telomeres'){
          value=t.short==null?(t.lengths?.length===0?'No reads':'Unavailable'):format(100*t.short/t.lengths.length,'%',1);
          note=t.short==null?'Complete lengths and a common cutoff are required for included barcodes.':'< '+t.cutoff/1000+' kb · '+t.short.toLocaleString('en-US')+'/'+t.lengths.length.toLocaleString('en-US')+' post-filtered telomeric reads · included barcodes';
        }
        if(value!==null){el.querySelector('strong').textContent=value;el.querySelector('strong').classList.toggle('missing',value==='Unavailable'||value==='No barcodes selected');let p=el.querySelector('p');if(!p){p=document.createElement('p');el.querySelector('strong').after(p);}p.textContent=note;el.title=note;}
      }
    };
    // Function: snapshotsFor.
    // Inputs: graph (Plotly graph element)
    // Outputs: Original figure snapshot cached for this graph.
    const snapshotsFor=graph=>{
      if(!snapshots.has(graph)&&graph.data){
        snapshots.set(graph,clone({data:graph.data,layout:graph.layout}));
        graph.on?.('plotly_afterplot',()=>{
          if(busy||!excluded.size)return;
          // Older view controls can rebuild traces from their own full-data cache.
          // Function: containsExcluded.
          // Inputs: value (value to inspect or format)
          // Outputs: True when the inspected identity or nested array contains an excluded barcode.
          const containsExcluded=value=>Array.isArray(value)?value.some(containsExcluded):excluded.has(resolve(value));
          if(graph.data.some(t=>containsExcluded(t.name)||containsExcluded(t.x)||containsExcluded(t.y)||containsExcluded(t.customdata)))
            setTimeout(apply,0);
        });
      }
      return snapshots.get(graph);
    };
    // Function: filterGraph.
    // Inputs: snapshot (original figure snapshot)
    // Outputs: New figure with excluded barcodes removed consistently from point arrays.
    const filterGraph=(snapshot)=>{
      // Start from the complete snapshot so re-including a barcode restores it.
      // Function: keep.
      // Inputs: id (stable barcode/read identity)
      // Outputs: True when the identity is absent or belongs to an included barcode.
      const figure=clone(snapshot),keep=id=>!id||!excluded.has(id);
      figure.data=figure.data.filter(t=>!resolve(t.name)||keep(resolve(t.name))).map(t=>{
        if(t.type==='heatmap'){
          const indices=(t.y||[]).map((v,i)=>keep(resolve(v))?i:-1).filter(i=>i>=0);
          for(const field of ['y','z','customdata','text','hovertext'])if(Array.isArray(t[field]))t[field]=indices.map(i=>t[field][i]);
        }else if(t.type!=='pie'){
          const n=Math.max(t.x?.length||0,t.y?.length||0,t.customdata?.length||0);
          const indices=Array.from({length:n},(_,i)=>i).filter(i=>{
            const identity=t.meta==='barcode-links'?resolve(t.customdata?.[i]):Array.isArray(t.customdata?.[i])?resolve(t.customdata[i][0]):null;
            return keep(identity||resolve(t.x?.[i])||resolve(t.y?.[i]));
          });
          // Slice every point-aligned array together to preserve labels and links.
          for(const field of ['x','y','text','hovertext','customdata','ids'])if(Array.isArray(t[field])&&t[field].length===n)t[field]=indices.map(i=>t[field][i]);
          for(const parent of [t.marker,t.error_y,t.error_x])if(parent)for(const field of ['color','size','opacity','array','arrayminus'])if(Array.isArray(parent[field])&&parent[field].length===n)parent[field]=indices.map(i=>parent[field][i]);
        }
        return t;
      });
      for(const axis of ['xaxis','yaxis'])if(figure.layout[axis]){
        const a=figure.layout[axis];
        if(Array.isArray(a.tickvals)){
          const indices=a.tickvals.map((v,i)=>keep(resolve(v))?i:-1).filter(i=>i>=0);
          if(a.ticktext?.length===a.tickvals.length)a.ticktext=indices.map(i=>a.ticktext[i]);
          a.tickvals=indices.map(i=>a.tickvals[i]);
        }
        if(Array.isArray(a.categoryarray))a.categoryarray=a.categoryarray.filter(v=>keep(resolve(v)));
        a.autorange=true;delete a.range;
      }
      figure.layout.annotations=(figure.layout.annotations||[]).filter(a=>keep(resolve(a.x))&&keep(resolve(a.y)));
      // Cutoff segments in numeric category positions follow the remaining groups.
      const oldGroups=snapshot.data.filter(t=>resolve(t.name));
      const newGroups=oldGroups.filter(t=>keep(resolve(t.name)));
      figure.layout.shapes=(figure.layout.shapes||[]).flatMap(shape=>{
        if(shape.name!=='short-telomere-cutoff'||shape.xref!=='x'||!oldGroups.length||typeof shape.x0!=='number')return [shape];
        const index=Math.round((shape.x0+shape.x1)/2),group=oldGroups[index];
        if(!group||!keep(resolve(group.name)))return [];
        const offset=newGroups.indexOf(group)-index;return [{...shape,x0:shape.x0+offset,x1:shape.x1+offset}];
      });
      return figure;
    };
    // Function: compositionGraph.
    // Inputs: figure (figure data/layout); section (containing report section)
    // Outputs: Updates the figure and legend from included-barcode composition counts.
    const compositionGraph=(figure,section)=>{
      const pie=figure.data.find(t=>t.type==='pie');if(!pie)return;
      const rows=included(),available=rows.filter(r=>r.composition),bases={};
      let total=0,withTVR=0;
      for(const row of available){const c=row.composition;total+=c.total;withTVR+=c.with_tvr;for(const [motif,n] of Object.entries(c.base_counts))bases[motif]=(bases[motif]||0)+n;}
      pie.values=pie.labels.map(m=>bases[m]||0);
      const sum=pie.values.reduce((a,b)=>a+b,0);
      figure.layout.annotations=(figure.layout.annotations||[]).filter(a=>!(a.x===.5&&a.y===.5));
      figure.layout.annotations.push({x:.5,y:.5,xref:'paper',yref:'paper',showarrow:false,
        text:sum&&total?'Reads with TVRs<br><b>'+(100*withTVR/total).toFixed(1)+'%</b><br>'+withTVR.toLocaleString('en-US')+' / '+total.toLocaleString('en-US')+' reads':'No composition data<br>for included barcodes'});
      section.querySelectorAll('.read-composition-legend li').forEach((li,i)=>{li.hidden=!sum||!pie.values[i];const strong=li.querySelector('strong');if(strong)strong.textContent=sum?(100*pie.values[i]/sum).toFixed(1)+'%':'Unavailable';});
      let note=section.querySelector('.exclusion-composition-coverage');
      if(!note){note=document.createElement('p');note.className='note exclusion-composition-coverage';section.appendChild(note);}
      const missing=rows.filter(r=>!r.composition);
      note.textContent='Composition uses '+available.length+' of '+rows.length+' included barcodes with complete motif exports.'+(missing.length?' Missing motif data: '+missing.map(r=>label(r.id)).join(', ')+'.':'');
      // Hide the original run-wide coverage message while a subset is selected.
      for(const p of section.querySelectorAll('p.note'))if(p!==note&&/Excluded because motif|No barcodes have complete motif|Showing \d+ barcodes/.test(p.textContent))p.hidden=excluded.size>0;
      note.hidden=!excluded.size;
    };
    const controls=document.createElement('details');controls.className='barcode-exclusion-controls';controls.open=true;
    controls.style.cssText='margin:18px 0;padding:16px;border:1px solid #ccd8e8;border-radius:10px;background:#f7faff';
    const summary=document.createElement('summary');summary.textContent='Include or exclude barcodes';controls.appendChild(summary);
    const status=document.createElement('p');status.setAttribute('role','status');controls.appendChild(status);
    const list=document.createElement('div');list.style.cssText='display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:8px;margin:12px 0';controls.appendChild(list);
    const help=document.createElement('p');help.className='note';help.textContent='Checked barcodes contribute to overview graphs and pooled statistics. Individual barcode and read pages remain available. Selection is saved in this browser.';controls.appendChild(help);
    // Function: field.
    // Inputs: page (barcode page element); parent (parent element)
    // Outputs: Created barcode-control DOM element with its event listeners attached.
    const field=(page,parent)=>{
      const wrapper=document.createElement('label');wrapper.style.cssText='display:flex;gap:8px;align-items:center';
      const input=document.createElement('input');input.type='checkbox';input.checked=!excluded.has(page.id);input.dataset.barcodeId=page.id;
      const text=document.createElement('span');text.textContent=label(page.id);wrapper.append(input,text);parent.appendChild(wrapper);
      if(!inputs.has(page.id))inputs.set(page.id,[]);inputs.get(page.id).push({input,text});
      // Function: input.onchange.
      // Inputs: None; uses the current report/browser state.
      // Outputs: Handles the UI action and updates the associated report controls.
      input.onchange=()=>set(page.id,!input.checked);return wrapper;
    };
    for(const page of pages){field(page,list);const banner=document.createElement('div');banner.className='barcode-exclusion-banner';banner.style.cssText='margin:10px 0;padding:10px;border:1px solid #e4c18d;border-radius:6px';
      const checkbox=field(page,banner);checkbox.querySelector('span').textContent='Include this barcode in the overview';
      const message=document.createElement('span');banner.appendChild(message);messages.set(page.id,message);
      page.querySelector('.barcode-name-editor,.breadcrumbs')?.after(banner);
    }
    overview.querySelector('.barcode-navigation')?.after(controls);
    const style=document.createElement('style');style.textContent='.barcode-link[data-excluded="true"]{border-style:dashed;opacity:.75}.barcode-link[data-excluded="true"]::after{content:" · Excluded";font-weight:700;color:#9b4a16}.barcode-exclusion-controls button{padding:8px;margin:4px;border:1px solid #bdcde0;border-radius:6px;background:white;cursor:pointer}.barcode-exclusion-banner[data-excluded="true"]{background:#fff2de}.barcode-exclusion-banner span+span{margin-left:12px}';document.head.appendChild(style);
    // Function: persist.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Saves excluded IDs to browser storage, or shows a storage-status note.
    const persist=()=>{try{localStorage.setItem(key,JSON.stringify([...excluded]));}catch{help.textContent='Browser storage is unavailable. Selection applies until this dashboard is closed.';}};
    let busy=false,again=false;
    // Function: apply.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Promise completing after overview state and plots reflect barcode exclusions.
    const apply=async()=>{
      if(busy){again=true;return;}busy=true;
      try{
        for(const page of pages){
          const out=excluded.has(page.id);page.dataset.overviewExcluded=String(out);
          document.querySelectorAll('a.barcode-link[href="#/barcode/'+page.id+'"]').forEach(a=>a.dataset.excluded=String(out));
          for(const {input,text} of inputs.get(page.id)){input.checked=!out;if(input.closest('.barcode-exclusion-controls'))text.textContent=label(page.id);input.setAttribute('aria-label','Include '+label(page.id)+' in overview');}
          const message=messages.get(page.id);message.textContent=out?'Excluded from overview graphs and pooled statistics.':'Included in overview graphs and pooled statistics.';
          message.parentElement.dataset.excluded=String(out);
        }
        status.textContent=(pages.length-excluded.size)+' of '+pages.length+' barcodes included.'+(excluded.size?' Excluded: '+[...excluded].map(label).join(', ')+'.':' All barcodes are included.');
        summary.textContent='Include or exclude barcodes ('+(pages.length-excluded.size)+' / '+pages.length+' included)';
        // Do not redraw the original overview until the selection actually changes.
        if(!excluded.size&&!snapshots.size)return;
        updateStats();
        for(const graph of overview.querySelectorAll('.js-plotly-plot')){
          const snapshot=snapshotsFor(graph);if(!snapshot)continue;
          const figure=excluded.size?filterGraph(snapshot):clone(snapshot),section=graph.closest('section');
          // Function: currentLabel.
          // Inputs: value (value to inspect or format)
          // Outputs: Value with any recognized barcode identity replaced by its current display
          // label.
          const currentLabel=value=>{
            if(Array.isArray(value))return value.map(currentLabel);
            const id=resolve(value);return id?safe(label(id)):value;
          };
          for(const trace of figure.data)for(const field of ['name','x','y','text','labels'])if(trace[field]!=null)trace[field]=currentLabel(trace[field]);
          for(const axis of ['xaxis','yaxis'])if(figure.layout[axis])for(const field of ['ticktext','tickvals','categoryarray'])if(figure.layout[axis][field])figure.layout[axis][field]=currentLabel(figure.layout[axis][field]);
          for(const annotation of figure.layout.annotations||[])for(const field of ['text','x','y'])annotation[field]=currentLabel(annotation[field]);
          // Preserve current zoom scale and sizing while restoring the full underlying observations.
          for(const k of ['width','height','autosize'])if(graph.layout?.[k]!=null)figure.layout[k]=graph.layout[k];
          if(graph.layout?.yaxis?.type&&figure.layout.yaxis)figure.layout.yaxis.type=graph.layout.yaxis.type;
          if(figure.data.some(t=>t.type==='pie'))compositionGraph(figure,section);
          figure.layout.meta={...figure.layout.meta,barcodeSelection:{included:pages.filter(p=>!excluded.has(p.id)).map(p=>facts.get(p.id).barcode_id),excluded:[...excluded].map(id=>facts.get(id).barcode_id)}};
          if(excluded.size){
            figure.layout.annotations=figure.layout.annotations||[];
            figure.layout.annotations.push({name:'barcode-selection-scope',text:(pages.length-excluded.size)+' / '+pages.length+' barcodes included',xref:'paper',yref:'paper',x:1,y:1,xanchor:'right',yanchor:'top',showarrow:false,bgcolor:'#fff6e8',font:{size:11,color:'#8b4619'}});
            if(!included().length)figure.layout.annotations.push({name:'barcode-selection-empty',text:'No barcodes selected',xref:'paper',yref:'paper',x:.5,y:.5,showarrow:false});
          }
          await Plotly.react(graph,figure.data,figure.layout,{responsive:true,displaylogo:false});
        }
      }finally{busy=false;if(again){again=false;await apply();}}
    };
    // Function: set.
    // Inputs: id (stable barcode/read identity); out (whether to exclude this barcode)
    // Outputs: Overview-update promise after changing one barcode exclusion setting.
    const set=(id,out)=>{if(!facts.has(id))throw Error('Unknown barcode');if(out)excluded.add(id);else excluded.delete(id);persist();return apply();};
    // Function: includeAll.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Clears barcode exclusions and returns the overview-update promise.
    window.reportBarcodeExclusion={set,includeAll:()=>{excluded.clear();persist();return apply();},
      // Function: excluded.
      // Inputs: None; uses the current report/browser state.
      // Outputs: Array of excluded stable barcode identities.
      // Function: statistics.
      // Inputs: None; uses the current report/browser state.
      // Outputs: Current pooled overview statistics for the included barcodes.
      excluded:()=>[...excluded],statistics:()=>totals(included()),refresh:apply};
    // Names may change independently; update labels without recapturing a filtered baseline.
    document.addEventListener('change',event=>{if(event.target.matches('.barcode-name-editor input,.barcode-names input[type="text"],.barcode-names input[type="file"]'))setTimeout(apply,0);});
    window.reportBarcodeExclusion.ready=apply();
  };
  // Function: launch.
  // Inputs: None; uses the current report/browser state.
  // Outputs: Promise completing after barcode-exclusion controls initialize.
  const launch=async()=>{
    if(!document.getElementById('barcode-exclusion-data')){
      // Previously exported reports may finish their corrections in deferred jobs.
      const patches=[...document.scripts].filter(s=>s.textContent.length<50000&&!s.textContent.includes('window.reportBarcodeExclusion.ready=apply')).map(s=>s.textContent);
      const expectsShort=patches.some(s=>s.includes('const cutoffFor=page=>'));
      const expectsAverage=patches.some(s=>s.includes('reportAverageUpdated'));
      for(let attempt=0;attempt<200;attempt++){
        const pages=[...document.querySelectorAll('.barcode-page')];
        const shortReady=!expectsShort||(pages.every(p=>p.querySelector('.short-telomere-stat[data-compact-card="true"]'))&&document.querySelector('#run-overview .short-telomere-stat'));
        const graphs=[...document.querySelectorAll('#run-overview .js-plotly-plot')];
        const graphReady=graphs.every(g=>g.data&&g._fullLayout)&&(!expectsAverage||graphs.some(g=>g.reportAverageUpdated));
        if(shortReady&&graphReady)break;
        await new Promise(resolve=>setTimeout(resolve,25));
      }
      await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    }
    start();
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',launch,{once:true});else launch();
})();
