# NanoTel.R --analysis outputs

These outputs belong to NanoTel.R's optional `--analysis` block, separate from
`r_analysis`. Existing TXT, CSV and PNG outputs remain available. The application
command does not yet enable `--analysis`; this change does not enable GUI analysis
or add visible KM censoring information.

## Barcode files

`<barcode>_analysis.json` contains the same information as `<barcode>_results.txt`:
barcode, final-filter read/complete/incomplete counts and censoring percentage,
final-filter descriptive median, short-telomere threshold and percentage, and
assessed KM median, confidence limits, whole relative CI width and reason.
Numbers use bp and percentages use 0–100. KM values are unrounded; display rounding
belongs to the report. A withheld median and its limits are JSON `null`; unavailable
widths and non-finite descriptive values are also `null`. No raw withheld estimates
are exported. The threshold field records the value used in the TXT row label.

`<barcode>_km_statistics.csv` stores one assessed KM row plus KM-input counts and
censoring percentage. KM uses density/start-filtered reads **before** edge filtering;
complete means `sequence_length - selected_telomere_end >= 50 bp`. These counts and
rates differ from final-filter statistics. They are exported silently, not added
to the visible TXT or GUI log. Empty KM input or any non-finite completeness margin
makes its rate unavailable (blank); no unknown classification is silently counted.
An estimation failure may still have an available censoring rate.

The short-telomere percentage in this JSON/TXT uses NanoTel.R's final-filter reads.
`r_analysis` uses the same configurable threshold (default 2000 bp) on its own
filtered data, possibly with an additional minimum-read-length filter. Its
`below_<threshold>bp_pct` value is not an interchangeable source. The threshold is
descriptive only: it does not filter reads or affect KM fitting/reportability.

## Run files

The NanoTel processor combines only newly produced KM CSVs from successful barcode
executions in the current run. It does not scan old outputs or recompute KM fits.
Failed executions are excluded; a completed barcode whose KM fit failed is retained
with `km_status=failed`. Counts in these files cover contributing barcode exports,
not every barcode expected in the workflow.

- `km_barcode_statistics.csv`: one row per contributing barcode. Median and limits
  are blank unless `km_status=reportable`; width and withholding reason are retained
  when available. Histogram inputs are the saved barcode medians and KM censoring
  rates. Withheld medians are excluded from the median histogram.
- `km_run_statistics.csv`: counts of reportable/withheld KM results, count of
  available censoring rates, and their arithmetic mean. Each barcode has equal
  weight, including withheld medians when their censoring is available. An empty
  set has zero counts and a blank mean. This is not pooled censoring or pooled KM.

If a reused output directory contains old run KM files but the current run produces
no KM exports, the processor replaces the old aggregates with empty results.
General run statistics remain owned by `r_analysis`; these KM files do not duplicate
its CSV/TXT/Excel summaries. GUI/HTML should read these outputs rather than calculate
statistics from formatted logs. Histogram bins and interactive plots are deferred.

For standalone R barcode runs, combine their CSVs explicitly after processing:

```text
python -m dorado_workflow.reports.km_statistics --output-dir RESULTS barcode01_km_statistics.csv barcode02_km_statistics.csv
```

NanoTel JSON export requires `jsonlite`, already declared in the Bioconda recipe.
