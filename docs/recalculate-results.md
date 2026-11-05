# Recalculate results

Select **Existing project** in Input Data, or **Recalculate results** in Analysis Steps. This mode is separate from Basecalling and NanoTel; it enters the existing workflow after NanoTel detection.

**Analysis Options** is the same panel in both modes. Recalculation locks TVR and mismatch options to the original settings. Editable thresholds are minimum read length, latest telomere start (also the read margin), minimum repeat density and the short-telomere cutoff. Organism is loaded from original metadata when available. For legacy metadata without an organism, select the original organism explicitly.

Choose an Output Path outside the source project. A new timestamped run preserves the original data and records its source in `results/reports/post_analysis_source.json`. The **Summary only** toggle remains editable and initially follows the source run. Summary mode writes barcode pages and read tables without individual read pages; full mode uses the normal full dashboard and workbook writer. Full mode can only display saved measurements: missing sequence/density exports from a Summary source are not reconstructed. The original source evidence workbook is retained under `results/reports/post_analysis_sources` for full recalculations.

## Source requirements

- An original `results/nanotel` CSV population, or `nanotel_summary.xlsx` containing original source worksheets. A presentation-only spreadsheet or standalone HTML cannot supply the original population.
- Original detection settings in `results/reports/nanotel_source_settings.json`, the original R configuration, or workbook Run metadata. The NanoTel processor now saves a detection snapshot before starting, for both GUI and CLI runs.
- When Run mapping is selected, alignment is always recalculated through AlignmentProcessor. Prefer saved `processing/fastq` reads, then FASTQ or BAM inputs under `processing/demultiplexed`; aligned BAMs are a fallback sequence source and are realigned. A candidate input directory must cover every nonempty original NanoTel barcode. Partial cached alignment output must not silently limit the run to one barcode. Basecalling and NanoTel detection are not repeated.

## Shared implementation

`WorkflowOperator.run_post_analysis` is the common tail for normal POD5, FASTQ, NanoTel Summary and existing-project workflows. It delegates to the existing RAnalyzer, filtration/mapping functions and report/workbook writers. `ProjectSources` in `processors/project_sources.py` only discovers and restores original populations and evidence to a fresh run; it does not implement new filtering or mapping formulas.

Threshold changes filter existing measurements; they do not recalculate NanoTel interval boundaries or densities. The first detection settings remain recorded separately in `source_detection_settings`, including after repeated recalculation.

Old filtered rows, mappings and aggregate figures are not reused as new results. Source counts, motifs, repeat coverage and KM evidence are retained when available. Unavailable measurements stay unavailable. The original detected population may be smaller than all input reads; recalculation cannot recover reads never exported by NanoTel.

Missing length histograms are rebuilt from the current post-filtered reads using
the original NanoTel R histogram builder, shared with normal analysis. This keeps
the original `pretty(..., n=45)` bins, Gaussian observed-length smoothing, and
count/percentage controls. There is no alternate automatic-bin histogram.
All barcodes are rendered in one R process; temporary plot requests are removed.

Loose `barcodeXX_analysis.json` files are intermediate outputs. After the full
dashboard and automatic Excel workbook save successfully, their original fields
are retained in a hidden analysis-facts worksheet and the loose JSON files are
removed. Rebuilding and recalculation restore those fields from Excel. Files are
kept on failure or if their fields do not match the saved worksheet. Before-filter
summary CSVs remain available for recalculation.

When TVR motifs were not selected but one mismatch was enabled, the repeat panels
show mismatch composition from the saved motif exports. The position panel is
shown only when specific TVR motifs were selected.
These use the exported mismatch-inclusive intervals and observed matched sequences;
they do not subtract density curves or rerun repeat searches. Partial matches are
shown separately and are not classified as mismatches. The overview uses the same
definition when barcodes are excluded. TVR-specific Key Statistics stay distinct.

Motif plots distinguish exact observed matches from the searched motif name.
An imperfect AACCGC hit is grouped under `Mismatch`; an exact AACCGC hit keeps
its motif label. This rule applies to composition, position and read tracks.
TVR-positive read counts still follow NanoTel's recorded search tolerance;
relabeling does not change scientific calls.

Mapping subprocesses use direct samtools arguments rather than Unix shell pipelines, so BAM read-ID extraction and filtering work on Windows too. Mapping thresholds are unchanged.

## Disk usage

Recalculation links native source CSVs, read files, detail exports and saved BAM
inputs instead of copying them. FASTQ inputs are read directly; fresh aligned
BAMs and their indexes are new analysis outputs. Hard links share the original file's disk
storage; file symlinks are used when hard links are unavailable. If neither is
supported, the run reports an error rather than silently copying large inputs.
Linked detail exports are not repacked into duplicate archives. Inputs must be
treated as immutable; symlinked sources must remain accessible.

Workbook-only populations still need CSV extraction for the R pipeline. Archived
details need extraction, and evidence workbooks and updated Excel/dashboard,
filtered tables, mapping outputs and BAM indexes are newly generated outputs.
