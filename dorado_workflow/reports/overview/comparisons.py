"""Presentation-only comparisons of exported, post-filtered telomere records."""
from collections import Counter, defaultdict
from html import escape
from statistics import median, quantiles
import re
from dorado_workflow.reports.shared.colors import motif_color
from dorado_workflow.reports.barcode.composition import motif_base_counts, composition_section


def comparison_data(run):
    """Return read-based TVR percentages and chromosome medians with missing states.

    TVR matches must overlap the exported TVR-inclusive telomere call.
    Boundary-crossing matches count once; position markers clip to the call.
    Read prevalence counts each motif once per read. The composition chart instead
    counts individual exported matches, retaining overlaps and source motif roles.
    Chromosome names come from annotations or explicit chrN[_Head/_Tail] labels;
    Head/Tail is never interpreted as a chromosome arm.
    """
    composition, groups, omitted = [], defaultdict(list), []
    observations = defaultdict(list)
    for barcode in run.barcodes:
        lengths = barcode.metrics.get("filtered_length_records")
        if not lengths or lengths.status != "available":
            omitted.append(barcode.label)
            continue
        by_id = {read.id: read for read in barcode.reads}
        rows = lengths.value
        with_tvr, covered, motifs = 0, 0, Counter()
        match_counts = Counter()
        base_counts = Counter()
        positions = []
        for item in rows:
            read = by_id.get(item["read_id"])
            if read is None:
                continue
            track = read.tracks.get("motifs")
            interval = read.calls.get("tvr_inclusive", {}).get("interval")
            if (track and interval and track.status == "available" and interval.status == "available"
                    and "tvr_inclusive" in track.value["methods"]):
                covered += 1
                base_counts.update(motif_base_counts(interval.value['start'], interval.value['end'],
                    ((hit['motif'] + (' (canonical)' if hit['role'] == 'canonical' else ''), hit['start'], hit['end'])
                     for hit in track.value['matches'] if hit['method'] == 'tvr_inclusive')))
                # Count source hits, not covered bases. Only the TVR-inclusive
                # method enters this denominator, avoiding duplicate methods.
                for hit in track.value["matches"]:
                    if (hit["method"] == "tvr_inclusive"
                            and hit["end"] > interval.value["start"]
                            and hit["start"] < interval.value["end"]):
                        label = hit["motif"] + (" (canonical)" if hit["role"] == "canonical" else "")
                        match_counts[label] += 1
                        # Normalize exported match starts within the TVR-inclusive call.
                        # This is a presentation axis, not inferred biological polarity.
                        span = interval.value['end'] - interval.value['start']
                        serial = read.metrics.get('read_number')
                        read_label = (f'Read {int(serial.value)}' if serial and serial.status == 'available'
                                      else read.original_id.split()[0])
                        positions.append(dict(motif=label, percent=100*(max(hit['start'],interval.value['start'])-interval.value['start'])/span,
                            start=hit['start']+1, end=hit['end'], read=read_label))
                # Count each motif at most once per read; a multi-motif read may
                # contribute to several motif percentages but only one stack class.
                found = {hit["motif"] for hit in track.value["matches"]
                         if hit["method"] == "tvr_inclusive" and hit["role"] == "tvr"
                         and hit["end"] > interval.value["start"]
                         and hit["start"] < interval.value["end"]}
                with_tvr += bool(found)
                motifs.update(found)
            if read.alignments.status != "available":
                continue
            chromosomes = set()
            for alignment in read.alignments.value:
                annotation = alignment.get("chromosome")
                if annotation and annotation.status == "available":
                    chromosomes.add(str(annotation.value))
                    continue
                reference = alignment["reference"]
                if reference.status == "available":
                    match = re.fullmatch(r"(chr(?:[0-9]+|X|Y|M|MT))(?:_(?:Head|Tail))?", reference.value)
                    if match:
                        chromosomes.add(match.group(1))
            # Do not assign a molecule to an arbitrary best alignment. Same-
            # chromosome multimapping contributes once; cross-chromosome reads
            # are excluded from this chromosome-specific median.
            if len(chromosomes) == 1:
                key = (barcode.label, next(iter(chromosomes)))
                groups[key].append(item["length_bp"])
                # Retain molecule identity beside each value for read-level clicks.
                serial = read.metrics.get('read_number')
                label = (f'Read {int(serial.value)}' if serial and serial.status == 'available'
                         else read.original_id.split()[0])
                observations[key].append(dict(read_id=read.id, barcode_id=barcode.id,
                    label=label, length_kb=item['length_bp']/1000))
        if rows and covered == len(rows):
            composition.append(dict(barcode=barcode.label, total=len(rows), with_tvr=with_tvr,
                                    without_tvr=len(rows)-with_tvr, motifs=dict(motifs), match_counts=dict(match_counts), base_counts=dict(base_counts), positions=positions))
        else:
            omitted.append(barcode.label)
    # Presentation quartiles use linear interpolation (inclusive/type 7).
    # Single-read groups have coincident quartiles, not a fabricated spread.
    cells = []
    for (b, c), values in groups.items():
        q1, _, q3 = quantiles(values, n=4, method='inclusive') if len(values) > 1 else [values[0]] * 3
        cells.append(dict(barcode=b, chromosome=c, median_kb=median(values)/1000,
                          q1_kb=q1/1000, q3_kb=q3/1000, reads=len(values), observations=observations[(b,c)]))
    return dict(composition=composition, cells=cells, omitted=omitted)


def overview_composition_section(data, requested=None):
    """Pool available complete barcodes and disclose any excluded barcodes."""
    if requested is False:
        return composition_section(None, number=4, title='TVR Composition', requested=False)
    rows = data['composition']
    pooled = None
    if rows:
        bases = Counter()
        for row in rows:
            bases.update(row['base_counts'])
        pooled = dict(base_counts=dict(bases), total=sum(row['total'] for row in rows),
                      with_tvr=sum(row['with_tvr'] for row in rows))
    title = 'TVR Composition - Available Barcodes' if data['omitted'] else 'TVR Composition - All Barcodes'
    section = composition_section(pooled, number=4, title=title)
    if pooled and 'class="histogram-figure"' in section:
        section = section.replace('class="saved-histogram composition-plot"',
            'id="overview-composition" class="saved-histogram composition-plot"')
        section = section.replace('</section>',
            '<script>(()=>{const plot=document.getElementById("overview-composition");'
            'const figure=JSON.parse(plot.nextElementSibling.textContent);'
            'Plotly.newPlot(plot,figure.data,figure.layout,{responsive:true,displaylogo:false});})();</script></section>')
    if data['omitted']:
        coverage = (f"Showing {len(rows)} barcodes and {pooled['total']:,} post-filtered reads with complete motif exports. "
                    if pooled else "No barcodes have complete motif exports. ")
        section = section.replace('</section>', '<p class="note">' + coverage +
            'Excluded because motif data is incomplete or unavailable: ' +
            escape(', '.join(data['omitted'])) +
            '. Missing data is not counted as zero.</p></section>')
    return section


def comparison_figures(run):
    """Build charts 4/5; missing cells remain gaps, never zero-length telomeres."""
    import plotly.graph_objects as go
    from dorado_workflow.reports.reads.density import tvr_enabled
    data = comparison_data(run)
    heatmap = go.Figure()
    cells = data["cells"]
    if cells:
        chroms = sorted({c["chromosome"] for c in cells},key=lambda c:(0,int(c[3:])) if c[3:].isdigit() else (1,c))
        barcodes = [b.label for b in run.barcodes]
        lookup = {(c["barcode"],c["chromosome"]):c for c in cells}
        heatmap.add_trace(go.Heatmap(x=chroms,y=[b.replace("barcode","BC") for b in barcodes],
            z=[[lookup.get((b,c),{}).get("median_kb") for c in chroms] for b in barcodes],
            customdata=[[lookup.get((b,c),{}).get("reads",0) for c in chroms] for b in barcodes],
            colorscale="RdYlBu_r",xgap=1,ygap=1,hoverongaps=False,
            colorbar=dict(title="Median<br>length (kb)"),
            hovertemplate="%{y} / %{x}<br>Median: %{z:.3f} kb<br>%{customdata} reads<extra></extra>"))
    heatmap.update_layout(xaxis_title="Chromosome",yaxis_title="Barcode",yaxis_autorange="reversed")
    return [(4,"TVR Composition - All Barcodes",None,overview_composition_section(data, requested=tvr_enabled(run.settings))),
            (5,"Median Telomere Length by Chromosome and Barcode",heatmap,
             "Post-filtered lengths; explicit chromosome annotations or chrN/chrN_Head/chrN_Tail labels. Cross-chromosome ambiguous reads excluded; gaps mean unavailable.")]
