# Telomere Analyzer

Process Oxford Nanopore POD5, BAM and FASTQ data with Dorado, NanoTel, minimap2,
samtools and downstream R analysis. The GUI is the installed entry point;
the backend commands remain available for source-based workflows.

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

Select input, output directory, organism and workflow stages. The GUI creates a
new timestamped run directory. Cancel stops active commands and prevents later
stages from starting; user cancellation is recorded separately from failure.

Open **Settings & Configuration** in the sidebar. **Profile settings** contains
the sequencing kit, organism-specific TVR patterns and analysis defaults. **App settings** contains the shared Dorado model folder,
reference genomes for each organism, and default output folder.
Add sequences individually or paste a list; removal and
restoring defaults support Undo. TVR presets are separate for Mouse, Human and
Zebrafish. Telomere and TSQ1 motifs stay in the configuration and are not editable
in Settings; TSQ1 mode remains available on Pipeline Setup. An empty TVR
preset is allowed. Each TVR must contain at least five A/C/G/T bases, including
bulk-pasted, imported and run-time patterns. Kit choices come from the official
[Dorado CLI reference](https://software-docs.nanoporetech.com/dorado/latest/barcoding/barcoding/#cli-reference).
The dropdown also preserves existing profile kit IDs; choose a kit supported by
your installed Dorado version.

**Save profile** activates the selected profile for subsequent GUI runs.
**Save app settings** saves shared paths independently, without committing profile
edits. Existing/imported profiles with different paths retain clearly marked custom
paths; choose **Use app paths**, then **Save profile**, to adopt shared paths.
Old settings files migrate on the next save without losing custom resource paths.
The compact **Analysis defaults** card saves minimum read length, short telomere
cutoff, maximum edge distance, maximum telomere start, and minimum density with
each organism within each profile. Switching the organism in Settings loads its
own values; older profiles use their profile-wide values until edited.
Selecting a profile or organism fills Pipeline Setup; run-specific edits can
still override these defaults. The existing adjustment for untrimmed reads applies.
Choose a saved **Profile** at the bottom of the dark blue sidebar.
The selected profile supplies the configuration for the next run.
**Create new profile** creates a named profile, and **Import / Export** uses workflow
configuration JSON (exports also work with the backend `--config` option).
**Delete profile** removes a saved profile after confirmation. Lab default is
protected; deleting the active profile switches back to Lab default.
Changes are staged until saved, with Save/Discard/Cancel when leaving the page.
Profiles are stored in the operating system's user configuration directory under
`TelomereAnalyzer/profiles.json`, independently of `default_config.json`.
Every run receives a copy of the saved configuration; editing settings during a
run does not alter it. Pipeline Setup retains run-specific analysis overrides.

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
