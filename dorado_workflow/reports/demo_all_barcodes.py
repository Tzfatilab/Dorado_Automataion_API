"""Reproducible synthetic data for visually reviewing the All Barcodes report.

Run: python -m dorado_workflow.reports.demo_all_barcodes --output test/demo-report
No experimental files are read or modified. All generated values are fictitious.
"""
import argparse
import json
import random
from dataclasses import asdict
from pathlib import Path
from statistics import median

from dorado_workflow.reports.overview.dashboard import render_screen
from .interactive.models import Availability as A, Barcode, Fact, Read, Run, safe_id, unavailable


def demo_run(seed=42):
    """Create internally consistent fictional counts, reads, motifs and mappings."""
    rng = random.Random(seed)
    def fact(value):
        return Fact(A.AVAILABLE, value, origin="presentation_aggregate", population="synthetic_demo")
    barcodes = []
    motifs = ["TTAGGG", "TCAGGG", "TGAGGG", "TTGGGG", "CTAGGG"]
    for index in range(12):
        label = f"barcode{index+1:02d}"
        barcode = Barcode(safe_id("b", "demo", label), label)
        records = []
        count = 100 + index*9
        for number in range(count):
            rid = safe_id("r", "demo", label, str(number))
            chromosome = f"chr{number%22+1}" if number%24<22 else ["chrX","chrY"][number%24-22]
            # Vary barcode centers and chromosome trends to make the box plots
            # and heatmap useful to inspect; these are not biological estimates.
            length = max(300, int(rng.lognormvariate(8.1+index*.055+(number%6)*.05,.5)))
            interval = fact(dict(start=0,end=length,convention="zero_based_half_open",space="nanotel_analyzed_read"))
            hits = []
            weights = [0.55 + .025*(index%4), .20-.012*(index%4), .11,.08,.06]
            for position in range(40):
                motif = rng.choices(motifs,weights=weights)[0]
                hits.append(dict(method="tvr_inclusive",motif=motif,matched_sequence=motif,
                    role="canonical" if motif=="TTAGGG" else "tvr",max_mismatch=0,start=position*6,end=position*6+6))
            calls = {key:dict(interval=interval,reported_length=fact(length)) for key in ["exact","mismatch","tvr_inclusive"]}
            barcode.reads.append(Read(rid,f"demo_read_{index+1:02d}_{number:04d}",barcode.id,
                {"read_length":fact(length+15000)},calls,fact("present_in_filtered_output"),
                fact([dict(reference=fact(chromosome),chromosome=fact(chromosome),mapq=fact(60))]),
                {"motifs":fact(dict(methods=["tvr_inclusive"],matches=hits))},[]))
            records.append(dict(read_id=rid,original_id=barcode.reads[-1].original_id,length_bp=length))
        barcode.metrics={"total_reads":fact(count*7+index*83),"amount_of_telomeres":fact(count),
            "detected_telomeric_reads":fact(count+20),"median_telomere_length":fact(median(r["length_bp"] for r in records)),
            "filtered_length_records":fact(records)}
        barcodes.append(barcode)
    return Run(safe_id("run","synthetic-demo"),"Synthetic demonstration",fact("Demo organism"),fact({}),{},barcodes,[],
               {"barcode_count":fact(12),
                # Count explicit synthetic chromosome annotations, not references.
                "detected_chromosomes":fact(len({
                    alignment["chromosome"].value
                    for barcode in barcodes for read in barcode.reads
                    for alignment in read.alignments.value
                }))},["SYNTHETIC DEMO: not experimental results"])


def main():
    """Write the demo separately and refuse to overwrite an existing folder."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new output folder.")
    run=demo_run()
    page=render_screen(run)
    # The banner is embedded, so screenshots and shared HTML retain the warning.
    page=page.replace("<main>",'<main><p style="background:#fff0ca;padding:12px 18px;border-radius:8px;font-weight:600">SYNTHETIC DEMO DATA - 12 fictional barcodes. For design review only; not experimental results.</p>')
    args.output.mkdir(parents=True)
    (args.output/"index.html").write_text(page,encoding="utf-8")
    (args.output/"synthetic-data.json").write_text(json.dumps(asdict(run),indent=2),encoding="utf-8")
    print((args.output/"index.html").resolve())


if __name__=="__main__":
    main()
