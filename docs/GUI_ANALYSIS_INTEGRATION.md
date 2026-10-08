# NanoTel analysis integration handoff

Analysis results and interactive barcode plots are implemented in NanoTel.R.
The desktop application now requests `--analysis` for full NanoTel runs and
presents the assessed KM results in a separate execution-log table. Summary-only
behavior is unchanged. HTML report implementation belongs to Inbar; the existing
standalone plot viewers are not the final report. The Python changes below are
implemented.

## First integration scope

Full NanoTel runs enable `--analysis` and show an assessed KM table in the
execution log after the existing descriptive-statistics table. No new GUI control
or reporting threshold control is needed. Keep KM-input censoring silent.

Do not enable it for summary-only runs yet. That workflow saves an Excel workbook
then deletes the temporary NanoTel tree in `RAnalyzer._cleanup_summary_workspace`.
Generating analysis JSON/plots there without a retention policy would lose them.
Summary-only analysis requires a separately agreed destination/cleanup change.

`r_analysis` remains a separate downstream phase. Its general run summaries,
filtering, mapping and TVR work are not replaced or disabled by this integration.

## Data sources for the future report

Use the task's barcode output directory, rather than assuming all files sit in
the run root. Full runs have per-barcode directories. Run KM CSVs are written
under `NanoTelProcessor.output_dir` after successful current barcode processing.

| Report element | Source | Interpretation |
| --- | --- | --- |
| Barcode analysis statistics | `<barcode>_analysis.json` | Same information as the existing analysis TXT |
| Per-barcode KM status and input censoring | `<barcode>_km_statistics.csv` | Already assessed; KM censoring is silent for now |
| Run KM observations | `km_barcode_statistics.csv` | Reportable medians and available pre-edge censoring |
| Mean barcode KM censoring | `km_run_statistics.csv` | Precomputed equal-barcode mean, not pooled censoring |
| Interactive barcode plots | `<barcode>_telomere_plot.plotly.json`, `<barcode>_telomere_histogram.plotly.json` | Ready-to-use `data`, `layout`, `config` |
| Standalone plots and static downloads | Matching `.html` and `.png` files; histogram also `_pct.png` | Existing local/offline viewer and companions |
| Existing general run statistics | Current r_analysis CSV/TXT/Excel outputs | Keep separately identified; no duplicate computation |

Only use current successful barcode artifacts. A failed barcode execution is
different from a completed barcode whose KM fit failed. The latter still has
descriptive results and an explicit KM withholding reason. Older runs without
the new files should say analysis results are unavailable, not invent zero values.

KM median/limits are JSON null or CSV blank when withheld. Render them as
"Not reported"; unavailable width is "Not available". Display the existing reason
verbatim below the table, escaped as text. Do not reapply the width threshold in
the GUI, reveal internal estimates, or replace KM with the descriptive median.
Round only for display: integer bp with separators; percentages to one decimal.
Keep the rounding explanation in a too-wide reason even if its displayed width
looks equal to the reporting limit. The 20% policy remains provisional.

The final-filter censoring in JSON/TXT differs from the pre-edge KM censoring in
CSV. The histogram uses final-filter reads; the line plot and KM use pre-edge
reads. Short-telomere percentages from r_analysis and NanoTel.R can also differ
because r_analysis may apply an additional minimum-read-length filter. Keep source
labels explicit; do not substitute one stage's values for another's.

## Python changes implemented

### 1. Activate analysis for full runs

In `dorado_workflow/processors/nanotel.py`, immediately before the existing
`if summary_only:` command branch:

```python
# Summary-only output is currently removed after Excel creation; keep its
# behavior until analysis-artifact retention is explicitly implemented.
if not summary_only:
    command_arguments.append("--analysis")
```

### 2. Notify the log only after a successful current barcode export

In `_process_barcodes_sequential`, inside its existing `try`, before building
the command:

```python
analysis_path = Path(task['output_dir']) / f"{barcode}_analysis.json"
previous_analysis_stamp = (
    analysis_path.stat().st_mtime_ns if analysis_path.exists() else None
)
```

After successful command execution and the existing
`results[barcode] = True` assignment:

```python
# Notify the GUI only after successful current-run output, never
# from a stale file. The GUI presents the already-assessed JSON.
if (analysis_path.exists()
        and analysis_path.stat().st_mtime_ns != previous_analysis_stamp):
    self.context.logger.info(f"NanoTel analysis JSON saved to: {analysis_path}")
```

This follows the same before/after freshness rule as the existing KM CSV collector.
A failed command or untouched file does not produce a KM table notification.

### 3. Render a separate KM table from the assessed JSON

In `dorado_gui/gui/sections/execution_log_section.py`, add `import json`.
In `_append_worker_log_line`, immediately before `_handle_nanotel_result_path`:

```python
if self._handle_nanotel_analysis_result(analysis_line):
    return
```

Add this method to `ExecutionLogSection`:

```python
def _handle_nanotel_analysis_result(self, analysis_line):
    """Present assessed KM output; do not refit or reapply reporting policy."""
    prefix = "NanoTel analysis JSON saved to:"
    if not analysis_line.startswith(prefix):
        return False
    self._flush_pending_nanotel_stats_table()
    try:
        path = Path(analysis_line[len(prefix):].strip())
        result = json.loads(path.read_text(encoding="utf-8"))
        barcode = result["barcode"]
        median = result["km_median_telomeric_length_bp"]
        lower = result["km_median_95_ci_lower_bp"]
        upper = result["km_median_95_ci_upper_bp"]
        width = result["km_whole_relative_ci_width_pct"]
        reason = result["km_reporting_reason"]
        # Check completeness of approved output, not a second statistical rule.
        # KM-input censoring remains in CSV only; do not add it to this table.
        reported = all(value is not None for value in (median, lower, upper))
        values = (
            str(barcode),
            f"{median:,.0f} bp" if reported else "Not reported",
            f"{lower:,.0f}-{upper:,.0f} bp" if reported else "Not reported",
            f"{width:.1f}%" if width is not None else "Not available",
            "Reported" if reported else "Not reported",
        )
        headers = ("Barcode", "KM median", "95% CI", "Whole CI width", "Reporting")
        style = "padding: 3px 7px; border: 1px solid #d7dce1;"
        header = "".join(f'<th style="{style}">{escape(label)}</th>' for label in headers)
        cells = "".join(f'<td style="{style}">{escape(value)}</td>' for value in values)
    except (OSError, ValueError, KeyError, TypeError):
        self._append_timestamped_text("    NanoTel KM report could not be read.")
        return True

    self._append_timestamped_text("    NanoTel KM reporting")
    self._append_log_line(
        f'<table style="border-collapse: collapse;"><tr>{header}</tr><tr>{cells}</tr></table>'
    )
    if reason:
        self._append_log_line(f"<p>{escape(str(reason))}</p>")
    self._append_log_blank()
    return True
```

The notification is consumed by the GUI formatter; the user sees the table,
not an additional raw file-path line. KM-input censoring is not shown. The old
six-column descriptive table remains unchanged. No NanoTel.R edit is proposed.

## HTML work for Inbar

Embed the Plotly specifications using one shared Plotly runtime and their saved
data/layout/config. Preserve unit-switch buttons, legend toggling, hover, separate
censored strip and PNG downloads. Do not rebuild bins or recompute the trend/KM.
Provide a saved offline report and optional static downloads. The generated
standalone HTML files are useful previews, not a replacement desktop application.

Choose a file-loading strategy that works when opening the saved report locally;
do not assume browser fetch of sibling JSON files will work from file:// URLs.
Embedding the required data when generating the report is one possible approach.
The report must identify missing/failed barcode results and not rediscover stale
files from older runs. TVR, chromosome and read-level panels require separately
agreed outputs from their owners; these NanoTel analysis files do not supply them.

Across-barcode KM-median and censoring histograms are a later plot task. Bimodal
fitting/research remains deferred.

## Verification before accepting the connection

- Check command arguments: full run includes --analysis; summary-only does not.
- Check fresh success, untouched old output, failed execution and paths with spaces.
- Check the GUI table for reportable, too-wide, non-estimable, invalid and failed KM.
- Check missing/malformed JSON: readable message, no GUI crash or invented result.
- Keep reasons escaped, numbers formatted, descriptive results separate and KM
  censoring hidden. Verify the table follows the existing descriptive table.
- Run focused tests, R parsing/whitespace checks as applicable; no research reruns.

Focused tests execute the real command/notification methods and isolate the actual
GUI renderer/routing methods without requiring Qt. They cover both command modes,
fresh/stale/failed notifications, all KM reporting outcomes, escaped reasons,
paths with spaces, missing/malformed files and keeping censoring hidden. Existing
R analysis, plot and KM-export regression tests remain part of the suite.
A full desktop GUI/FASTQ smoke test remains separate; these tests do not start Qt.
