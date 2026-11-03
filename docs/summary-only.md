# Summary only

Summary only changes output detail, not the telomere search, mismatch/TVR settings,
filters, or KM assessment/reporting policy.

## Saved automatically

- `nanotel_summary.xlsx` in the configured post-analysis results directory: combined barcode statistics, raw NanoTel read
  summaries, R post-filter read tables, NanoTel final-filter read tables, numeric
  analysis facts, and available KM barcode/run statistics.
- KM retains its source status, confidence interval and pre-edge input population;
  it is not substituted for the ordinary post-filter median. Withheld KM estimates
  remain unavailable.
- Execution logs, configuration, and outputs of separately selected mapping or
  modification stages remain available in their normal locations.

## Compact dashboard

`dashboard_summary.html` is saved next to the workbook before intermediate files
are removed. It includes key statistics, barcode length/count/short-telomere
comparisons, non-human KM/completeness tables, and searchable, paginated barcode
read tables before/after filtering. It opens offline and links to the workbook.
There are no individual read pages or per-read track plots. The read columns
follow the recorded TVR/mismatch mode, including TVR content, canonical content
and block counts when those measurements were exported. The violin uses the same
1 kb bandwidth as the full dashboard; single-value groups remain visible as points.

The visible workbook layout matches the full export: barcode-level Key Statistics
in `Barcode summary`, individual read Key Statistics in the barcode worksheets,
and separate before-filter and KM sheets. Hidden `_source_` worksheets retain the
original numeric source tables, settings, input counts and mapping facts so that
re-importing the workbook after cleanup does not lose those measurements. CSV/JSON
files, when present, remain authoritative over workbook fallbacks.

## Skipped
- NanoTel per-read FASTA, read plots, density/motif track exports and read-ID lists.
- Standalone NanoTel aggregate analysis plots (HTML, images and Plotly JSON).
  Summary comparison charts are rendered directly inside the compact dashboard.
- Detailed filter-audit exports and the extra R pipeline text report.

Numeric CSV/JSON/TXT files needed during analysis are temporary. The NanoTel
workspace is removed only after the workbook is successfully saved. A failure
keeps the workspace for diagnosis/recovery. No rerun of the detector is needed
for the workbook, but summary-only results cannot reconstruct detailed tracks;
run full mode if those are needed.

Before-filter tables contain imported NanoTel summary reads, not necessarily all
input/basecalled reads. R post-filter, NanoTel final-filter and pre-edge KM are
separate populations and are labelled separately in the workbook.
