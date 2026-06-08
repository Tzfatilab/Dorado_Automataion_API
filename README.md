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

## GUI integration

In addition to the command-line interface provided in this repository, the pipeline can also be executed through the **`dorado_api` GUI application** used in the lab.

The GUI acts as a front-end that calls the same workflow logic implemented here. This allows users who are less comfortable with command-line tools to run the full sequencing pipeline through a graphical interface while still relying on the same backend processing code.

In other words:

* **This repository** provides the processing engine.
* **`dorado_api`** provides the graphical interface that interacts with it.

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
