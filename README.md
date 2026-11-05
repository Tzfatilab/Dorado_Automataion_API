# Telomere Analyzer

Analyze Oxford Nanopore telomere sequencing data through a graphical workflow
for Human, Mouse and Zebrafish. Start from raw POD5 signals, basecalled BAM or
FASTQ reads, or an existing NanoTel project.

The workflow combines Dorado basecalling and barcode separation, NanoTel
telomere detection, optional chromosome mapping, and downstream filtering and
statistics. Results are saved as an interactive HTML dashboard and an Excel
workbook, with barcode summaries and read-level measurements.

Use **Recalculate results** to change post-analysis filters and rebuild reports
from saved NanoTel measurements without repeating basecalling or sequence-level
telomere detection. The GUI is the installed entry point; backend commands remain
available for source-based workflows.

## Installation and tools

Use Python 3.10 or newer. Install the Python package from the repository root:

```sh
python -m pip install .
```

Python dependencies are declared in `pyproject.toml` (PySide6 and openpyxl).
Install external tools separately and make them available in `PATH`:

- Dorado for basecalling and demultiplexing, plus the appropriate model.
- R / Rscript and the packages listed in [R dependencies](packaging/R_DEPENDENCIES.md).
- samtools for BAM conversion, indexing and inspection.
- minimap2 for new reference alignments.
- modkit when methylation pileup is requested.

Reference FASTA files and Dorado models must be supplied locally. See
[packaging notes](packaging/README.md) for resource and distribution limitations.
No dependencies were added by the readability refactor.

## Run the GUI

```sh
telomere-analyzer
```

From a source checkout:

```sh
python -m dorado_gui.main
```

### Choose input and analysis steps

On **Pipeline Setup**, choose a saved **Profile**, select the organism, and set
the input folder and **Output Path**. Then select the required **Analysis Steps**:

| Input Data | Analysis Steps | Purpose |
| --- | --- | --- |
| **POD5 (Raw Signals)** | **Basecalling**, optionally followed by **NanoTel Analysis** | Call bases and separate barcodes; add NanoTel to analyze telomeres. |
| **BAM (Basecalled)** | **NanoTel Analysis** | Convert existing basecalled reads to FASTQ for telomere analysis. |
| **FASTQ** | **NanoTel Analysis** | Analyze sequence reads; use barcode folders directly or demultiplex unsplit input with the configured kit. |
| **Existing project** | **Recalculate results** | Refilter saved NanoTel measurements and regenerate reports. |

For a complete POD5-to-telomere workflow, select both **Basecalling** and
**NanoTel Analysis**. **Recalculate results** runs separately from those steps.
Mapping and base-modification options are available in their corresponding
analysis panels and require the appropriate reference files and tools.

Each run creates a new timestamped output directory. Follow progress in the
execution log and open the generated HTML report when the run completes.
**Cancel** stops active commands and prevents subsequent stages from starting.

### Analysis Options

Profile and organism defaults fill these controls; edit them on Pipeline Setup
to override them for the next run.

| Control | Meaning |
| --- | --- |
| **Minimum read length (bp)** | Minimum total read length, including sequence outside the telomere. |
| **Latest telomere start (bp)** | Latest accepted telomere start in the analyzed read. The same value also sets the read-margin/edge-distance threshold internally. |
| **Minimum density (%)** | Minimum telomeric repeat density, entered as a percentage in the GUI. |
| **Short telomere cutoff (bp)** | Length strictly below which a telomere is counted as short. This reporting cutoff does not itself remove reads. |
| **Run mapping** | Include chromosome mapping in the analysis. |
| **Allow 1 mismatch** | Allow one difference when searching canonical and selected TVR motifs. |
| **Summary only** | Generate the shared dashboard with barcode pages and read tables, plus Excel, while omitting individual-read pages and detailed NanoTel outputs. |

Under **TVR Mode**, select **Preset**, **TSQ1**, **Manual**, or a combination.
Leave all modes unselected to analyze canonical telomeres without selected TVR
patterns. **Preset** forces exact matching and disables **Allow 1 mismatch**.
**TSQ1** initially enables that checkbox; it can be cleared when Preset is not
selected. Manual patterns must contain at least five A/C/G/T bases.

### Recalculate results from an existing project

1. Select **Existing project** and choose the original project or its `results` folder.
2. Select **Recalculate results** under **Analysis Steps**.
3. Adjust the four numeric analysis options and choose whether to run mapping.
4. Choose **Summary only** or a full report, then set an **Output Path** outside the source project.
5. Run the analysis to regenerate filtered results, Excel and the dashboard.

Original TVR and mismatch settings are loaded from the source run and locked;
changing them requires a new NanoTel detection run. The recorded trimming state
is reused when available; legacy projects may require confirmation of whether
the reads were trimmed.

Recalculation requires the original before-filter NanoTel CSVs or the retained
source worksheets in `nanotel_summary.xlsx`, together with the original analysis
settings. A standalone dashboard or presentation-only Excel export is insufficient.
Mapping additionally requires saved read inputs. The source project is preserved,
and existing source files are linked where supported instead of copied.

A full report can reuse saved read sequences and detail tracks. Recalculation
does not recreate details that were never exported by the original run. See
[recalculation details](docs/recalculate-results.md) for source requirements.

### View results

The dashboard provides an overview and individual barcode pages with statistics,
length plots and searchable, sortable read tables. Available mapping and repeat
details depend on the selected analyses and saved source data. Full reports also
provide individual-read views; **Summary only** omits those views.

Barcode display names can be edited while keeping the original barcode ID
visible. Excluding a barcode removes it from overview graphs and the Key Statistics
table; its barcode page remains accessible. Graphs and tables have save controls,
and an Excel workbook is saved automatically with the run. Browser-only names
and exclusions do not modify that automatic workbook.

Short-telomere percentages use the configured cutoff and the exported
post-filtered telomeric reads for each barcode. Missing or incomplete source
measurements are shown as **Unavailable**, rather than as zero.

### Settings and profiles

Open **Settings & Configuration** in the sidebar:

- **Profile settings** stores the sequencing kit, organism-specific TVR presets
  and analysis defaults. Each organism has its own minimum read length, latest
  telomere start, minimum density and short-telomere cutoff within the profile.
- **App settings** stores shared Dorado model paths, reference genomes and the
  default output folder. **Save app settings** saves these independently of profile edits.

TVR presets are separate for Human, Mouse and Zebrafish. Add sequences individually
or paste a list; removal and restoring defaults support Undo. Empty presets are
allowed, and each pattern must contain at least five A/C/G/T bases. Canonical
telomere and TSQ1 motifs remain in the configuration and are not editable on the
Settings page. Choose a kit supported by your installed Dorado version; the kit
list follows the official
[Dorado CLI reference](https://software-docs.nanoporetech.com/dorado/latest/barcoding/barcoding/#cli-reference)
and preserves existing profile kit IDs.

Choose the active **Profile** at the bottom of the sidebar. **Save profile** saves
and activates its settings for subsequent runs. Profiles with custom resource
paths retain them; select **Use app paths**, then **Save profile**, to adopt shared paths.
Older settings migrate on save without losing custom paths.

Use **Create new profile**, **Import / Export**, or **Delete profile** to manage
profiles. Import/export uses workflow configuration JSON, also usable with the
backend `--config` option. **Lab default** cannot be deleted; deleting the active
profile switches back to it. Unsaved edits offer Save/Discard/Cancel when leaving
the page.

Profiles are stored in the operating system's user configuration directory at
`TelomereAnalyzer/profiles.json`, separately from `default_config.json`.
Each run receives its own configuration snapshot, so editing settings during a
run does not change that run's parameters.

## Run backend commands

Run these commands from the repository root. Global options `--config` and
`--output-dir` must precede the subcommand.

```sh
python -m dorado_workflow.main --help
python -m dorado_workflow.main --config lab_config.json --output-dir runs pod5 Trial_75 /data/pod5 --organism mouse
python -m dorado_workflow.main --config lab_config.json --output-dir runs fastq Trial_75 /data/fastq --organism human
python -m dorado_workflow.main --config lab_config.json --output-dir runs nanotel Trial_75 /data/fastq
python -m dorado_workflow.main --config lab_config.json --output-dir runs align Trial_75 /data/fastq --organism mouse
python -m dorado_workflow.main --config lab_config.json --output-dir runs r-analysis Trial_75 --no-mapping --no-methylation
```

The existing commands are `pod5`, `fastq`, `nanotel`, `align` and `r-analysis`.
The existing organisms are `mouse`, `human` and `zebrafish`. `r-analysis` keeps its
`--no-filtration`, `--no-mapping` and `--no-methylation` switches. Use an individual
subcommand's `--help` for its arguments. The installed `telomere-analyzer` command
launches the GUI; it does not accept these backend subcommands.

The FASTQ workflow prepares barcode inputs, runs NanoTel, aligns and filters.
The `nanotel` command expects a directory containing barcode folders. The POD5
backend command uses the operator's existing defaults; it does not expose GUI
methylation/mapping switches. Select those options through the GUI when needed.
The raw NanoTel CLI remains available as `Rscript dorado_workflow/data/NanoTel.R --help`.

Example barcode layout:

```text
fastq/
  barcode02/reads.fastq
  barcode19/reads.fastq.gz
```

Do not mix unsplit FASTQ files at the root with barcode folders. Missing files,
empty uncompressed FASTQ files, invalid numerical settings and malformed summary
columns produce explicit errors. Missing analysis values are reported; existing
NA filtering rules are retained rather than converting unknown values to zeros.
An empty filtered result is distinct from a failed analysis.

## Configuration and units

Copy `dorado_workflow/configs/default_config.json` to a lab configuration file,
then set the paths for reference genomes, the Dorado model and the output root.
Relative configured resource paths are resolved against `dorado_workflow/`,
not against the shell's current directory. The GUI currently uses the bundled
configuration plus its on-screen overrides; `--config` is a backend option.

Existing setting names and defaults are retained. In `nanotel`:

- `min_density` and `density_threshold` are fractions between 0 and 1.
- `max_mismatch` is 0 or 1, shared by canonical and TVR searches.
- `short_telomere_threshold_bp` is a positive integer in base pairs.
- `min_read_length`, `read_length`, `max_telomere_start` and `max_edge_distance`
  are measured in base pairs. Optional minimum-length filtering can be disabled
  with null. Existing precedence is retained: the R batch reader prefers
  `min_read_length` over `read_length` when both are present.
- TVR presets, manual patterns and TSQ1 settings keep their current behavior.

Operational constants are documented in `utils/analysis_constants.py`: 10,000
reads per NanoTel chunk (progress estimation), four lines per unwrapped FASTQ
record and a 0.05-second pipeline polling interval. They do not change biological
thresholds. The four-line counter is a progress estimate, not a full FASTQ validator.

## Output files

Default layout (directory names can be configured):

```text
<output_base>/<trial_or_timestamped_run>/
  processing/
    basecalled/
    demultiplexed/
    fastq/
    aligned/
  results/
    nanotel/
    mapping/
    methylation/
    nanotel_summary.xlsx       # Summary mode
  logs/
```

Full mode retains per-barcode NanoTel outputs. Summary mode packages raw and
filtered CSV data into `nanotel_summary.xlsx`, then cleans the temporary NanoTel
tree only after saving succeeds. CSV column names, worksheet layout and existing
output filenames are preserved. `nanotel_summary_statistics.csv` retains its
threshold-dependent `below_<threshold>bp_pct` column. Alignment writes a temporary
BAM and publishes the final filename only if every pipeline tool succeeds.

## Module responsibilities

- `dorado_workflow/operators/`: stage orchestration and cancellation boundaries.
- `dorado_workflow/processors/`: tool execution and stage-specific validation.
- `dorado_workflow/managers/`: paths, configuration and barcode bookkeeping.
- `dorado_workflow/data/NanoTel.R`: sequence-level telomere detection.
- `dorado_workflow/r_analysis/functions/`: downstream calculations and filtering.
  `calculate_nanotel_summary_stats()` performs calculation without file output;
  its existing caller handles writing and logging.
- `dorado_workflow/reports/nanotel_workbook.py`: Excel rendering from CSV results.
- `dorado_workflow/utils/`: logging, command execution, quoting, cancellation,
  numerical-setting validation and operational constants.
- `dorado_gui/services/`: GUI-to-workflow settings and dispatch.
- `dorado_gui/gui/sections/execution_log_section.py`: log and progress presentation.
- `dorado_gui/gui/widgets/advanced_controls.py`: reusable advanced-option controls.

## Verification

```sh
python -m unittest discover -s tests -v
Rscript tests/test_analysis_results.R
```

The R check calls production calculations on synthetic canonical, mismatch,
TVR, TVR-with-mismatch and non-telomeric reads. It compares per-read results,
per-barcode filtering and summary statistics with a captured baseline, including
missing observations. It does not run plotting or parallel chunk workers.
The Python checks cover workbook content/formatting, GUI presentation, settings,
command failures, cancellation and synthetic minimap2/samtools alignment.
See [test notes](tests/README.md). Tests do not replace validation on a representative
real sequencing run or establish biological accuracy.

## Follow-up work

Review these separately before changing scientific behavior:

- Reconcile `read_length` and `min_read_length` precedence between GUI and R.
- Investigate exact TVR matching when patterns are supplied as a scalar string
  rather than a list; the core R branches are not identical.
- Validate full plotting, parallel processing, mapping and methylation on real
  lab data, including truncated/compressed FASTQ inputs and missing-value cases.
