# Local Bioconda Build Rehearsal

This file records local build evidence for the draft recipe. It is not a substitute for Bioconda's
official CI or maintainer review.

## Successful Run

- Date: 2026-08-06
- Source commit: `47b68d3`
- Platform: WSL2, Linux x86_64
- Build tooling: Micromamba 2.8.1 and conda-build 26.7.0
- Temporary package identity: `package-name-pending` version `0.0.0`, build `py_0`
- Channels: `conda-forge` and `bioconda`, with default channels disabled

The tracked recipe was copied to an ignored rehearsal directory and given a temporary local source
URL and checksum. No release metadata was filled in and nothing was uploaded.

## Resolved Environment

The clean install resolved and executed with:

- Python 3.14.6
- PySide6 6.11.1
- R 4.5.3
- minimap2 2.31
- samtools/htslib 1.24
- ont-modkit 0.6.4
- The declared CRAN and Bioconductor dependencies

The complete clean environment occupied approximately 2.7 GB. The test phase reached approximately
4.8 GB of memory while NanoTel used its R workers.

## Tests Passed

- Package build through `build.sh`.
- Installation into conda-build's isolated test environment.
- `telomere-analyzer --help` and `--version`.
- Installed configuration, NanoTel script, R scripts, functions, and GUI icon discovery.
- Required R/CRAN/Bioconductor namespace loading.
- All three sanitized real-data integration tests.
- A second installation from the local Conda channel into an independent clean environment.
- Offscreen construction and clean shutdown of the real installed Qt `AppWindow`.
- Independent rerun of all three real-data tests from a directory containing no source packages.
- minimap2, samtools, Modkit, and R command discovery in the clean environment.

## Package Inspection

- Corrected Conda artifact size: approximately 24 MB.
- Application runtime payload: 59 files under the installed `dorado_workflow` and `dorado_gui`
  packages.
- Runtime payload contained no FASTQ, BAM, BAI, FASTA, RDS, ZIP, executable, or test fixture files.
- References, Dorado, and the Dorado model were absent as intended.
- The sanitized BAM/BAI/FASTQ fixtures are stored inside the Conda artifact under `info/test` because
  conda-build preserves `test.source_files`. They are not installed into `site-packages`, but they do
  contribute approximately 18.7 MB to the downloadable Conda artifact.

The fixture behavior above is standard conda-build test metadata behavior. If the team later decides
that genomic fixtures must not travel inside the final `.conda` artifact, the recipe test strategy
must change; the current behavior is authorized and technically functional.

## Remaining Validation

- Repeat official Bioconda CI after final name, version, license, source URL/checksum, URLs, and
  maintainers are supplied.
- Resolve the existing Dorado, reference-provenance, methylation, and other explicitly deferred
  decisions.
- Add an approved tagged-BAM methylation fixture when available.
- Repeat the NanoTel `--analysis` assertions added on 2026-08-09 against the next built package. The
  extended real-data suite passed in a fresh Linux dependency environment, but was added after this
  recorded package build.
- Review the non-fatal conda-build metadata warning about parsed output blocks during official recipe
  linting; the single-output package built and tested correctly in this rehearsal.
