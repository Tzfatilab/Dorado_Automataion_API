/* Offline presentation only. No scientific detection, calling or filtering. */
"use strict";
(() => {
  const view = document.getElementById("view");
  const breadcrumbs = document.getElementById("breadcrumbs");
  const data = window.NanoTelData;
  const node = (tag, text, cls) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = String(text);
    if (cls) element.className = cls;
    return element;
  };
  const link = (text, href) => { const a = node("a", text); a.href = href; return a; };
  const readLabel = r => r.original_id.trim().split(/\s+/)[0];
  const routeFor = (b, r) => "#/barcode/" + b.id + (r ? "/read/" + r.id : "");
  const titleFor = key => ({amount_of_telomeres: "Telomeric reads (post-filtered)",
    imported_read_records: "Imported read records", median_telomere_length: "Median telomere length (post-filtered)",
    mean_density: "Mean density (post-filtered)", tvr_inclusive: "TVR-inclusive call",
    exact: "Exact call", mismatch: "Mismatch call"}[key] || key.replaceAll("_", " "));
  let generation = 0;
  const pending = new Map();
  const sources = new Map((data?.run?.sources || []).map(s => [s.id, s]));

  function evidenceText(items) {
    return (items || []).map(e => {
      const s = sources.get(e.source_id);
      return (s ? s.path + (s.sheet ? " · sheet " + s.sheet : "") : "Unknown source") +
        (e.row ? " · row " + e.row : "") + (e.fields?.length ? " · " + e.fields.join(", ") : "");
    }).join("; ");
  }
  function fact(f) {
    const el = node("div", undefined, "fact");
    if (!f || f.status !== "available") {
      el.append(node("span", "Not available", "state " + (f?.status || "missing")));
      const why = node("details", undefined, "fact-details");
      why.append(node("summary", "Why?"), node("p", f?.reason || "No exported value", "muted"));
      el.append(why); return el;
    }
    let display = f.value;
    if (display && typeof display === "object" && display.convention === "zero_based_half_open") {
      display = `${display.start + 1}\u2013${display.end} bp (1-based inclusive; ${display.space})`;
    } else if (typeof display === "object") display = JSON.stringify(display, null, 2);
    else if (typeof display === "number") display = display.toLocaleString(undefined, {maximumFractionDigits: 2});
    el.append(node(typeof f.value === "object" ? "pre" : "span", display + (f.unit && typeof f.value !== "object" ? " " + f.unit : ""), "fact-value"));
    const details = node("details", undefined, "fact-details"); details.append(node("summary", "Source & definition"));
    if (f.population) details.append(node("p", "Population: " + f.population.replaceAll("_", " "), "state"));
    if (f.origin === "presentation_aggregate") details.append(node("span", "Presentation aggregate", "state"));
    details.append(node("div", evidenceText(f.evidence), "provenance")); el.append(details); return el;
  }
  function card(title) { const c = node("section", undefined, "card"); c.append(node("h2", title)); view.append(c); return c; }
  function metrics(parent, values) {
    const grid = node("div", undefined, "grid");
    for (const [key, f] of Object.entries(values)) { const m = node("div", undefined, "metric"); m.append(node("strong", titleFor(key)), fact(f)); grid.append(m); }
    parent.append(grid);
  }
  function warnings(items) { for (const text of items || []) view.append(node("p", text, "warning")); }
  function provenance(evidence) {
    const section = card("Source provenance");
    const ids = evidence ? new Set(evidence.map(e => e.source_id)) : new Set(sources.keys());
    if (!ids.size) section.append(node("p", "No source artifacts available.", "muted"));
    for (const id of ids) {
      const s = sources.get(id); if (!s) continue;
      const details = node("details"); details.append(node("summary", s.path + (s.sheet ? " · " + s.sheet : "")));
      details.append(node("p", "Format: " + s.format), node("pre", "SHA-256: " + s.sha256)); section.append(details);
    }
  }
  function crumbs(b, r) {
    breadcrumbs.replaceChildren(link("All Barcodes", "#/run"));
    if (b) breadcrumbs.append(document.createTextNode(" › "), link(b.label, routeFor(b)));
    if (r) breadcrumbs.append(document.createTextNode(" › "), node("span", readLabel(r)));
  }
  function table(parent, headers) {
    const wrap = node("div", undefined, "table-wrap"), t = node("table"), head = node("thead"), tr = node("tr"), body = node("tbody");
    for (const h of headers) { const th = node("th", h); th.scope = "col"; tr.append(th); }
    head.append(tr); t.append(head, body); wrap.append(t); parent.append(wrap); return body;
  }
  function row(body, values) { const tr = node("tr"); for (const value of values) { const td = node("td"); td.append(value instanceof Node ? value : document.createTextNode(String(value))); tr.append(td); } body.append(tr); }

  const ok = f => f && f.status === "available";
  const shortBarcode = label => label.replace(/^barcode0*/i, "BC").replace(/^BC(\d)$/, "BC0$1");
  const htmlText = value => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
  function numbered(parent, number, title) {
    const section = node("section", undefined, "card chart-card");
    const heading = node("h2"); heading.append(node("span", number, "section-number"), document.createTextNode(title));
    section.append(heading); parent.append(section); return section;
  }
  function emptyChart(parent, title, explanation) {
    const empty = node("div", undefined, "empty-chart");
    empty.append(node("strong", title), node("p", explanation)); parent.append(empty);
  }
  function plot(parent, traces, layout, onClick) {
    const host = node("div", undefined, "plot"); parent.append(host);
    if (!window.Plotly) { emptyChart(host, "Chart library unavailable", "Keep plotly.min.js in the report assets folder."); return; }
    const style = {font:{family:"Segoe UI, Arial, sans-serif",size:12,color:"#21354e"},
      margin:{l:62,r:24,t:20,b:62},paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#ffffff",
      showlegend:false, xaxis:{automargin:true,showgrid:false}, yaxis:{automargin:true,gridcolor:"#e8eef5",zeroline:false}, ...layout};
    Plotly.newPlot(host, traces, style, {responsive:true,displaylogo:false,scrollZoom:false,
      modeBarButtonsToRemove:["lasso2d","select2d","sendDataToCloud"]}).then(() => {
      host.dataset.ready = "true";
      if (onClick) host.on("plotly_click", event => onClick(event.points[0]));
    }).catch(() => { host.replaceChildren(); emptyChart(host, "Chart unavailable", "Use the barcode table to explore these results."); });
  }
  function runCounts(parent) {
    const entries = data.run.barcodes.filter(b => ok(b.metrics.amount_of_telomeres));
    if (!entries.length) { emptyChart(parent,"No filtered counts", "No post-filtered barcode statistics were exported."); return; }
    plot(parent,[{type:"bar",x:entries.map(b=>shortBarcode(b.label)),y:entries.map(b=>b.metrics.amount_of_telomeres.value),
      customdata:entries.map(b=>b.id),marker:{color:"#428cf0",line:{color:"#2577db",width:1}},
      text:entries.map(b=>b.metrics.amount_of_telomeres.value),textposition:"outside",cliponaxis:false,
      hovertemplate:"%{x}<br>%{y:,} post-filtered reads<extra></extra>"}],
      {yaxis:{title:{text:"Post-filtered telomeric reads"},rangemode:"tozero",gridcolor:"#edf1f7"},xaxis:{title:{text:"Barcode"}}},
      p=>{location.hash=routeFor({id:p.customdata});});
    parent.append(node("p","Click a bar to open its barcode.","chart-note"));
  }
  function runLengths(parent, barcodeId) {
    const items = data.run.dashboard.distributions.filter(d=>ok(d.lengths) && (!barcodeId || d.id===barcodeId));
    const available = items.filter(d=>d.lengths.value.length);
    if (!available.length) { emptyChart(parent,"No length distribution", "Filtered per-read lengths are unavailable; source medians remain in the table."); return; }
    const traces = available.map(d=>({type:"box",name:shortBarcode(d.label),y:d.lengths.value.map(r=>r.length_bp/1000),
      customdata:d.lengths.value.map(r=>[d.id,r.read_id]),boxpoints:"all",jitter:0.35,pointpos:0,
      marker:{color:"#2779d9",size:6,opacity:0.7},fillcolor:"#a9d6ff",line:{color:"#2162a6",width:1.5},
      hovertemplate:"%{y:.3f} kb<extra>%{fullData.name}</extra>"}));
    plot(parent,traces,{yaxis:{title:{text:"Telomere length (kb)"},rangemode:"tozero",gridcolor:"#edf1f7"},xaxis:{title:{text:"Barcode"}}},
      p=>{const ids=p.customdata;if(ids?.[1]) location.hash=routeFor({id:ids[0]},{id:ids[1]});});
    parent.append(node("p","Post-filtered lengths used by the R summary. Click a read point for details.","chart-note"));
  }
  function referenceHeatmap(parent, barcodeId) {
    const cells=data.run.dashboard.reference_cells.filter(c=>!barcodeId||c.barcode_id===barcodeId);
    if(!cells.length){emptyChart(parent,"Mapping detail unavailable","No joined post-filtered mapping records are available for this selection.");return;}
    const refs=[...new Set(cells.map(c=>c.reference))].sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
    const bars=data.run.barcodes.filter(b=>!barcodeId||b.id===barcodeId);
    const matrix=bars.map(b=>refs.map(ref=>cells.find(c=>c.barcode_id===b.id&&c.reference===ref)?.median_bp/1000 || null));
    plot(parent,[{type:"heatmap",x:refs.map(htmlText),y:bars.map(b=>shortBarcode(b.label)),z:matrix,
      customdata:bars.map(b=>refs.map(()=>b.id)),colorscale:[[0,"#d9efce"],[0.35,"#94cde3"],[0.7,"#f8c079"],[1,"#b82463"]],
      hoverongaps:false,colorbar:{title:{text:"Median<br>(kb)"},thickness:12},
      hovertemplate:"%{y} \u00b7 %{x}<br>Median: %{z:.3f} kb<extra></extra>"}],
      {margin:{l:70,r:100,t:20,b:95},xaxis:{title:{text:"Mapped reference (source label)"},tickangle:-35},yaxis:{autorange:"reversed"}},
      p=>{location.hash=routeFor({id:p.customdata});});
    parent.append(node("p","Reference labels are preserved. A read mapping to multiple references contributes once to each; these are not unique chromosome assignments.","chart-note"));
  }
  function technicalDetails() {
    const details=node("details",undefined,"technical-details card");details.append(node("summary","Run settings & source provenance"));view.append(details);
    const section=node("div");details.append(section);
    metrics(section,{organism:data.run.organism,...data.run.stages});
    const settings=node("details");settings.append(node("summary","Settings snapshot"),fact(data.run.settings));section.append(settings);
    for(const s of sources.values()){const item=node("details");item.append(node("summary",s.path+(s.sheet?" \u00b7 "+s.sheet:"")),node("pre","SHA-256: "+s.sha256));section.append(item);}
  }
  function overview() {
    crumbs();view.append(node("h1","All Barcodes"),node("p",data.run.label+" \u00b7 "+(ok(data.run.organism)?data.run.organism.value:"Organism not recorded"),"run-subtitle"));warnings(data.run.warnings);
    const dash=data.run.dashboard;
    const stats=numbered(view,"1","Key Statistics (All Barcodes)");stats.classList.add("stats-section");
    const grid=node("div",undefined,"kpi-grid");stats.append(grid);
    const labels={barcode_count:"Total barcodes",total_reads:"Input reads",telomeric_reads:"Post-filtered telomeric reads",telomeric_percentage:"Post-filtered telomeric fraction",median_telomere_length:"Overall median telomere length",mapped_references:"Mapped references"};
    for(const [key,label] of Object.entries(labels)) {
      const f=dash.metrics[key], item=node("div",undefined,"kpi kpi-"+key);item.append(node("span",label,"kpi-label"));
      let value="\u2014", unit="";
      if(ok(f)){value=typeof f.value==="number"?f.value.toLocaleString(undefined,{maximumFractionDigits:2}):f.value;if(key==="median_telomere_length"){value=(f.value/1000).toFixed(2);unit=" kb";}if(key==="telomeric_percentage")unit="%";}
      item.append(node("strong",value+unit,"kpi-value"));
      let caption=ok(f)?(key==="median_telomere_length"?"Pooled post-filtered reads":key==="mapped_references"?"Source labels; not inferred chromosomes":key==="telomeric_reads"&&ok(dash.metrics.detected_telomeric_reads)?dash.metrics.detected_telomeric_reads.value+" detected before filtering":""):"Not available in these outputs";
      item.append(node("span",caption,"kpi-note"));
      const details=node("details");details.append(node("summary","Details"),fact(f));item.append(details);grid.append(item);
    }
    const charts=node("div",undefined,"chart-grid");view.append(charts);
    runCounts(numbered(charts,"2","Telomeric Reads by Barcode"));
    runLengths(numbered(charts,"3","Telomere Length by Barcode"));
    const tvr=numbered(charts,"4","TVR Composition Across Barcodes");
    barcodeComposition(tvr);
    referenceHeatmap(numbered(charts,"5","Median Telomere Length by Reference and Barcode"));
    const highlights=numbered(view,"6","Barcode Highlights");
    const ranks=data.run.barcodes.filter(b=>ok(b.metrics.median_telomere_length)).sort((a,b)=>b.metrics.median_telomere_length.value-a.metrics.median_telomere_length.value);
    const list=node("div",undefined,"highlight-grid");highlights.append(list);
    for(const b of ranks.slice(0,3)){const item=node("div",undefined,"highlight");item.append(link(shortBarcode(b.label),routeFor(b)),node("strong",(b.metrics.median_telomere_length.value/1000).toFixed(2)+" kb"),node("span","Median length \u00b7 post-filtered"));list.append(item);}
    if(!ranks.length)highlights.append(node("p","No source-reported barcode medians available.","muted"));
    const body=table(card("Barcodes"),["Barcode","Detected summary records","Post-filtered telomeric reads","Median length"]);
    for(const b of data.run.barcodes)row(body,[link(b.label,routeFor(b)),fact(b.metrics.imported_read_records),fact(b.metrics.amount_of_telomeres),fact(b.metrics.median_telomere_length)]);
    technicalDetails();
  }

  function barcodeComposition(parent) {
    const select=node("select");select.setAttribute("aria-label","Composition region");
    for(const [value,label] of [["telomere","Inside exact telomeres"],["whole_read","Whole reads (including outside telomeres)"]]){const option=node("option",label);option.value=value;select.append(option);}
    parent.append(select);const chart=node("div");parent.append(chart);
    const redraw=()=>{
      if(window.Plotly)for(const host of chart.querySelectorAll(".js-plotly-plot"))Plotly.purge(host);
      chart.replaceChildren();const entries=data.run.dashboard.motif_comparison||[];
      const eligible=entries.filter(e=>e.available&&Object.values(e[select.value]).reduce((a,b)=>a+b,0)>0);
      if(!eligible.length){emptyChart(chart,"No complete motif composition","No usable exports for the selected region.");return;}
      const labels=[...new Set(eligible.flatMap(e=>Object.keys(e[select.value])))].sort((a,b)=>Number(b.includes("(canonical)"))-Number(a.includes("(canonical)"))||a.localeCompare(b));
      const palette=["#3498DB","#E7A33E","#3FA878","#E56D83","#A56CC1","#4DA6BA","#927252","#697586"];
      plot(chart,labels.map((label,i)=>({type:"bar",name:label,x:eligible.map(e=>shortBarcode(e.label)),
        y:eligible.map(e=>100*(e[select.value][label]||0)/Object.values(e[select.value]).reduce((a,b)=>a+b,0)),
        customdata:eligible.map(e=>[e.id,e[select.value][label]||0]),marker:{color:palette[i%palette.length]},
        hovertemplate:"%{x}<br>%{y:.2f}% of search matches<br>%{customdata[1]} matches<extra>%{fullData.name}</extra>"})),
        {barmode:"stack",showlegend:true,legend:{orientation:"h"},xaxis:{title:{text:"Barcode"}},yaxis:{title:{text:"Motif search matches (%)"},range:[0,100]}},
        point=>{if(point?.customdata)location.hash="#/barcode/"+point.customdata[0];});
      chart.append(node("p","Post-filtered reads; percentages count exported search matches, not bases or reads. Overlaps are retained. Click a bar to open its barcode.","chart-note"));
      const excluded=entries.filter(e=>!eligible.includes(e));if(excluded.length)chart.append(node("p","Not plotted (missing data or no matches): "+excluded.map(e=>e.label).join(", "),"chart-note"));
    };select.onchange=redraw;redraw();
  }

  function barcodePage(b) {
    crumbs(b);
    const heading=node("div",undefined,"barcode-heading");heading.append(node("h1","Barcode "+shortBarcode(b.label)));
    const nav=node("div",undefined,"pager"),index=data.run.barcodes.findIndex(item=>item.id===b.id);
    for(const neighbor of [data.run.barcodes[index-1],data.run.barcodes[index+1]])if(neighbor)nav.append(link(shortBarcode(neighbor.label),routeFor(neighbor)));
    heading.append(nav);view.append(heading);warnings(b.warnings);
    const lengths=b.metrics.filtered_length_records;
    const ids=new Set(ok(lengths)?lengths.value.map(item=>item.read_id):[]);
    const eligible=b.reads.filter(r=>ids.has(r.id));
    const covered=eligible.filter(r=>ok(r.tracks.motifs)&&r.tracks.motifs.value.methods.includes("tvr_inclusive")&&ok(r.calls.exact?.interval));
    const matches=[];
    for(const r of covered){const interval=r.calls.exact.interval.value;
      for(const hit of r.tracks.motifs.value.matches)if(hit.method==="tvr_inclusive"&&hit.start>=interval.start&&hit.end<=interval.end)
        matches.push({...hit,read:r,relative:(hit.start-interval.start)/(interval.end-interval.start)});
    }
    const tvrReads=new Set(matches.filter(h=>h.role==="tvr").map(h=>h.read.id));
    const complete=ok(lengths)&&eligible.length===lengths.value.length&&covered.length===eligible.length&&eligible.length>0;
    const tvrFact=complete?{status:"available",value:tvrReads.size,unit:"reads",origin:"presentation_aggregate",
      population:"post-filtered reads with TVR search matches fully inside the exact telomere call",evidence:covered.flatMap(r=>r.tracks.motifs.evidence)}:
      {status:"not_exported",reason:`Motif and exact-boundary data available for ${covered.length} of ${eligible.length} imported post-filtered reads.`};
    const grid=node("div",undefined,"barcode-kpis");view.append(grid);
    for(const [label,f] of [["Total input reads",b.metrics.total_reads],["Telomeric reads (post-filtered)",b.metrics.amount_of_telomeres],
      ["Median telomere length",b.metrics.median_telomere_length],["Reads with TVR matches in exact telomere",tvrFact]]) {
      const box=node("div",undefined,"kpi");box.append(node("span",label,"kpi-label"),fact(f));grid.append(box);
    }
    const charts=node("div",undefined,"barcode-charts");view.append(charts);
    const distribution=numbered(charts,"1","Telomere length distribution");
    if(ok(lengths)&&lengths.value.length){
      plot(distribution,[{type:"histogram",x:lengths.value.map(item=>item.length_bp/1000),marker:{color:"#9581D5",line:{color:"white",width:1}},
        hovertemplate:"Length: %{x:.2f} kb<br>Reads: %{y}<extra></extra>"}],
        {xaxis:{title:{text:"Telomere length (kb)"}},yaxis:{title:{text:"Post-filtered reads"}},
         shapes:ok(b.metrics.median_telomere_length)?[{type:"line",xref:"x",yref:"paper",x0:b.metrics.median_telomere_length.value/1000,x1:b.metrics.median_telomere_length.value/1000,y0:0,y1:1,line:{color:"#D55E45",dash:"dash",width:2}}]:[]});
      distribution.append(node("p","Post-filtered source lengths. Coral line: source-reported median.","chart-note"));
    }else emptyChart(distribution,"Length distribution unavailable","No complete post-filtered length export.");
    const composition=numbered(charts,"2","Motif composition");
    const positions=numbered(charts,"3","TVR positions within telomeres");
    if(complete&&matches.length){
      const groups=new Map();for(const h of matches)groups.set(h.motif,(groups.get(h.motif)||0)+1);
      const labels=[...groups.keys()].sort(),palette=["#3498DB","#E7A33E","#3FA878","#A56CC1","#E56D83","#4DA6BA","#927252"];
      plot(composition,[{type:"pie",hole:0.62,labels,values:labels.map(label=>groups.get(label)),sort:false,
        marker:{colors:labels.map((_,i)=>palette[i%palette.length])},textinfo:"none",hovertemplate:"%{label}<br>%{value} search matches<br>%{percent} of matches<extra></extra>"}],
        {showlegend:true,legend:{orientation:"h",font:{size:10}},margin:{l:15,r:15,t:15,b:40}});
      composition.append(node("p","Share of motif search matches fully inside exact telomere calls. Overlaps retained; this is not base coverage or percentage of reads.","chart-note"));
      const tvrs=matches.filter(h=>h.role==="tvr");
      if(tvrs.length)plot(positions,labels.map((label,i)=>{const hits=tvrs.filter(h=>h.motif===label);return {type:"scatter",mode:"markers",name:label,
        x:hits.map(h=>h.relative),y:hits.map(h=>readLabel(h.read)),customdata:hits.map(h=>h.read.id),
        marker:{symbol:"line-ns",size:12,color:palette[i%palette.length],line:{width:2,color:palette[i%palette.length]}},
        hovertemplate:"Read: %{y}<br>Relative start: %{x:.3f}<extra>%{fullData.name}</extra>"};}),
        {xaxis:{title:{text:"Relative position in exact telomere"},range:[0,1]},yaxis:{showticklabels:false,title:{text:"Reads"}},margin:{l:45,r:15,t:15,b:55}},
        point=>{if(point?.customdata)location.hash=routeFor(b,{id:point.customdata});});
      else emptyChart(positions,"No TVR matches inside exact telomeres","Exported TVR matches elsewhere in the read remain visible on the read page.");
      positions.append(node("p","Click a match to open its read. Position follows the analyzed sequence; 5′/3′ orientation is not inferred.","chart-note"));
    }else{
      emptyChart(composition,"Composition unavailable",complete?"No motif matches inside exact telomere calls.":tvrFact.reason);
      emptyChart(positions,"TVR positions unavailable",complete?"No motif matches inside exact telomere calls.":tvrFact.reason);
    }
    const technical=node("details",undefined,"card technical-details");technical.append(node("summary","Barcode statistics"));metrics(technical,Object.fromEntries(Object.entries(b.metrics).filter(([key])=>key!=="filtered_length_records")));view.append(technical);
    barcodeComposition(card("TVR composition across barcodes"));
    const section = card("Reads");
    section.append(node("p", "Source-reported calls are shown separately. Missing values are not zero; absent filtered records are not classified as failures.", "muted"));
    const body = table(section, ["Read ID", "Read length", "Exact telomere length", "Mismatch telomere length", "TVR-inclusive length", "Filtering membership"]);
    const pager = node("div", undefined, "pager"), previous = node("button", "Previous"), next = node("button", "Next"), count = node("span");
    let offset = 0;
    const redraw = () => {
      body.replaceChildren();
      for (const r of b.reads.slice(offset, offset + 50)) row(body, [link(readLabel(r), routeFor(b, r)), fact(r.metrics.read_length),
        ...["exact", "mismatch", "tvr_inclusive"].map(key => fact(r.calls[key].reported_length)), fact(r.filtering)]);
      previous.disabled = offset === 0; next.disabled = offset + 50 >= b.reads.length;
      count.textContent = b.reads.length ? `${offset + 1}–${Math.min(offset + 50, b.reads.length)} of ${b.reads.length} records` : "No read records available";
    };
    previous.addEventListener("click", () => { offset = Math.max(0, offset - 50); redraw(); });
    next.addEventListener("click", () => { offset += 50; redraw(); });
    pager.append(previous, count, next); section.append(pager); redraw(); provenance(b.evidence);
  }

  // Draw exported intervals only; this is not a reconstructed density curve.
  function readBoundaryPlot(parent, r) {
    const groups = new Map();
    for (const [method, call] of Object.entries(r.calls)) {
      const interval = call.interval;
      if (!ok(interval)) continue;
      const value = interval.value;
      if (value.space !== "nanotel_analyzed_read" || value.convention !== "zero_based_half_open" ||
          !Number.isInteger(value.start) || !Number.isInteger(value.end) || value.start < 0 || value.end <= value.start) continue;
      const key = `${value.start}:${value.end}`;
      if (!groups.has(key)) groups.set(key, {value, calls:[]});
      groups.get(key).calls.push({method, call});
    }
    if (!groups.size) {
      emptyChart(parent, "Telomere boundary unavailable", "No valid NanoTel read-coordinate interval was exported for this read."); return;
    }
    const length = ok(r.metrics.read_length) ? r.metrics.read_length.value : null;
    const traces = [], labels = [], positions = [];
    let lane = 0;
    for (const {value, calls} of groups.values()) {
      labels.push(calls.map(({method}) => titleFor(method)).join(" / ")); positions.push(lane);
      if (Number.isFinite(length) && length >= value.end) traces.push({type:"scatter",mode:"lines",
        x:[1,length],y:[lane,lane],line:{color:"#dce5ef",width:18},hoverinfo:"skip"});
      const hover = calls.map(({method,call}) => htmlText(titleFor(method)) +
        (ok(call.reported_length) ? `<br>Reported length: ${call.reported_length.value} bp` : "") +
        (ok(call.density) ? `<br>Source density: ${call.density.value} (fraction)` : "")).join("<br><br>");
      traces.push({type:"scatter",mode:"lines+markers",x:[value.start+1,value.end],y:[lane,lane],
        line:{color:"#2472dc",width:18},marker:{size:8,color:"#2472dc"},
        hovertemplate:`Start: ${value.start+1} bp<br>End: ${value.end} bp<br>${hover}<extra></extra>`});
      lane++;
    }
    const extent = Math.max(Number.isFinite(length) ? length : 0, ...Array.from(groups.values(),g=>g.value.end));
    plot(parent,traces,{margin:{l:30,r:30,t:25,b:95},
      xaxis:{title:{text:"Position in NanoTel-analyzed read (bp)"},range:[0,extent*1.02],tickformat:",d"},
      yaxis:{tickvals:positions,ticktext:positions.map(n=>`Call group ${n+1}`),range:[-0.65,lane-0.35],showticklabels:false,showgrid:false,zeroline:false}});
    labels.forEach((label,i)=>parent.append(node("p",`Call group ${i+1}: ${label}`,"chart-note")));
    parent.append(node("p", "Blue: reported telomere interval. Gray: read extent, when exported. Hover over the blue interval for exact source values. Identical boundaries share one track.", "chart-note"));
    parent.append(node("p", "Positions use 1-based inclusive coordinates on the analyzed sequence; original-read orientation is unknown. Reference alignments are not projected onto this axis.", "chart-note"));
    parent.append(node("p", "A repeat-density curve and exact TVR tracks are unavailable in the imported outputs. The reported mean density cannot reconstruct a density curve.", "muted"));
  }

  function readDensity(parent, r) {
    const samples = r.tracks.density;
    if (!ok(samples)) { readBoundaryPlot(parent,r); return; }
    const colors = {exact:"#D55E45", mismatch:"#697586", tvr_inclusive:"#8B5FBF"};
    const traces = [];
    for (const method of ["tvr_inclusive", "mismatch", "exact"]) {
      const values = samples.value.filter(s=>s.method===method);
      if (!values.length) continue;
      traces.push({type:"scatter", mode:"lines", name:({exact:"Canonical repeat density",mismatch:"Density allowing mismatches",tvr_inclusive:"Canonical + TVR density"})[method],
        x:values.map(s=>s.start+1),y:values.map(s=>s.density),
        customdata:values.map(s=>[s.start+1,s.end]),line:{color:colors[method],width:method==="exact"?2.5:2,dash:"solid"},
        fill:method==="exact"?"tozeroy":"none",fillcolor:"rgba(213,94,69,0.18)",
        hovertemplate:"Window: %{customdata[0]}-%{customdata[1]} bp<br>Density: %{y:.4f}<extra>%{fullData.name}</extra>"});
    }
    const shapes=[];
    for(const [method,call] of Object.entries(r.calls)) if(ok(call.interval)) {
      shapes.push({type:"line",xref:"x",yref:"paper",x0:call.interval.value.end,x1:call.interval.value.end,
        y0:0.38,y1:1,line:{color:colors[method],width:1,dash:"dot"}});
    }
    // Match the R plot's region strip: blue means outside the exact call,
    // not independently confirmed genomic subtelomere annotation.
    const exact=r.calls.exact?.interval;
    if(ok(exact) && ok(r.metrics.read_length)) {
      const start=exact.value.start+1, end=exact.value.end, length=r.metrics.read_length.value;
      const region=(name,a,b,color)=>{
        if(b<a) return;
        traces.push({type:"scatter",mode:"lines",name,x:[a,b],y:[-0.07,-0.07],
          line:{color,width:10},hovertemplate:`${name}: ${a}-${b} bp<extra></extra>`});
      };
      region("Telomere (exact call)",start,end,"#D55E45");
      region("Sub-telomere (outside exact call)",end+1,length,"#397FA6");
      if(start>1) {
        region("Outside exact call (leading bases)",1,start-1,"#397FA6");
        traces[traces.length-1].showlegend=false;
      }
      shapes.push({type:"rect",xref:"x",yref:"y",x0:start,x1:end,y0:0,y1:1,
        fillcolor:"rgba(213,94,69,0.04)",line:{width:0},layer:"below"});
    }
    const annotations=[];
    if(ok(r.tracks.motifs)) {
      const data=r.tracks.motifs.value;
      const method=data.methods.includes("tvr_inclusive")?"tvr_inclusive":data.methods[0];
      const hits=data.matches.filter(h=>h.method===method);
      const motifs=[...new Set(hits.filter(h=>h.role==="tvr").map(h=>h.motif))].sort();
      const palette=["#E7A33E","#3FA878","#A56CC1","#E56D83","#4DA6BA","#927252","#697586"];
      const length=ok(r.metrics.read_length)?r.metrics.read_length.value:Math.max(...hits.map(h=>h.end),1);
      for(const lane of [0,1]) traces.push({type:"scatter",mode:"lines",x:[1,length],y:[lane,lane],yaxis:"y2",
        line:{color:"#edf0f5",width:20},showlegend:false,hoverinfo:"skip"});
      const groups=[{name:"Canonical motif matches",hits:hits.filter(h=>h.role==="canonical"),color:"#3498DB",tvr:false},
        ...motifs.map((motif,i)=>({name:motif,hits:hits.filter(h=>h.role==="tvr"&&h.motif===motif),color:palette[i%palette.length],tvr:true}))];
      for(const group of groups) {
        for(const lane of group.tvr?[1,0]:[1]) {
          const x=[],y=[],customdata=[];
          for(const hit of group.hits){x.push(hit.start+1,hit.end,null);y.push(lane,lane,null);
            const detail=[hit.motif,hit.matched_sequence,hit.start+1,hit.end,hit.max_mismatch];customdata.push(detail,detail,detail);}
          traces.push({type:"scatter",mode:"lines+markers",marker:{symbol:"line-ns",size:18,color:group.color,line:{width:1,color:group.color}},name:group.name,legendgroup:"motif-"+group.name,showlegend:lane===1,
            x,y,yaxis:"y2",customdata,line:{color:group.color,width:18},
            hovertemplate:"Motif: %{customdata[0]}<br>Matched: %{customdata[1]}<br>%{customdata[2]}-%{customdata[3]} bp<br>Allowed mismatches: %{customdata[4]}<extra></extra>"});
        }
      }
      if(!hits.length) annotations.push({xref:"paper",yref:"paper",x:0.5,y:0.15,text:"No motif matches in this search",showarrow:false});
    } else annotations.push({xref:"paper",yref:"paper",x:0.5,y:0.15,text:"Motif positions were not exported for this read",showarrow:false});
    plot(parent,traces,{height:480,showlegend:true,legend:{orientation:"v",x:1.02,y:1,font:{size:11}},
      shapes,annotations,margin:{l:100,r:230,t:20,b:55},
      xaxis:{title:{text:"Position in NanoTel-analyzed read (bp)"},tickformat:"~s",anchor:"y2"},
      yaxis:{domain:[0.38,1],title:{text:"Repeat density"},range:[-0.13,1.05],tickvals:[0,0.5,1]},
      yaxis2:{domain:[0.02,0.23],range:[-0.6,1.6],tickvals:[0,1],ticktext:["TVR matches","Motif type"],showgrid:false,zeroline:false,fixedrange:true}});
    parent.querySelector(".plot").style.height="480px";
    parent.append(node("p","All tracks share the same read-position axis. Motif colors show source search matches; short hits use a minimum-width marker for visibility. Hover for exact coordinates. Overlapping hits may overlap visually. TVR matches are individual hits, not merged regions. Blue below the density curve marks the portion outside the exact telomere call, as in the R plot.","chart-note"));

  }
  function readMotifs(r) {
    const panel=card("TVR sequences & positions");
    if(!ok(r.tracks.motifs)) {
      panel.append(fact(r.tracks.motifs),node("p","This run predates motif-level export or was summary-only. A new non-summary run is required to populate this view.","muted")); return;
    }
    const dataset=r.tracks.motifs.value, select=node("select");
    select.setAttribute("aria-label","Motif search method");
    for(const method of dataset.methods){const option=node("option",titleFor(method));option.value=method;select.append(option);}
    select.value=dataset.methods.includes("tvr_inclusive")?"tvr_inclusive":dataset.methods[0];
    panel.append(select,node("p","Source search matches across the analyzed read. Overlapping hits are retained; counts are matches, not distinct TVR regions or coverage percentages. Coordinates are 1-based inclusive.","muted"));
    const content=node("div");panel.append(content);
    const redraw=()=>{
      if(window.Plotly) for(const host of content.querySelectorAll(".js-plotly-plot")) Plotly.purge(host);
      content.replaceChildren();
      const hits=dataset.matches.filter(h=>h.method===select.value&&h.role==="tvr");
      if(!hits.length){content.append(node("p",select.value==="tvr_inclusive"?"No TVR search matches were exported for this read.":"This method searches canonical repeats. Select the TVR-inclusive method to inspect TVR matches."));return;}
      const motifs=[...new Set(hits.map(h=>h.motif))].sort();
      content.append(node("p",`${hits.length} TVR matches | ${motifs.length} searched motifs`));
      const body=table(content,["Searched motif","Matched sequence","Start (bp)","End (bp)","Length (bp)","Allowed mismatches"]);
      let offset=0;
      const count=node("span"),prev=node("button","Previous"),next=node("button","Next");
      const rows=()=>{body.replaceChildren();for(const h of hits.slice(offset,offset+100))row(body,[h.motif,h.matched_sequence,h.start+1,h.end,h.end-h.start,h.max_mismatch]);count.textContent=` ${offset+1}-${Math.min(offset+100,hits.length)} of ${hits.length} `;prev.disabled=offset===0;next.disabled=offset+100>=hits.length;};
      prev.onclick=()=>{offset-=100;rows();};next.onclick=()=>{offset+=100;rows();};content.append(prev,count,next);rows();
    };
    select.addEventListener("change",redraw);redraw();
  }

  function readHighlights(r) {
    const grid=node("div",undefined,"read-kpis");view.append(grid);
    const alignments=ok(r.alignments)?r.alignments.value:[];
    const items=Object.entries(r.calls).filter(([,c])=>ok(c.reported_length)).map(([method,c])=>[titleFor(method)+" length",c.reported_length]);
    if(alignments.length===1) items.push(["Mapped reference",alignments[0].reference],["Mapping quality",alignments[0].mapq]);
    else items.push(["Reference alignments",{status:"available",value:alignments.length?`${alignments.length} alignments`:"Not exported"}]);
    if(ok(r.tracks.motifs) && r.tracks.motifs.value.methods.includes("tvr_inclusive")) {
      items.push(["TVR search matches (whole read)",{status:"available",
        value:r.tracks.motifs.value.matches.filter(h=>h.method==="tvr_inclusive"&&h.role==="tvr").length,
        origin:"presentation_aggregate",population:"TVR search hits across the whole analyzed read; overlaps retained",evidence:r.tracks.motifs.evidence}]);
    } else items.push(["TVR content",{status:"not_exported",reason:"Motif-level results are not available for this read."}]);
    for(const [label,f] of items){const box=node("div",undefined,"kpi");box.append(node("span",label,"kpi-label"),fact(f));grid.append(box);}
  }

  function readPage(b, r) {
    crumbs(b, r); view.append(node("h1", "Read: " + readLabel(r)), link("Back to " + b.label, routeFor(b))); warnings(r.warnings);
    view.append(node("p", b.label + " | Read length: " + (ok(r.metrics.read_length)?r.metrics.read_length.value.toLocaleString()+" bp":"Not exported"), "run-subtitle"));
    readHighlights(r);
    const header = node("details", undefined, "card technical-details");
    header.append(node("summary", "Full source read header"), node("pre", r.original_id)); view.append(header);
    readDensity(card(ok(r.tracks.density)?"Telomeric repeat density":"Telomere location (density samples not exported)"), r);
    readMotifs(r);
    const section = node("details", undefined, "card technical-details");
    section.append(node("summary", "Source-reported telomere calls")); view.append(section);
    section.append(node("p", "Coordinates are on the NanoTel-analyzed sequence. Its orientation relative to the original sequencing read is not recorded. These positions are not overlaid with reference alignments.", "muted"));
    for (const [method, call] of Object.entries(r.calls)) { section.append(node("h3", titleFor(method))); metrics(section, call); }
    const mapping = node("details",undefined,"card technical-details");mapping.append(node("summary","Reference alignments"));view.append(mapping);
    if (r.alignments.status !== "available") mapping.append(fact(r.alignments));
    else for (const alignment of r.alignments.value) metrics(mapping, alignment);
    const availability=node("details",undefined,"card technical-details");availability.append(node("summary","Data availability & read information"));
    metrics(availability,{...r.metrics,filtering_membership:r.filtering,...Object.fromEntries(Object.entries(r.tracks).filter(([,f])=>!ok(f)))});view.append(availability);
    const evidence = [...r.evidence, ...(r.alignments.evidence || [])];
    for (const call of Object.values(r.calls)) for (const f of Object.values(call)) evidence.push(...(f.evidence || []));
    provenance(evidence);
  }

  function loadBarcode(id) {
    if (data.barcodes[id]) return Promise.resolve(data.barcodes[id]);
    if (pending.has(id)) return pending.get(id);
    const promise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "assets/data/" + id + ".js";
      const timer = setTimeout(() => reject(new Error("Barcode data did not load. Keep the complete report folder together.")), 8000);
      script.onload = () => { clearTimeout(timer); data.barcodes[id] ? resolve(data.barcodes[id]) : reject(new Error("Barcode data is invalid.")); };
      script.onerror = () => { clearTimeout(timer); reject(new Error("Barcode data is missing. Keep the assets folder next to index.html.")); };
      document.head.append(script);
    });
    pending.set(id, promise); promise.catch(() => pending.delete(id)); return promise;
  }
  async function render() {
    const request = ++generation;
    if(window.Plotly) for(const host of view.querySelectorAll(".js-plotly-plot")) Plotly.purge(host);
    view.replaceChildren(); crumbs();
    try {
      if (!data?.run || data.run.schema_version !== "1.0") throw new Error("Run data is missing or uses an unsupported schema. Keep the complete report folder together.");
      const route = location.hash || "#/run";
      if (route === "#/run") { overview(); return; }
      const match = /^#\/barcode\/(b-[a-f0-9]{64})(?:\/read\/(r-[a-f0-9]{64}))?$/.exec(route);
      if (!match) throw new Error("Unknown report address.");
      const summary = data.run.barcodes.find(b => b.id === match[1]);
      if (!summary) throw new Error("This barcode is not present in the report.");
      view.append(node("p", "Loading " + summary.label + "…"));
      const b = await loadBarcode(summary.id);
      if (request !== generation) return;
      view.replaceChildren();
      if (!match[2]) barcodePage(b);
      else { const r = b.reads.find(r => r.id === match[2]); if (!r) throw new Error("This read is not present in this barcode."); readPage(b, r); }
    } catch (error) {
      if (request !== generation) return;
      view.replaceChildren(node("h1", "Page unavailable"), node("p", error.message, "warning"), link("Return to All Barcodes", "#/run"));
    } finally {
      if (request === generation) { document.getElementById("main").focus({preventScroll: true}); window.scrollTo(0, 0); }
    }
  }
  window.addEventListener("hashchange", render);
  render();
})();
