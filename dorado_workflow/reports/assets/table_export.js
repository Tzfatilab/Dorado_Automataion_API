/* Offline CSV and genuine XLSX exports; no network or spreadsheet formulas. */
(() => {
  if(window.reportTableExportInstalled==='v6')return;
  window.reportTableExportObserver?.disconnect();
  document.querySelectorAll('.table-export-controls').forEach(node=>node.remove());
  window.reportTableExportInstalled='v6';
  const encoder=new TextEncoder(),attached=new WeakSet();
  // Function: text.
  // Inputs: value (value to inspect or format)
  // Outputs: Text representation of the value; missing values become empty text.
  const text=value=>value==null?'':String(value);
  // Function: xml.
  // Inputs: value (value to inspect or format)
  // Outputs: XML-escaped text with invalid XML control characters removed.
  const xml=value=>text(value).replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g,'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
  // Function: csv.
  // Inputs: data (source/presentation data)
  // Outputs: UTF-8-BOM CSV text with properly quoted cell values.
  const csv=data=>'\uFEFF'+[data.headers,...data.rows].map(row=>row.map(value=>{
    let cell=text(value);
    if(typeof value!=='number' && /^[\s\u0000-\u001f]*[=+@-]/.test(cell))cell="'"+cell;
    return /[",\r\n]/.test(cell)?'"'+cell.replace(/"/g,'""')+'"':cell;
  }).join(',')).join('\r\n')+'\r\n';
  const crcTable=Uint32Array.from({length:256},(_,n)=>{
    for(let bit=0;bit<8;bit++)n=n&1?0xEDB88320^(n>>>1):n>>>1;
    return n>>>0;
  });
  // Function: crc32.
  // Inputs: bytes (input byte array)
  // Outputs: Unsigned CRC-32 checksum of the bytes.
  const crc32=bytes=>{let crc=0xFFFFFFFF;for(const byte of bytes)crc=crcTable[(crc^byte)&255]^(crc>>>8);return (crc^0xFFFFFFFF)>>>0;};
  // Function: join.
  // Inputs: arrays (ordered byte arrays)
  // Outputs: Uint8Array containing all supplied byte arrays in order.
  const join=arrays=>{const result=new Uint8Array(arrays.reduce((sum,a)=>sum+a.length,0));let offset=0;for(const a of arrays){result.set(a,offset);offset+=a.length;}return result;};
  // Function: zip.
  // Inputs: files (ZIP entries keyed by path)
  // Outputs: Uint8Array containing the uncompressed ZIP entries and central directory.
  const zip=files=>{
    // XLSX is a ZIP package; stored entries keep offline exports dependency-free.
    const entries=[],directory=[];let offset=0;
    for(const [path,contents] of Object.entries(files)){
      const name=encoder.encode(path),bytes=encoder.encode(contents),crc=crc32(bytes);
      const local=new Uint8Array(30+name.length),l=new DataView(local.buffer);
      l.setUint32(0,0x04034B50,true);l.setUint16(4,20,true);l.setUint16(6,0x800,true);l.setUint16(12,33,true);
      l.setUint32(14,crc,true);l.setUint32(18,bytes.length,true);l.setUint32(22,bytes.length,true);l.setUint16(26,name.length,true);local.set(name,30);
      const central=new Uint8Array(46+name.length),c=new DataView(central.buffer);
      c.setUint32(0,0x02014B50,true);c.setUint16(4,20,true);c.setUint16(6,20,true);c.setUint16(8,0x800,true);c.setUint16(14,33,true);
      c.setUint32(16,crc,true);c.setUint32(20,bytes.length,true);c.setUint32(24,bytes.length,true);c.setUint16(28,name.length,true);c.setUint32(42,offset,true);central.set(name,46);
      entries.push(local,bytes);directory.push(central);offset+=local.length+bytes.length;
    }
    const central=join(directory),end=new Uint8Array(22),view=new DataView(end.buffer);
    view.setUint32(0,0x06054B50,true);view.setUint16(8,directory.length,true);view.setUint16(10,directory.length,true);
    view.setUint32(12,central.length,true);view.setUint32(16,offset,true);
    return join([...entries,central,end]);
  };
  // Function: columnName.
  // Inputs: index (zero-based index)
  // Outputs: Excel column label for the zero-based column index.
  const columnName=index=>{let label='';for(index++;index;index=Math.floor((index-1)/26))label=String.fromCharCode(65+(index-1)%26)+label;return label;};
  // Function: workbook.
  // Inputs: input (worksheet descriptor or descriptor list)
  // Outputs: Uint8Array containing a standalone XLSX workbook.
  const workbook=input=>{
    const sheets=Array.isArray(input)?input:[input];
    if(!sheets.length)throw Error('There are no worksheets to export.');
    const declaration='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
    const ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';
    const used=new Set(),names=[];
    for(const data of sheets){
      if(!data.headers.length)throw Error('This table has no columns to export.');
      if(data.rows.length>1048575||data.headers.length>16384)throw Error('This table exceeds the Excel worksheet size limit. Save CSV instead.');
      const base=(data.name||'Table').replace(/[\\/*?:\[\]\x00-\x1f]/g,' ').replace(/^'+|'+$/g,'').trim().slice(0,31)||'Table';
      let name=base,index=2;
      while(used.has(name.toLowerCase())){const suffix='_'+index++;name=base.slice(0,31-suffix.length)+suffix;}
      used.add(name.toLowerCase());names.push(name);
    }
    const files={
      '[Content_Types].xml':declaration+'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'+sheets.map((_,i)=>'<Override PartName="/xl/worksheets/sheet'+(i+1)+'.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>').join('')+'<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
      '_rels/.rels':declaration+'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
      'xl/workbook.xml':declaration+`<workbook xmlns="${ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${names.map((name,i)=>`<sheet name="${xml(name)}" sheetId="${i+1}" r:id="rId${i+1}"/>`).join('')}</sheets></workbook>`,
      'xl/_rels/workbook.xml.rels':declaration+'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+sheets.map((_,i)=>'<Relationship Id="rId'+(i+1)+'" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet'+(i+1)+'.xml"/>').join('')+'<Relationship Id="rId'+(sheets.length+1)+'" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
      'xl/styles.xml':declaration+`<styleSheet xmlns="${ns}"><numFmts count="4"><numFmt numFmtId="164" formatCode="0.##########"/><numFmt numFmtId="165" formatCode="#,##0"/><numFmt numFmtId="166" formatCode="#,##0.000"/><numFmt numFmtId="167" formatCode="0.0%"/></numFmts><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF18324D"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="6"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="166" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="167" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>`
    };
    sheets.forEach((data,index)=>{
      const rows=[data.headers,...data.rows],last=columnName(data.headers.length-1)+rows.length;
      const widths=data.headers.map((header,column)=>data.widths?.[column]||Math.min(44,Math.max(13,text(header).length+2,...data.rows.slice(0,500).map(row=>Math.min(40,text(row[column]).length+2)))));
      // Function: cell.
      // Inputs: value (value to inspect or format); column (zero-based column index); row (row)
      // Outputs: Worksheet cell XML preserving numeric types and text values.
      const cell=(value,column,row)=>{
        const reference=columnName(column)+(row+1);
        if(typeof value==='number'&&Number.isFinite(value)){
          const style={integer:3,decimal:4,percent:5}[data.formats?.[column]]||2;
          return `<c r="${reference}" s="${row?style:1}"><v>${value}</v></c>`;
        }
        if(text(value).length>32767)throw Error('A cell exceeds Excel\u2019s text limit. Save CSV instead.');
        return `<c r="${reference}" s="${row?0:1}" t="inlineStr"><is><t xml:space="preserve">${xml(value)}</t></is></c>`;
      };
      const frozen=Math.max(0,Math.min(data.freezeColumns||0,data.headers.length-1));
      const first=columnName(frozen)+'2';
      const pane=`<pane${frozen?' xSplit="'+frozen+'"':''} ySplit="1" topLeftCell="${first}" activePane="${frozen?'bottomRight':'bottomLeft'}" state="frozen"/>`;
      files['xl/worksheets/sheet'+(index+1)+'.xml']=declaration+`<worksheet xmlns="${ns}"><dimension ref="A1:${last}"/><sheetViews><sheetView workbookViewId="0">${pane}</sheetView></sheetViews><cols>${widths.map((width,i)=>`<col min="${i+1}" max="${i+1}" width="${width}" customWidth="1"/>`).join('')}</cols><sheetData>${rows.map((row,i)=>`<row r="${i+1}"${i===0?' ht="54" customHeight="1"':''}>${row.map((value,column)=>cell(value,column,i)).join('')}</row>`).join('')}</sheetData><autoFilter ref="A1:${last}"/></worksheet>`;
    });
    return zip(files);
  };
  // Function: contextName.
  // Inputs: table (table element)
  // Outputs: Contextual export filename/title for the selected table.
  const contextName=table=>{
    const heading=table.closest('section,details')?.querySelector('h3,h2,summary')?.cloneNode(true);
    heading?.querySelectorAll('.number').forEach(n=>n.remove());
    const detail=table.closest('#read-detail');
    const barcode=detail?.dataset.barcodeLabel||table.closest('.barcode-page')?.dataset.label||
      [...(detail?.querySelectorAll('.breadcrumbs a')||[])].find(a=>/^#\/barcode\/[^/]+$/.test(a.getAttribute('href')))?.textContent;
    const read=detail?.dataset.readLabel||detail?.querySelector('.read-summary-identity h2')?.textContent;
    let title=heading?.textContent.trim()||'Table';
    if(table.closest('.read-browser'))title='Read Information';
    else if(table.matches('.read-tvr-table'))title='TVR and Unassigned Regions';
    else title=title.replace(/\s*\([^)]*\)/g,'').replace(/\s*\d+\s+(?:telomeric\s+)?reads\b/gi,'').trim();
    return [title,barcode,read].filter(Boolean).join(' ');
  };
  // Function: domData.
  // Inputs: table (table element)
  // Outputs: Table headers and rows recovered from the current DOM/export adapter.
  const domData=table=>{
    const grid=[];
    [...table.rows].filter(row=>row.dataset.overviewExcluded!=='true').forEach((row,index)=>{
      grid[index]||=[];let column=0;
      for(const cell of row.cells){
        while(grid[index][column]!==undefined)column++;
        const value=cell.textContent.replace(/\s*[▾↕]$/,'').trim();
        for(let down=0;down<cell.rowSpan;down++)for(let across=0;across<cell.colSpan;across++){
          grid[index+down]||=[];grid[index+down][column+across]=value;
        }
        column+=cell.colSpan;
      }
    });
    const hasHeader=table.tHead?.rows.length||[...table.rows[0]?.cells||[]].every(cell=>cell.tagName==='TH');
    const headers=hasHeader?(grid.shift()||[]):(grid[0]||[]).map((_,index)=>'Column '+(index+1));
    const rows=grid.map(row=>headers.map((header,index)=>{
      const value=row[index]??'';
      if(/length|start|end|count|density|percent|position|repeats|blocks|\(bp\)|%/i.test(header) && /^-?\d[\d,]*(?:\.\d+)?%?$/.test(value))return Number(value.replace(/[,%]/g,''));
      return value;
    }));
    return {name:contextName(table),headers,rows};
  };
  // Function: save.
  // Inputs: blob (download content); name (trace/column name)
  // Outputs: Saves the selected data or setting using this feature's existing destination.
  const save=(blob,name)=>{
    const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=name;
    document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);
  };
  // Function: exportTable.
  // Inputs: table (table element); format (display-value formatter)
  // Outputs: Prepares and downloads the selected CSV or XLSX table.
  const exportTable=(table,format)=>{
    const raw=table.reportExportData?.()||domData(table);
    const data=window.reportBarcodeNames?.exportData(table,raw)||raw;
    const name=contextName(table).replace(/[^a-zA-Z0-9_-]+/g,'-').replace(/^-|-$/g,'').slice(0,150)||'table';
    if(format==='csv')save(new Blob([csv(data)],{type:'text/csv;charset=utf-8'}),name+'.csv');
    else save(new Blob([workbook(data)],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}),name+'.xlsx');
  };
  window.reportExportTable=exportTable;
  window.reportTableExportFormats={csv,workbook,domData};
  // Function: attach.
  // Inputs: table (table element)
  // Outputs: Adds export controls or related handlers to the supplied report element.
  const attach=table=>{
    if(attached.has(table)||!table.closest('main'))return;attached.add(table);
    const anchor=table.closest('.reads-scroll,.table-responsive')||table;
    // Cloning a saved table copies its toolbar markup but not its handlers.
    // Replace those toolbars instead of adding another set alongside them.
    while(anchor.previousElementSibling?.matches('.table-export-controls'))anchor.previousElementSibling.remove();
    const controls=document.createElement('div');controls.className='table-export-controls';
    controls.style.cssText='display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:10px 0';
    const status=document.createElement('span');status.setAttribute('role','status');
    for(const [format,label] of [['csv','Save CSV'],['xlsx','Save Excel']]){
      const button=document.createElement('button');button.type='button';button.textContent=label;
      button.style.cssText='padding:7px 10px;border:1px solid #ccd8e8;border-radius:6px;background:white;color:#2456a6;cursor:pointer';
      // Function: button.onclick.
      // Inputs: None; uses the current report/browser state.
      // Outputs: Handles the UI action and updates the associated report controls.
      button.onclick=()=>{try{exportTable(table,format);status.textContent='\u2713';status.setAttribute('aria-label','Saved');setTimeout(()=>{status.textContent='';status.removeAttribute('aria-label');},2500);}catch(error){status.textContent=error.message||'Table export failed.';}};
      controls.appendChild(button);
    }
    controls.appendChild(status);
    const statsHeading=table.closest('.barcode-statistics-section')?.querySelector('.barcode-statistics-heading');
    if(statsHeading)statsHeading.appendChild(controls);
    else{
      const section=table.closest('section');
      const heading=section?.querySelector('h2');
      if(heading&&section.querySelectorAll('table').length===1){
        let row=heading.closest('.report-section-heading');
        if(!row){row=document.createElement('div');row.className='report-section-heading';heading.before(row);row.appendChild(heading);}
        row.appendChild(controls);
      }else anchor.before(controls);
    }
  };
  // Function: scan.
  // Inputs: root (DOM/data root)
  // Outputs: Finds relevant report elements and attaches this feature once per element.
  const scan=root=>{if(root.nodeType!==1&&root!==document)return;if(root.matches?.('table'))attach(root);root.querySelectorAll('table').forEach(attach);};
  // Function: start.
  // Inputs: None; uses the current report/browser state.
  // Outputs: Initializes this report feature and registers its event listeners.
  const start=()=>{
    window.reportTableExportObserver?.disconnect();
    document.querySelectorAll('.table-export-controls').forEach(node=>node.remove());
    scan(document);
    const observer=new MutationObserver(records=>records.forEach(record=>record.addedNodes.forEach(scan)));
    window.reportTableExportObserver=observer;observer.observe(document.body,{childList:true,subtree:true});
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
