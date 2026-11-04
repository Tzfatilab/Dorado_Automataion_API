# Recalculate results

Select **Existing project** in Input Data, or **Recalculate results** in Analysis Steps. This mode is separate from Basecalling and NanoTel; it enters the existing workflow after NanoTel detection.

**Analysis Options** is the same panel in both modes. Recalculation locks TVR and mismatch options to the original settings. Editable thresholds are minimum read length, latest telomere start (also the read margin), minimum repeat density and the short-telomere cutoff. Organism is loaded from original metadata when available. For legacy metadata without an organism, select the original organism explicitly.

Choose an Output Path outside the source project. A new timestamped run preserves the original data and records its source in `results/reports/post_analysis_source.json`. The **Summary only** toggle remains editable and initially follows the source run. Summary mode writes barcode pages and read tables without individual read pages; full mode uses the normal full dashboard and workbook writer. Full mode can only display saved measurements: missing sequence/density exports from a Summary source are not reconstructed. The original source evidence workbook is retained under `results/reports/post_analysis_sources` for full recalculations.

## Source requirements

- An original `results/nanotel` CSV population, or `nanotel_summary.xlsx` containing original source worksheets. A presentation-only spreadsheet or standalone HTML cannot supply the original population.
- Original detection settings in `results/reports/nanotel_source_settings.json`, the original R configuration, or workbook Run metadata. The NanoTel processor now saves a detection snapshot before starting, for both GUI and CLI runs.
- Mapping additionally needs original `processing/aligned` BAMs, or `processing/fastq` sequences if new alignment is necessary. Existing aligned BAMs are reused through AlignmentProcessor, without repeating basecalling or NanoTel detection.

## Shared implementation

`WorkflowOperator.run_post_analysis` is the common tail for normal POD5, FASTQ, NanoTel Summary and existing-project workflows. It delegates to the existing RAnalyzer, filtration/mapping functions and report/workbook writers. `ProjectSources` in `processors/project_sources.py` only discovers and restores original populations and evidence to a fresh run; it does not implement new filtering or mapping formulas.

Threshold changes filter existing measurements; they do not recalculate NanoTel interval boundaries or densities. The first detection settings remain recorded separately in `source_detection_settings`, including after repeated recalculation.

Old filtered rows, mappings and aggregate figures are not reused as new results. Source counts, motifs, repeat coverage and KM evidence are retained when available. Unavailable measurements stay unavailable. The original detected population may be smaller than all input reads; recalculation cannot recover reads never exported by NanoTel.

Mapping subprocesses use direct samtools arguments rather than Unix shell pipelines, so BAM read-ID extraction and filtering work on Windows too. Mapping thresholds are unchanged.

## Disk usage

Recalculation links native source CSVs, read files, detail exports and existing
aligned BAMs instead of copying them. Hard links share the original file's disk
storage; file symlinks are used when hard links are unavailable. If neither is
supported, the run reports an error rather than silently copying large inputs.
Linked detail exports are not repacked into duplicate archives. Inputs must be
treated as immutable; symlinked sources must remain accessible.

Workbook-only populations still need CSV extraction for the R pipeline. Archived
details need extraction, and evidence workbooks and updated Excel/dashboard,
filtered tables, mapping outputs and BAM indexes are newly generated outputs.
