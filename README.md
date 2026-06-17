# Dorado Automation API

A modular command-line workflow for processing Oxford Nanopore sequencing data with **Dorado**, **NanoTel**, and downstream **R-based analysis**.

This repository automates the sequencing workflow used in the lab, starting from raw sequencing outputs and producing telomere-related analysis outputs. The pipeline organizes the full process into clear stages that can be executed together or individually.

The workflow supports:

* **Basecalling** from POD5 files using Dorado
* **Demultiplexing** reads into barcode-specific outputs
* **NanoTel telomere analysis** on FASTQ files
* **Reference alignment** with Dorado
* **Downstream R analysis** for filtration, mapping, and methylation
* **Centralized logging and command tracking**

---

## Graphical User Interface (GUI)

The Dorado Automation API is also available through the Telomere Analyzer graphical interface, providing a user-friendly way to configure and execute Oxford Nanopore sequencing workflows without requiring command-line interaction. The graphical interface is supported on both Linux and Windows systems; however, due to limitations in parallel processing and process management on Windows, workflow execution may be slower. For optimal performance and stability, running the software on Linux is recommended.

* <img width="2864" height="1662" alt="image" src="https://github.com/user-attachments/assets/fb120896-465c-4378-aa5c-a7c28a899c16" />

### Main Features

#### Input Data Selection

The GUI supports multiple starting points in the sequencing workflow:

* **POD5 (Raw Signals)** – Perform Dorado basecalling from raw nanopore signals.
* **BAM (Basecalled)** – Continue analysis from existing basecalled BAM files.
* **FASTQ** – Run downstream analysis using existing FASTQ files.

#### Pipeline Configuration

Users can configure:

* Input and output directories
* Organism-specific reference settings
* Analysis workflow components
* Basecalling parameters
* NanoTel telomere analysis options

#### Analysis Modules

The interface provides access to the following workflow stages:

##### Basecalling

* Dorado basecalling from POD5 files
* Optional modified-base detection:

  * CpG (5mC)
  * CpG + Hydroxymethylation (5hmC)
* Optional chromosome mapping during basecalling

##### NanoTel Analysis

* Telomere repeat analysis
* TVR (Telomere Variant Repeat) detection
* Preset or custom TVR configurations
* Adjustable filtering parameters:

  * Minimum read length
  * Minimum density threshold
  * Edge distance settings

#### Workflow Execution

Once configured, users can launch the workflow directly from the GUI. The application automatically executes the selected analysis stages and organizes outputs into the configured project directory structure.

### Benefits

* No command-line experience required
* Centralized configuration management
* Simplified workflow execution
* Consistent analysis settings
* Reduced risk of user input errors
* Seamless integration with the Dorado Automation backend

The GUI serves as a front-end for the Dorado Automation API, ensuring that both graphical and command-line executions rely on the same validated workflow engine.

### Structure

```text
dorado_gui/
│
├── main.py                         # Application entry point
│
├── core/                           # Core application logic
│   ├── __init__.py
│   ├── stream_to_gui.py            # Redirect console output to GUI
│   ├── validators.py               # Input and configuration validation
│   └── workflow_constants.py       # Shared workflow constants
│
├── gui/                            # User interface components
│   ├── __init__.py
│   ├── app_window.py               # Main application window
│   ├── ui_styles.py                # Global styling and themes
│   │
│   ├── sections/                   # Major GUI sections
│   │   ├── action_section.py       # Run / Cancel controls
│   │   ├── advanced_section.py     # Advanced workflow options
│   │   ├── config_section.py       # Organism and configuration settings
│   │   ├── input_section.py        # Input data selection
│   │   ├── output_section.py       # Output path configuration
│   │   ├── sidebar_section.py      # Navigation sidebar
│   │   └── workflow_section.py     # Workflow step selection
│   │
│   └── widgets/                    # Reusable GUI widgets
│       ├── __init__.py
│       └── selection_widgets.py
│
├── services/                       # Backend service layer
│   ├── __init__.py
│   └── pipeline_runner.py          # Executes Dorado Automation workflows
│
├── workers/                        # Background execution threads
│   ├── __init__.py
│   └── worker_thread.py            # Prevents GUI blocking during analysis
│
└── icons/                          # Application icons and graphical assets
```

### Architecture Overview

The GUI follows a modular architecture that separates the user interface from workflow execution logic.

* **GUI Layer (`gui/`)** – Responsible for user interaction, workflow configuration, and visual presentation.
* **Core Layer (`core/`)** – Provides validation, constants, and utility functions shared across the application.
* **Service Layer (`services/`)** – Acts as the bridge between the graphical interface and the Dorado Automation API backend.
* **Worker Layer (`workers/`)** – Runs long analyses in background threads, keeping the interface responsive.
* **Assets (`icons/`)** – Stores application icons and visual resources.

This structure makes the application easier to maintain, extend, and test while keeping workflow execution logic independent from the graphical interface.


---

## Supported commands

### Show version

```bash
python main.py --version
```

### Run complete POD5 workflow

```bash
python main.py pod5 <Trial_Name> /path/to/pod5 --organism mouse
```

### Run FASTQ workflow

```bash
python main.py fastq <Trial_Name> /path/to/fastq --organism human
```

### Run NanoTel only

```bash
python main.py nanotel <Trial_Name> /path/to/fastq
```

### Run alignment only

```bash
python main.py align <Trial_Name> /path/to/fastq --organism mouse
```

### Run R analysis only

Run all enabled R analyses:

```bash
python main.py r-analysis <Trial_Name>
```

Run only NanoTel filtration:

```bash
python main.py r-analysis <Trial_Name> --no-mapping --no-methylation
```

Run mapping and methylation only:

```bash
python main.py r-analysis <Trial_Name> --no-filtration
```

---

## Output structure

For each trial, the pipeline creates a dedicated directory tree.

Example:

```text
<output_base>/<Trial_Name>/
├── rebasecalled/
├── demuxed/
├── fastqs/
├── nanotel_output/
├── aligned/
├── r_analysis/
│   ├── mapping_output/
│   └── methylation_output/
└── logs/
```

This structure keeps all outputs grouped by sequencing trial and allows individual stages to be rerun without repeating the full pipeline.

---

## Configuration

The workflow is driven by **`default_config.json`**.

This configuration file defines paths and parameters used by the pipeline, including:

* reference genome locations
* Dorado model path
* NanoTel script path
* output directory base path
* demultiplexing settings
* telomere detection parameters
* alignment parameters
* logging settings

Before running the pipeline in a new environment, update the relevant paths in the configuration file so they match the local system.

---

## External dependencies

This project relies on several external tools that must be installed separately.

### Required command-line tools

* **Dorado**
* **R / Rscript**
* **samtools**

### Required external resources

* Dorado model files
* reference genome FASTA files
* NanoTel R script
* downstream R analysis scripts

### Python

The Python side of the pipeline primarily uses the standard library, keeping the environment lightweight.

---

## Quick start

1. Clone the repository
2. Update paths inside `default_config.json`
3. Ensure Dorado, R, and samtools are installed and available in `PATH`
4. Run the pipeline

Example:

```bash
python main.py pod5 <Trial_Name> /path/to/pod5 --organism mouse
```

or

```bash
python main.py fastq <Trial_Name> /path/to/fastq --organism human
```

---

## License

Add the appropriate license for this repository.

If the code is intended for internal laboratory use only, replace this section with the appropriate usage note.
