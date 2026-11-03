/* Offline scientific workbook: complete filtered read tables, not table-page exports. */
(() => {
  if(window.reportWorkbook?.version===8)return;
  const installation={};window.reportWorkbookInstallation=installation;
  const start=()=>{
    if(window.reportWorkbookInstallation!==installation)return;
    // Replace controls at initialization, after older DOM-ready callbacks ran.
    document.querySelectorAll('.report-workbook-controls').forEach(node=>node.remove());
    const overview=document.getElementById('run-overview');if(!overview)return;
    const pages=[...document.querySelectorAll('.barcode-page')],cache=new WeakMap();
    const unavailable='Unavailable',notApplicable='Not applicable';
    const valid=value=>typeof value==='number'&&Number.isFinite(value)&&value>=0;
    const scalar=value=>valid(value)?value:unavailable;
    let source=[];try{source=JSON.parse(document.getElementById('barcode-exclusion-data')?.textContent||'[]');}catch{}
    const count=(page,pattern)=>{
      const card=[...page.querySelectorAll('.stats>.stat')].find(el=>pattern.test(el.querySelector('h3')?.textContent.trim()||''));
      const text=card?.querySelector('strong')?.textContent.trim().replace(/,/g,'');
      return text&&/^\d+$/.test(text)?Number(text):null;
    };
    const rowsFor=page=>{
      if(!cache.has(page)){
        let rows=null;try{const value=JSON.parse(page.querySelector('script.read-data')?.textContent||'null');if(Array.isArray(value))rows=value;}catch{}
        cache.set(page,rows);
      }
      return cache.get(page);
    };
    const quantile=(sorted,p)=>{
      if(!sorted.length)return notApplicable;
      const position=(sorted.length-1)*p,low=Math.floor(position),fraction=position-low;
      return sorted[low]+fraction*((sorted[low+1]??sorted[low])-sorted[low]);
    };
    const identity=page=>{
      const entry=window.reportBarcodeNames?.entries().find(row=>row.id===page.dataset.barcodeId);
      return {id:page.dataset.barcodeId||source.find(row=>row.id===page.id)?.barcode_id||page.dataset.chartLabel?.replace(/^BC/i,'barcode')||page.dataset.label,
        name:page.dataset.displayName||entry?.name||''};
    };
    const excluded=id=>window.reportBarcodeExclusion?.excluded().includes(id)||document.getElementById(id)?.dataset.overviewExcluded==='true';
    const summaryFor=page=>{
      const records=rowsFor(page),fact=source.find(row=>row.id===page.id),who=identity(page);
      const total=valid(fact?.total)?fact.total:count(page,/^Total barcode reads$/);
      const filtered=valid(fact?.filtered)?fact.filtered:count(page,/^(?:Post-filtered|NanoTel final-filtered) telomeric reads$/);
      const rawCutoff=fact?.cutoff??page.dataset.shortCutoffBp??page.querySelector('.short-telomere-stat')?.dataset.cutoffBp;
      const parsed=Number(rawCutoff),cutoff=rawCutoff!=null&&rawCutoff!==''&&parsed>0&&Number.isFinite(parsed)?parsed:null;
      const complete=records!==null&&records.every(r=>valid(r.telomere))&&(filtered==null||filtered===records.length);
      const lengths=complete?records.map(r=>r.telomere).sort((a,b)=>a-b):null;
      const readLengths=records?.filter(r=>valid(r.length)).map(r=>r.length).sort((a,b)=>a-b);
      const kb=value=>typeof value==='number'?value/1000:value;
      const short=lengths&&cutoff!=null?lengths.filter(v=>v<cutoff).length:null;
      const coverage=records===null?'Read export unavailable':filtered==null?'Source count unavailable':records.length===filtered?'Complete':'Incomplete: exported reads differ from source count';
      const fraction=valid(total)&&total>0&&valid(filtered)&&filtered<=total?filtered/total:total===0?notApplicable:unavailable;
      const medianRead=records===null?unavailable:!records.length?notApplicable:readLengths.length===records.length?kb(quantile(readLengths,.5)):unavailable;
      return [who.id,who.name,excluded(page.id)?'No':'Yes',scalar(total),scalar(filtered),records===null?unavailable:records.length,
        fraction,lengths===null?unavailable:lengths.length?lengths.reduce((a,b)=>a+b,0)/lengths.length/1000:notApplicable,
        lengths===null?unavailable:kb(quantile(lengths,.5)),lengths===null?unavailable:kb(quantile(lengths,.25)),
        lengths===null?unavailable:kb(quantile(lengths,.75)),lengths===null?unavailable:lengths.length?lengths[0]/1000:notApplicable,
        lengths===null?unavailable:lengths.length?lengths[lengths.length-1]/1000:notApplicable,
        cutoff??unavailable,short??unavailable,lengths===null?unavailable:lengths.length,
        short==null?unavailable:lengths.length?short/lengths.length:notApplicable,
        medianRead,readLengths?.length??unavailable,coverage];
    };
    const readSheet=(page,before=false)=>{
      const filtered=rowsFor(page)||[];let extra=[];
      if(before)try{const value=JSON.parse(page.querySelector('script.read-details')?.textContent||'[]');if(Array.isArray(value))extra=value;}catch{}
      const seen=new Set(),records=(before?[...filtered,...extra]:filtered).filter(r=>{const id=r.id||r.header;if(id&&seen.has(id))return false;if(id)seen.add(id);return true;});
      const kb=v=>valid(v)?v/1000:unavailable,pct=v=>valid(v)?v/100:unavailable;
      const noTVR=page.dataset.tvrEnabled==='false',mismatch=page.dataset.mismatchEnabled==='true';
      const columns=[['Read number',r=>r.label||unavailable],['Read ID',r=>r.header||unavailable],
        ['Exact telomere length (kb)',r=>kb(r.exact_length),'decimal'],
        ...(noTVR?[
          [mismatch?'Telomere length (1 mismatch, kb)':'Filtered telomere length (kb)',r=>kb(mismatch?r.mismatch_length:r.telomere),'decimal'],
          ['Exact repeat density (%)',r=>scalar(r.exact_density),'percent'],
          ...(mismatch?[['Repeat density (1 mismatch, %)',r=>scalar(r.mismatch_density),'percent']]:[['TVR analysis',()=> 'Not requested']]),
          ['Read length (bp)',r=>scalar(r.length),'integer']
        ]:[
          ['Telomere length with TVRs (kb)',r=>kb(r.tvr_length),'decimal'],
          ['TVR content (%)',r=>pct(r.tvr),'percent'],
          ['Canonical content (%)',r=>pct(r.canonical),'percent'],
          ['TVR blocks',r=>scalar(r.blocks),'integer']
        ]),
        ['Mapping',r=>r.chromosomes?.length?r.chromosomes.join(', '):unavailable]];
      return {name:identity(page).id+(before?'_before_filter':''),headers:columns.map(c=>c[0]),formats:columns.map(c=>c[2]),freezeColumns:1,rows:records.map(r=>columns.map(c=>c[1](r)))};
    };
    const sheets=(scope='all')=>{
      const selected=pages.filter(p=>scope!=='included'||!excluded(p.id));
      if(!selected.length)throw Error('No included barcodes to export. Include a barcode or choose All barcodes.');
      const summaries=selected.map(summaryFor);
      const cardValue=(page,title)=>{
        const card=[...page.querySelectorAll('.stats>.stat')].find(el=>el.querySelector('h3')?.textContent.trim()===title);
        const text=card?.querySelector('strong')?.textContent.trim();
        const parsed=text?.replace(/,/g,'');
        return parsed&&/^\d+$/.test(parsed)?Number(parsed):text||unavailable;
      };
      const headers=['Barcode ID','Barcode display name','Total barcode reads',
        'Post-filtered telomeric reads','Median length (kb)','Reads with TVRs','TVR motifs','Chromosomes','Short telomeres (%)'];
      const rows=summaries.map((row,i)=>[row[0],row[1],row[3],row[4],row[8],
        cardValue(selected[i],'Reads with TVRs'),cardValue(selected[i],'TVR motifs'),cardValue(selected[i],'Chromosomes'),row[16]]);
      const formats=['','','integer','integer','decimal','integer','integer','integer','percent'];
      const cutoffs=[...new Set(summaries.map(r=>r[13]))];
      const cutoffDefinition=cutoffs.length===1&&typeof cutoffs[0]==='number'?
        'Length < '+cutoffs[0].toLocaleString('en-US')+' bp.':
        selected.map((p,i)=>identity(p).id+': '+(typeof summaries[i][13]==='number'?'length < '+summaries[i][13]+' bp':'cutoff unavailable')).join('; ');
      const definitions={name:'Definitions',headers:['Field','Definition'],widths:[38,110],rows:[
        ['Export scope',scope==='included'?'Included barcodes only.':'All barcodes, including excluded barcodes.'],
        ['Barcode sheets','Barcode summary contains barcode-level Key Statistics. Each barcode sheet lists individual post-filtered reads with their read-level Key Statistics. Before-filter sheets also include additional saved read details; these are not necessarily every input read.'],
        ['Telomere statistics','Computed from the exported filtered telomere lengths, in kb. These are the lengths used for the filtered population, not a substitution of exact or TVR-inclusive calls.'],
        ['Short telomeres',cutoffDefinition+' Length is strictly less than the recorded cutoff. The denominator is all exported post-filtered telomeric reads for that barcode. Missing lengths or a mismatch with the source count makes the statistic unavailable.'],
        ['Units','Telomere lengths: kb. Percent cells store fractions with Excel percentage formatting. Counts are integers.'],
        ['Unavailable and empty populations','Unavailable means a required value is missing or the population is incomplete. Not applicable means a statistic has no defined value, for example a median or percentage with zero reads. Zero counts remain numeric zero.'],
        ['TVR columns','TVR statistics are marked Not requested when TVR analysis was not requested. Missing measurements remain unavailable.'],
        ['Workbook snapshot','Values reflect the dashboard data and barcode names/selection when exported. Export again after changing the dashboard. Editing workbook values does not recalculate this snapshot.'],
        ['Source','Embedded read-data and barcode source-count/cutoff exports in this standalone NanoTel dashboard. Original barcode IDs are preserved.']
      ]};
      return [{name:'Barcode summary',headers,formats,freezeColumns:1,rows},...selected.map(p=>readSheet(p)),...selected.map(p=>readSheet(p,true)),definitions];
    };
    const workbook=(scope='all')=>{
      if(!window.reportTableExportFormats?.workbook)throw Error('Excel export is not ready. Reload the dashboard.');
      return window.reportTableExportFormats.workbook(sheets(scope));
    };
    window.reportWorkbook={version:8,sheets,workbook};
    const controls=document.createElement('div');controls.className='report-workbook-controls';
    controls.style.cssText='display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:14px 0';
    const select=document.createElement('select');select.setAttribute('aria-label','Excel workbook barcode scope');
    for(const [value,label] of [['all','All barcodes'],['included','Included barcodes only']]){const option=document.createElement('option');option.value=value;option.textContent=label;select.appendChild(option);}
    const button=document.createElement('button');button.type='button';button.textContent='Export Excel workbook';
    button.style.cssText='padding:8px 12px;border:1px solid #b8cbea;border-radius:7px;background:white;color:#2456a6;cursor:pointer;font-weight:600';
    select.style.cssText='padding:7px 10px;border:1px solid #ccd8e8;border-radius:6px;background:white';
    const status=document.createElement('span');status.setAttribute('role','status');status.style.fontSize='13px';
    button.onclick=async()=>{
      button.disabled=true;status.textContent='Preparing barcode summary and read Key Statistics...';
      try{
        if(window.reportBarcodeExclusion?.ready)await window.reportBarcodeExclusion.ready;
        await new Promise(resolve=>setTimeout(resolve,0));
        const bytes=workbook(select.value),blob=new Blob([bytes],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
        const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;
        link.download=select.value==='included'?'NanoTel_included_barcodes.xlsx':'NanoTel_all_barcodes.xlsx';
        document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);
        status.textContent='Workbook saved: barcode summary and read Key Statistics per barcode.';
      }catch(error){status.textContent=error.message||'Excel export failed.';}finally{button.disabled=false;}
    };
    controls.append(button,select,status);
    const stats=overview.querySelector('.stats')?.closest('section');
    if(stats){const heading=stats.querySelector('h2');heading?.after(controls);}else overview.appendChild(controls);
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
