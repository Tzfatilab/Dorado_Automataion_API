# Non-Python Resource Inventory

This document records whether each non-Python resource is installed with the package, supplied by
Conda, kept external, excluded, or awaiting a decision. Update the provenance and checksum whenever
a resource is replaced or regenerated.

Status values:

- `SHIP`: install the resource with this package.
- `CONDA DEPENDENCY`: install it from an existing Conda package.
- `EXTERNAL`: the user obtains it separately and configures or detects its path.
- `EXCLUDE`: do not put it in release archives or installed packages.
- `AWAITING DECISION`: do not package it until the stated question is resolved.

## Current Decisions

| Resource | Status | Reason and remaining work |
| --- | --- | --- |
| Python workflow and GUI source | `SHIP` | The installed `telomere-analyzer` command launches the GUI; backend-only workflow subcommands are not exposed as the public entry point. |
| `dorado_workflow/data/NanoTel.R` | `SHIP` | Created and owned by the lab; included as package data and passed the approved real-data regression baseline in an isolated Linux environment. |
| Core scripts under `dorado_workflow/r_analysis/` | `SHIP` | Lab-owned integral analysis code; the eight runtime scripts are included and their installed paths are tested. |
| `dorado_workflow/configs/default_config.json` | `SHIP` | Included as read-only defaults. The GUI supplies input, output, organism, and run settings at runtime; external reference/model overrides still need a supported mechanism. |
| GUI icons | `SHIP` | All nine PNG assets are included; installed discovery and offscreen startup of the real Conda-installed GUI passed. |
| Human chromosome-end FASTA | `SHIP` after completing provenance | Upstream T2T data is CC0; record the exact source file and transformation procedure. |
| Mouse chromosome-end FASTA and index | `AWAITING DECISION` | Exact upstream assembly, URL, terms, and transformation procedure are unknown. |
| Zebrafish GRCz12tu reference FASTA | `AWAITING DECISION` | Preferred outcome is to ship it like the human and mouse references. It is temporarily excluded because the local file is absent and its exact source/redistribution record still needs confirmation. External download is a fallback only. |
| Dorado executable | `EXTERNAL` | Users install the lab-tested Dorado version separately; its exact executable version still needs to be recorded in `DORADO_COMPATIBILITY.md`. |
| Dorado neural-network model | `EXTERNAL` | The initial package is pinned to `dna_r10.4.1_e8.2_400bps_sup@v5.2.0`; approximately 315 MB and subject to ONT redistribution terms. |
| minimap2, samtools, Modkit, Python, R, and language libraries | `CONDA DEPENDENCY` | Declare these in the Bioconda recipe rather than copying their files into this repository. Modkit is supplied by the approved `ont-modkit` dependency while public methylation modes await a decision. |
| User POD5, BAM, FASTQ, and result files | `EXCLUDE` | User data and generated output are never distribution resources. |
| Sanitized integration FASTQ/BAM fixtures | `CONDA TEST METADATA` | Sample/run identifiers use anonymous test labels; lab authorization for public redistribution was recorded on 2026-08-05. Excluded from wheel, sdist, and the installed runtime, but conda-build stores `test.source_files` under the downloadable artifact's `info/test` metadata. |
| Windows executable and installer artifacts | `EXCLUDE` | Native Windows distribution is deferred to a separately built and validated executable; it is not part of the Bioconda recipe or Python package archives. |

## How Installed Paths Work

Package resources do not need a fixed path chosen by the team. Conda installs them beneath its
environment prefix, for example under `site-packages/dorado_workflow/`, and the application locates
them relative to the installed Python modules.

- `RAnalyzer` already locates `r_analysis/main_analysis_pipeline.R` relative to its own installed
  Python file.
- The R entry scripts determine their own directory and source the sibling files under
  `r_analysis/functions/` relative to that directory.
- `ConfigManager` resolves relative resource paths against the installed `dorado_workflow` package
  directory rather than the user's current working directory.
- The GUI supplies the selected input/output locations and analysis overrides in memory. It does not
  edit the installed default configuration.

The R runtime files to include are:

- `r_analysis/main_analysis_pipeline.R`
- `r_analysis/batch_mapping_analysis.R`
- `r_analysis/batch_methylation_prep.R`
- `r_analysis/batch_nanotel_analysis.R`
- all four `.R` files under `r_analysis/functions/`

Do not include `.RData`, `.Rhistory`, `r_analysis.Rproj`, the `47911FD4/` RStudio session directory,
debug scripts, or notebook/session artifacts. They are development state rather than runtime code.

The remaining user-path issue is narrower: the GUI currently creates `ConfigManager` with
`config_path=None` and has no selectors for overriding external reference FASTAs or a Dorado model.
Packaged resources such as NanoTel need no user path. External resources need either GUI selectors or
a per-user configuration file; users must never be instructed to edit files inside `site-packages`.

## External Resource Configuration TODO

Recommended approach: keep installed defaults read-only, store external-resource choices in a
per-user configuration file, and expose those choices through a small GUI settings area. The CLI and
GUI should use the same configuration loader and precedence rules.

- [ ] Define the external-resource settings schema. Initial fields should cover the Dorado
  executable, Dorado model directory, optional custom reference overrides by organism, and a
  zebrafish-reference fallback only if redistribution cannot be approved.
- [ ] Decide the cross-platform user configuration location. Recommended: use the `platformdirs`
  package so Windows, Linux, and macOS follow their normal application-data conventions; add it to
  `pyproject.toml` and the Bioconda recipe if selected.
- [ ] Implement one loader that merges read-only package defaults with the per-user configuration.
- [ ] Use this precedence order: explicit run/CLI value, saved user setting, packaged default, then
  automatic executable discovery through `PATH` where applicable.
- [ ] Add a GUI "External resources" settings area with file/directory selectors, current-value
  display, validation, save, and reset-to-default actions.
- [ ] Preserve CLI `--config` support and document whether an explicitly supplied file replaces or
  overrides the saved user configuration.
- [ ] Auto-detect the Dorado executable through `PATH`; require a user-selected path only when
  detection fails or a specific executable must be used.
- [ ] Validate selected resources before starting a workflow: existence, readability, expected file
  type, supported organism, and compatible Dorado/model combination where this can be determined.
- [ ] Show actionable missing-resource messages that identify the setting to fix without exposing
  internal `site-packages` paths as something users should edit.
- [ ] Ensure workflows that do not require Dorado, its model, or an external reference remain usable
  when those resources are not configured.
- [ ] Add tests for package-default resolution, per-user overrides, explicit `--config` overrides,
  `PATH` detection, missing files, invalid files, and paths containing spaces.
- [ ] Test the settings location and GUI behavior on Linux and Windows; add macOS coverage if macOS
  becomes an officially supported platform.
- [ ] Document backup/reset behavior and include the resolved non-sensitive resource paths in run
  logs for reproducibility.

## Where Shipping Is Declared

This inventory records the decision and provenance, but it does not install files by itself.

- `pyproject.toml` controls which non-Python files enter the Python wheel through
  `[tool.setuptools.package-data]`. Because the resources live under `dorado_workflow/`, this is the
  main file-level inclusion point.
- The source archive must also be inspected to ensure approved resources are present and excluded
  resources are absent. Add a manifest rule only if the standard build does not match the inventory.
- `packaging/bioconda/meta.yaml` declares runtime dependencies and tests. It normally does not list
  each R script, icon, or configuration file because `build.sh` installs the already-defined Python
  package contents.
- Bioconda tests must verify that installed resources can be found and that excluded resources were
  not bundled accidentally.

## Lab-Owned NanoTel Script

- Local path: `dorado_workflow/data/NanoTel.R`
- Ownership: created by the lab
- Distribution decision: ship with the package
- Size: 111,618 bytes
- SHA256: `4EAA18CB4F5B3BD84E0166D8E0BA75E11A47BE2F6E7E2186DFD3317F603D1027`
- Packaged path: resolved through `ConfigManager.get_nanotel_script_path()`
- Verification: the sanitized FASTQ smoke test passed against the accepted CRAN/Bioconductor
  dependency set in an isolated Linux Micromamba environment on 2026-08-05 and against the built
  Conda package on 2026-08-06.
- Remaining work: add the optional scenarios listed in `R_DEPENDENCIES.md` when approved fixtures
  become available.

## Human T2T Chromosome-End Reference

- Local path: `dorado_workflow/data/references/Human/T2T-CHM13-150KchrHeadTail-Yincluded-telo-trimmed.fasta`
- Size: 7,234,382 bytes
- Records: 48 chromosome head/tail sequences
- SHA256: `2756FBA0833F69256F38EDAA992ED99BC8C8E0A6306C05E2DF095AEA0CCF56FD`
- Probable upstream assembly: T2T-CHM13v2.0 (T2T-CHM13 plus chromosome Y)
- Upstream project: https://github.com/marbl/CHM13
- Upstream data terms: CC0/public domain; acknowledge the Telomere-to-Telomere Consortium
- Distribution decision: ship after the two release blockers below are completed

Release blockers:

- `PACKAGING TODO [HUMAN-REFERENCE-SOURCE]`: record the exact downloaded filename, version, URL,
  accession, and download date. Do not rely only on the derived local filename.
- `PACKAGING TODO [HUMAN-REFERENCE-DERIVATION]`: record or add the reproducible commands/script that
  extracted 150 kb chromosome ends, included Y, and trimmed telomeric sequence.

## Mouse Chromosome-End Reference

- Local path: `dorado_workflow/data/references/Mouse/mouse.241018.v1.1.0.-40k_edges-telo-trimmed-Y-included.fasta`
- Index path: the same filename with `.fai` appended
- FASTA size: 1,435,475 bytes
- Records: 35 chromosome head/tail sequences, including combined head references
- FASTA SHA256: `81E502256D568F250117DBB07B2D8374D642738E6F80AF68A4743D69E769452D`
- Index SHA256: `026C5EFE6DCBE57BE1C54A8DD551E5D0B2623AD0C9F913D22ABD15EBE60E0ADB`
- Distribution decision: await provenance; the local name and headers do not identify the assembly

Release blockers:

- `PACKAGING TODO [MOUSE-REFERENCE-SOURCE]`: obtain the exact database, assembly accession/version,
  download URL, download date, and source terms from the team member who created the derivative.
- `PACKAGING TODO [MOUSE-REFERENCE-DERIVATION]`: document how the 40 kb edges, telomere trimming,
  chromosome Y, and combined head records were produced.
- Regenerate the `.fai` from the final packaged FASTA and verify both checksums.

If the original assembly came from NCBI molecular databases, NCBI itself places no restrictions on
data use or distribution, but it does not transfer or guarantee rights claimed by submitters. Record
the exact assembly before relying on that policy: https://www.ncbi.nlm.nih.gov/home/about/policies/

## Zebrafish GRCz12tu Reference

- Configured path: `dorado_workflow/data/references/ZebraFish/GCF_049306965.1_GRCz12tu_genomic.fasta`
- Assembly: NCBI RefSeq `GCF_049306965.1`, GRCz12tu
- Source record: https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_049306965.1/
- Local state: missing from this checkout and ignored by the current Git configuration
- Preferred distribution decision: ship the reference with the package, consistent with the human
  and mouse workflow experience
- Temporary status: excluded while the exact download, redistribution terms, file size, and checksum
  are confirmed; this exclusion is not a preference for an external-reference workflow
- Fallback only: if redistribution cannot be approved or package-size limits make bundling impossible,
  document a reproducible NCBI download command and support a per-user external path
- Remaining work: recover the exact local FASTA, confirm its source and terms, record its checksum,
  assess the resulting package size, and determine whether the full assembly or a reproducible
  chromosome-end derivative is the correct runtime resource

When redistributing NCBI-derived molecular data, acknowledge NLM/NCBI, do not imply endorsement, and
state when a bundled snapshot may not be current: https://www.nlm.nih.gov/databases/download.html
