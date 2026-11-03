# Summary only

Summary only changes saved detail, not telomere searches, mismatch/TVR settings,
filtering, mapping or KM assessment/reporting policy.

## Shared dashboard

`dashboard_summary.html` is saved beside `nanotel_summary.xlsx`. Full and Summary
use the same overview, barcode pages, graphs, styling, table controls and exports.
Summary has no individual read screen: clicking a read point opens its barcode
and locates/highlights the corresponding row in the read table.

Each barcode has Key Statistics, the original NanoTel length distribution and
per-read length plot, TVR patterns/positions when selected and available,
chromosome comparison, and searchable/sortable before/after read tables.
Overview selection can exclude barcodes from pooled statistics and graphs while
keeping their individual results accessible.

## Saved sources

The workbook contains barcode-level Key Statistics, per-barcode read tables,
separate before-filter sheets, and relevant assessed KM statistics. Hidden
`_source_` worksheets retain raw and filtered tables, settings, input counts,
mapping facts, original barcode Plotly specifications, and motif evidence.
Long figure/motif JSON is retained in ordered chunks, not truncated to Excel's
cell limit. Native CSV/JSON sources, when present, take precedence on re-import.

The NanoTel workspace is removed only after the workbook and dashboard save
successfully. Analysis failures retain the workspace for recovery. Outputs of
separately selected mapping/modification stages and execution logs are retained.

## Skipped outputs

- Individual read screens and read images.
- Per-read FASTA and density arrays.
- Detailed filter-audit files and the extra R pipeline text report.

Barcode figures and motif evidence are retained because they supply the shared
barcode graphs. They are not replaced by a second Summary chart implementation.
Older Summary workbooks can lack original figure specifications or motif data.
Such plots remain explicitly unavailable, or disclose their numeric fallback;
missing original running medians are never inferred from another population.

Before-filter tables contain imported NanoTel summary reads, not necessarily all
input reads. R post-analysis, NanoTel final-filter and pre-edge KM populations
remain distinct and explicitly labelled. No KM fits or filtering are repeated
when rebuilding the dashboard.
