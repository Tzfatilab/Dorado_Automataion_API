/* Offline scientific workbook: complete filtered read tables, not table-page exports. */
(() => {
  if(window.reportWorkbook?.version===13)return;
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
    const cutoffFor=page=>window.reportShortCutoff?.cutoffFor(page)??source.find(row=>row.id===page.id)?.cutoff;
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
      const noTVR=page.dataset.tvrEnabled==='false',withTSQ=page.dataset.tsqEnabled==='true',mismatch=page.dataset.mismatchEnabled==='true';
      const retained=new Set(filtered.map(row=>row.id));
      const columns=[['Read number',r=>r.label||unavailable],['Read ID',r=>r.header||unavailable],
        ['Total read length (kb)',r=>kb(r.length),'decimal'],
        ['Telomere start (bp)',r=>scalar(mismatch?r.mismatch_start:r.canonical_start),'integer'],
        ['Filtration status',r=>rowsFor(page)==null?'Unavailable':retained.has(r.id)?'Passed':'Filtered out'],
        ['Filtration reason',r=>retained.has(r.id)?'-':window.reportShortFilterReason(r.filtration_reason||r.filter_reason||unavailable)],
        ['Canonical telomere length (kb)',r=>kb(r.exact_length),'decimal'],
        ...(mismatch?[[ 'Telomere length including mismatch (kb)',r=>kb(r.mismatch_length),'decimal']]:[]),
        ...(!noTVR?[[ 'Telomere length including TVRs (kb)',r=>kb(r.tvr_length),'decimal']]:[]),
        ...(withTSQ?[[ 'Telomere length including TSQ (kb)',r=>kb(r.tsq_length),'decimal'],['TSQ content (%)',r=>pct(r.tsq),'percent']]:[]),
        ['Canonical repeat density (%)',r=>scalar(r.exact_density),'percent'],
        ...(mismatch?[[ 'Repeat density including mismatch (%)',r=>scalar(r.mismatch_density),'percent']]:[]),
        ...(!noTVR?[
          ['TVR content (%)',r=>pct(r.tvr),'percent'],
          ['Canonical content (%)',r=>pct(r.canonical),'percent'],
          ['TVR patterns',r=>Array.isArray(r.tvr_patterns)?r.tvr_patterns.join(', '):unavailable]]:[]),
        ['Chromosome',r=>r.chromosomes?.length?r.chromosomes.join(', '):unavailable]];
      return {name:identity(page).id,headers:columns.map(c=>c[0]),formats:columns.map(c=>c[2]),freezeColumns:1,rows:records.map(r=>columns.map(c=>c[1](r)))};
    };
    // Function: sheets.
    // Inputs: scope (all or included barcodes)
    // Outputs: Worksheet descriptors for the requested barcode scope.
    const sheets=(scope='all')=>{
      const selected=pages.filter(p=>scope!=='included'||!excluded(p.id));
      if(!selected.length)throw Error('No included barcodes to export. Include a barcode or choose All barcodes.');
      const cutoffs=new Set(selected.map(page=>cutoffFor(page)).filter(valid));
      const cutoffDefinition=cutoffs.size===1?'Dashboard cutoff: '+[...cutoffs][0]+' bp.':'Per-barcode recorded cutoffs are used.';
      // Function: cardValue.
      // Inputs: page (barcode page element); title (displayed heading)
      // Outputs: Displayed statistic value from the matching barcode card.
      const cardValue=(page,title)=>{
        const card=[...page.querySelectorAll('.stats>.stat')].find(el=>el.querySelector('h3')?.textContent.trim()===title);
        const text=card?.querySelector('strong')?.textContent.trim();
        const parsed=text?.replace(/,/g,'');
        return parsed&&/^\d+$/.test(parsed)?Number(parsed):text||unavailable;
      };
      const methods=[['exact','Canonical']];
      if(selected.some(page=>page.dataset.mismatchEnabled==='true'))methods.push(['mismatch','Including mismatch']);
      const includeTSQ=selected.some(page=>page.dataset.tsqEnabled==='true');
      const includeTVR=selected.some(page=>page.dataset.tvrEnabled!=='false');
      if(includeTVR)methods.push(['tvr_inclusive',
        selected.every(page=>page.dataset.mismatchEnabled==='false')?'Including TVRs (without mismatch)':
        selected.every(page=>page.dataset.mismatchEnabled==='true')?'Including TVRs (with mismatch)':'Including TVRs (run matching settings)']);
      if(selected.some(page=>page.dataset.tsqEnabled==='true'))methods.push(['tsq_inclusive','Including TSQ']);
      const cutoffTitle=cutoffs.size===1&&selected.every(page=>valid(cutoffFor(page)))?
        'telomere length < '+[...cutoffs][0]+' bp':'per-barcode cutoff; see Definitions';
      const methodFields=[['Median telomere length after filtration (kb)','median_bp',1000],
        ['Short telomeres after filtration (%, '+cutoffTitle+')','short_percent',100]];
      const headers=['Barcode ID','Sample name','Total number of reads','Median total read length (kb)',
        'Telomeric reads before filtration','Telomeric reads before filtration (%)',
        'Median total read length of telomeric reads before filtration (kb)','Number of telomeric reads after filtration',
        ...methodFields.flatMap(([title])=>methods.map(([,label])=>title+' - '+label)),
        ...(includeTVR?['Telomeric reads containing TVRs after filtration (%)']:[]),...(includeTSQ?['Telomeric reads containing TSQ after filtration (%)']:[]),'Number of chromosome ends'];
      const topHeaders=[...headers],subHeaders=headers.map(()=>null),merges=[];
      const groupedEnd=8+2*methods.length;
      for(let c=0;c<headers.length;c++)if(c<8||c>=groupedEnd)merges.push([c,0,c,1]);
      methodFields.forEach(([title],group)=>{
        const start=8+group*methods.length;
        methods.forEach(([,label],i)=>{topHeaders[start+i]=i===0?title:null;subHeaders[start+i]=label;});
        if(methods.length>1)merges.push([start,0,start+methods.length-1,0]);
      });
      const widths=headers.map((title,i)=>i>=8&&i<groupedEnd?26:Math.min(44,Math.max(15,title.length+2)));
      const formats=[null,null,null,'decimal',null,'percent','decimal',null,
        ...methodFields.flatMap(([,key])=>methods.map(()=>key==='median_bp'?'decimal':'percent')),
        ...(includeTVR?['percent']:[]),...(includeTSQ?['percent']:[]),null];
      const rows=selected.map(page=>{
        const fact=source.find(row=>row.id===page.id)||{},stats=fact.table_statistics||{};
        const scaled=(v,scale=1)=>valid(v)?v/scale:v==='Not requested'?v:unavailable;
        const number=(entry,key,scale=1)=>entry?.requested===false?'Not requested':scaled(entry?.[key],scale);
        return [identity(page).id,identity(page).name||stats.sample_name||'',scalar(fact.total),
          scaled(stats.total_read_length_median_bp,1000),scalar(stats.detected_reads),scaled(stats.detected_percent,100),
          scaled(stats.detected_read_length_median_bp,1000),scalar(fact.filtered),
          ...methodFields.flatMap(([,key,scale])=>methods.map(([method])=>number(key==='short_percent'&&window.reportShortCutoff?{...fact.measurements?.[method]?.after,short_percent:window.reportShortCutoff.percentage(fact.measurements?.[method]?.after,cutoffFor(page))}:fact.measurements?.[method]?.after,key,scale))),
          ...(includeTVR?[scaled(stats.tvr_read_percent_after,100)]:[]),
          ...(includeTSQ?[scaled(stats.tsq_read_percent_after,100)]:[]),
          Array.isArray(fact.chromosomes)&&(fact.chromosomes.length||fact.filtered===0)?fact.chromosomes.length:unavailable];
      });
      const definitions={name:'Definitions',headers:['Field','Definition'],widths:[38,110],rows:[
        ['Export scope',scope==='included'?'Included barcodes only.':'All barcodes, including excluded barcodes.'],
        ['Barcode sheets','Barcode summary contains barcode-level Key Statistics. Each barcode sheet combines detected source reads with their filtration status; these are not necessarily every input read.'],
        ['TSQ and TVR separation','Independent canonical-inclusive telomere calls. TSQ% and TVR% share the combined telomere interval; TSQ-covered bases are excluded from ordinary TVR base coverage. Legacy combined lengths are not split by inference.'],
        ['Telomere statistics','Median telomere lengths use after-filtration source measurements only. Canonical, mismatch and TVR-inclusive methods are distinct recorded calls.'],
        ['Short telomeres',cutoffDefinition+' Telomere length is strictly less than the cutoff. After-filtration percentages use the non-missing measured telomere lengths for that method and population as denominator. No additional filtering or repeat search is performed.'],
        ['Units','Telomere lengths: kb. Percent cells store fractions with Excel percentage formatting. Counts are integers.'],
        ['Unavailable and empty populations','Unavailable means a required value is missing or the population is incomplete. Not applicable means a statistic has no defined value, for example a median or percentage with zero reads. Zero counts remain numeric zero.'],
        ['TVR-positive reads (%)','Retained telomeric reads containing at least one TVR divided by all retained telomeric reads. This is a read percentage, not a base percentage.'],
        ['Total read length medians','All input reads for Median total read length; detected telomeric reads before filtration for Median total read length of telomeric reads.'],
        ...selected.map(page=>['Short cutoff - '+identity(page).id,String(cutoffFor(page)??unavailable)+' bp']),
        ['TVR columns','TVR statistics are marked Not requested when TVR analysis was not requested. Missing measurements remain unavailable.'],
        ['Workbook snapshot','Values reflect the dashboard data and barcode names/selection when exported. Export again after changing the dashboard. Editing workbook values does not recalculate this snapshot.'],
        ['Source','Embedded read-data and barcode source-count/cutoff exports in this standalone NanoTel dashboard. Original barcode IDs are preserved.']
      ]};
      return [{name:'Barcode summary',headers,headerRows:[topHeaders,subHeaders],merges,widths,formats,freezeColumns:2,rows},...selected.map(p=>readSheet(p,true)),definitions];
    };
    // Function: workbook.
    // Inputs: scope (all or included barcodes)
    // Outputs: Uint8Array containing a standalone XLSX workbook.
    const workbook=(scope='all')=>{
      if(!window.reportTableExportFormats?.workbook)throw Error('Excel export is not ready. Reload the dashboard.');
      return window.reportTableExportFormats.workbook(sheets(scope));
    };
    window.reportWorkbook={version:13,sheets,workbook};
    const controls=document.createElement('div');controls.className='report-workbook-controls';
    controls.style.cssText='display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:14px 0';
    const select=document.createElement('select');select.setAttribute('aria-label','Excel workbook barcode scope');
    for(const [value,label] of [['all','All barcodes'],['included','Included barcodes only']]){const option=document.createElement('option');option.value=value;option.textContent=label;select.appendChild(option);}
    const button=document.createElement('button');button.type='button';button.textContent='Save Excel';
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
    controls.append(select,button,status);
    const stats=overview.querySelector('.barcode-statistics-section');
    if(stats){
      const heading=stats.querySelector('.barcode-statistics-heading');
      if(heading)heading.insertBefore(controls,heading.querySelector('.table-export-controls'));
      else stats.prepend(controls);
    }else overview.appendChild(controls);
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
