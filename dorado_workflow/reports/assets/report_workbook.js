/* Offline scientific workbook: complete filtered read tables, not table-page exports. */
(() => {
  if(window.reportWorkbook?.version===9)return;
  const installation={};window.reportWorkbookInstallation=installation;
  // Function: start.
  // Inputs: None; uses the current report/browser state.
  // Outputs: Initializes this report feature and registers its event listeners.
  const start=()=>{
    if(window.reportWorkbookInstallation!==installation)return;
    // Replace controls at initialization, after older DOM-ready callbacks ran.
    document.querySelectorAll('.report-workbook-controls').forEach(node=>node.remove());
    const overview=document.getElementById('run-overview');if(!overview)return;
    const pages=[...document.querySelectorAll('.barcode-page')],cache=new WeakMap();
    const unavailable='Unavailable',notApplicable='Not applicable';
    // Function: valid.
    // Inputs: value (value to inspect or format)
    // Outputs: True for a finite nonnegative number; false otherwise.
    const valid=value=>typeof value==='number'&&Number.isFinite(value)&&value>=0;
    // Function: scalar.
    // Inputs: value (value to inspect or format)
    // Outputs: Valid numeric input, otherwise the explicit missing-value marker.
    const scalar=value=>valid(value)?value:unavailable;
    let source=[];try{source=JSON.parse(document.getElementById('barcode-exclusion-data')?.textContent||'[]');}catch{}
    // Function: count.
    // Inputs: page (barcode page element); pattern (statistic-heading matcher)
    // Outputs: Parsed count from the matching barcode statistic card, or null.
    const count=(page,pattern)=>{
      const card=[...page.querySelectorAll('.stats>.stat')].find(el=>pattern.test(el.querySelector('h3')?.textContent.trim()||''));
      const text=card?.querySelector('strong')?.textContent.trim().replace(/,/g,'');
      return text&&/^\d+$/.test(text)?Number(text):null;
    };
    // Function: rowsFor.
    // Inputs: page (barcode page element)
    // Outputs: Cached embedded read records for the barcode page, or null when absent.
    const rowsFor=page=>{
      if(!cache.has(page)){
        let rows=null;try{const value=JSON.parse(page.querySelector('script.read-data')?.textContent||'null');if(Array.isArray(value))rows=value;}catch{}
        cache.set(page,rows);
      }
      return cache.get(page);
    };
    // Function: quantile.
    // Inputs: sorted (sorted observations); p (quantile fraction)
    // Outputs: Linearly interpolated quantile, or Not applicable for an empty population.
    const quantile=(sorted,p)=>{
      if(!sorted.length)return notApplicable;
      const position=(sorted.length-1)*p,low=Math.floor(position),fraction=position-low;
      return sorted[low]+fraction*((sorted[low+1]??sorted[low])-sorted[low]);
    };
    // Function: identity.
    // Inputs: page (barcode page element)
    // Outputs: Original barcode ID and current custom display name.
    const identity=page=>{
      const entry=window.reportBarcodeNames?.entries().find(row=>row.id===page.dataset.barcodeId);
      return {id:page.dataset.barcodeId||source.find(row=>row.id===page.id)?.barcode_id||page.dataset.chartLabel?.replace(/^BC/i,'barcode')||page.dataset.label,
        name:page.dataset.displayName||entry?.name||''};
    };
    // Function: excluded.
    // Inputs: id (stable barcode/read identity)
    // Outputs: True when the barcode is excluded from overview graphs/statistics.
    const excluded=id=>window.reportBarcodeExclusion?.excluded().includes(id)||document.getElementById(id)?.dataset.overviewExcluded==='true';
    // Function: readSheet.
    // Inputs: page (barcode page element); before (whether to use before-filter read records)
    // Outputs: Worksheet descriptor containing the selected before/after-filter read rows.
    const readSheet=(page,before=true)=>{
      const filtered=rowsFor(page)||[];let extra=[];
      if(before)try{const value=JSON.parse(page.querySelector('script.read-details')?.textContent||'[]');if(Array.isArray(value))extra=value;}catch{}
      const seen=new Set(),records=(before?[...filtered,...extra]:filtered).filter(r=>{const id=r.id||r.header;if(id&&seen.has(id))return false;if(id)seen.add(id);return true;});
      // Function: kb.
      // Inputs: v (value to inspect or format)
      // Outputs: Numeric length in kilobases, or the missing-value marker.
      // Function: pct.
      // Inputs: v (value to inspect or format)
      // Outputs: Percentage converted to an Excel fractional value, or the missing marker.
      const kb=v=>valid(v)?v/1000:unavailable,pct=v=>valid(v)?v/100:unavailable;
      const noTVR=page.dataset.tvrEnabled==='false',mismatch=page.dataset.mismatchEnabled==='true';
      const retained=new Set(filtered.map(row=>row.id));
      const columns=[['Read number',r=>r.label||unavailable],['Read ID',r=>r.header||unavailable],
        ['Filtration status',r=>rowsFor(page)==null?'Unavailable':retained.has(r.id)?'Passed':'Not retained'],
        ['Exact telomere length (kb)',r=>kb(r.exact_length),'decimal'],
        ['Exact repeat density (%)',r=>scalar(r.exact_density),'percent'],
        ...(mismatch?[
          ['Telomere length (1 mismatch, kb)',r=>kb(r.mismatch_length),'decimal'],
          ['Repeat density (1 mismatch, %)',r=>scalar(r.mismatch_density),'percent']]:[]),
        ...(!noTVR?[
          ['Telomere length with TVRs (kb)',r=>kb(r.tvr_length),'decimal'],
          ['TVR content (%)',r=>pct(r.tvr),'percent'],
          ['Canonical content (%)',r=>pct(r.canonical),'percent'],
          ['TVR blocks',r=>scalar(r.blocks),'integer']]:[]),
        ['Read length (bp)',r=>scalar(r.length),'integer'],
        ['Mapping',r=>r.chromosomes?.length?r.chromosomes.join(', '):unavailable]];
      return {name:identity(page).id,headers:columns.map(c=>c[0]),formats:columns.map(c=>c[2]),freezeColumns:1,rows:records.map(r=>columns.map(c=>c[1](r)))};
    };
    // Function: sheets.
    // Inputs: scope (all or included barcodes)
    // Outputs: Worksheet descriptors for the requested barcode scope.
    const sheets=(scope='all')=>{
      const selected=pages.filter(p=>scope!=='included'||!excluded(p.id));
      if(!selected.length)throw Error('No included barcodes to export. Include a barcode or choose All barcodes.');
      const cutoffs=new Set(selected.map(page=>source.find(row=>row.id===page.id)?.cutoff).filter(valid));
      const cutoffDefinition=cutoffs.size===1?'Recorded cutoff: '+[...cutoffs][0]+' bp.':'Per-barcode recorded cutoffs are used.';
      // Function: cardValue.
      // Inputs: page (barcode page element); title (displayed heading)
      // Outputs: Displayed statistic value from the matching barcode card.
      const cardValue=(page,title)=>{
        const card=[...page.querySelectorAll('.stats>.stat')].find(el=>el.querySelector('h3')?.textContent.trim()===title);
        const text=card?.querySelector('strong')?.textContent.trim();
        const parsed=text?.replace(/,/g,'');
        return parsed&&/^\d+$/.test(parsed)?Number(parsed):text||unavailable;
      };
      const headers=['Barcode ID','Total number of reads','Measurement method',
        'Telomeric reads before filtration','Post-filtered telomeric reads',
        'Measured lengths before filtration','Measured lengths after filtration',
        'Median telomere length before filtration (kb)',
        'Short telomeres before filtration (%)','Short telomeres after filtration (%)',
        'Short telomere cutoff (bp)','Number of reads with TVRs before filtration',
        'Number of reads with TVRs after filtration','Chromosomes'];
      const formats=headers.map((_,i)=>i===7?'decimal':[8,9].includes(i)?'percent':null);
      const rows=selected.flatMap(page=>{
        const fact=source.find(row=>row.id===page.id)||{};
        const number=(entry,key,scale=1)=>entry?.requested===false?'Not requested':valid(entry?.[key])?entry[key]/scale:unavailable;
        return [['exact','Without mismatch or TVR'],['mismatch','With mismatch, without TVR'],
                ['tvr_inclusive',page.dataset.mismatchEnabled==='false'?'With TVR, without mismatch':'With mismatch and TVR']].map(([method,label])=>{
          const measurement=fact.measurements?.[method],before=measurement?.before,after=measurement?.after;
          return [identity(page).id,scalar(fact.total),label,scalar(before?.records),scalar(fact.filtered),
            number(before,'measured'),number(after,'measured'),number(before,'median_bp',1000),
            number(before,'short_percent',100),number(after,'short_percent',100),scalar(fact.cutoff),
            fact.tvr_counts?.before??unavailable,fact.tvr_counts?.after??unavailable,
            fact.chromosomes?.length||unavailable];
        });
      });
      const definitions={name:'Definitions',headers:['Field','Definition'],widths:[38,110],rows:[
        ['Export scope',scope==='included'?'Included barcodes only.':'All barcodes, including excluded barcodes.'],
        ['Barcode sheets','Barcode summary contains barcode-level Key Statistics. Each barcode sheet combines detected source reads with their filtration status; these are not necessarily every input read.'],
        ['Telomere statistics','Median telomere lengths use before-filtration source measurements only. Exact, mismatch and TVR-inclusive methods are distinct recorded calls.'],
        ['Short telomeres',cutoffDefinition+' Length is strictly less than the cutoff. Before/after percentages use the non-missing measured lengths for that method and population as denominator. No additional filtering or repeat search is performed.'],
        ['Units','Telomere lengths: kb. Percent cells store fractions with Excel percentage formatting. Counts are integers.'],
        ['Unavailable and empty populations','Unavailable means a required value is missing or the population is incomplete. Not applicable means a statistic has no defined value, for example a median or percentage with zero reads. Zero counts remain numeric zero.'],
        ['TVR columns','TVR statistics are marked Not requested when TVR analysis was not requested. Missing measurements remain unavailable.'],
        ['Workbook snapshot','Values reflect the dashboard data and barcode names/selection when exported. Export again after changing the dashboard. Editing workbook values does not recalculate this snapshot.'],
        ['Source','Embedded read-data and barcode source-count/cutoff exports in this standalone NanoTel dashboard. Original barcode IDs are preserved.']
      ]};
      return [{name:'Barcode summary',headers,formats,freezeColumns:3,rows},...selected.map(p=>readSheet(p,true)),definitions];
    };
    // Function: workbook.
    // Inputs: scope (all or included barcodes)
    // Outputs: Uint8Array containing a standalone XLSX workbook.
    const workbook=(scope='all')=>{
      if(!window.reportTableExportFormats?.workbook)throw Error('Excel export is not ready. Reload the dashboard.');
      return window.reportTableExportFormats.workbook(sheets(scope));
    };
    window.reportWorkbook={version:9,sheets,workbook};
    const controls=document.createElement('div');controls.className='report-workbook-controls';
    controls.style.cssText='display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:14px 0';
    const select=document.createElement('select');select.setAttribute('aria-label','Excel workbook barcode scope');
    for(const [value,label] of [['all','All barcodes'],['included','Included barcodes only']]){const option=document.createElement('option');option.value=value;option.textContent=label;select.appendChild(option);}
    const button=document.createElement('button');button.type='button';button.textContent='Export Excel workbook';
    button.style.cssText='padding:8px 12px;border:1px solid #b8cbea;border-radius:7px;background:white;color:#2456a6;cursor:pointer;font-weight:600';
    select.style.cssText='padding:7px 10px;border:1px solid #ccd8e8;border-radius:6px;background:white';
    const status=document.createElement('span');status.setAttribute('role','status');status.style.fontSize='13px';
    // Function: button.onclick.
    // Inputs: None; uses the current report/browser state.
    // Outputs: Promise completing after the selected UI action finishes.
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
