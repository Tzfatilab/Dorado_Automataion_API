"""
R Analyzer Processor Module
===========================

Handles the R analysis pipeline execution for NanoTel filtration, mapping, and methylation analysis.
Coordinates with R scripts to process aligned BAM files and NanoTel outputs.
"""

from pathlib import Path
from typing import Dict, Optional
import subprocess
import json
from ..reports.nanotel_workbook import NanoTelWorkbookWriter, barcode_from_summary_filename
from .base import ProcessorBase, ProcessorResult, WorkflowContext
from ..utils.cancellation import WorkflowCancelled
from ..utils.shell_commands import format_command

class RAnalyzer(ProcessorBase):
    """
    Processor for running R analysis pipeline.

    Responsibilities:
    - Validate prerequisites based on analysis type
    - Execute R analysis scripts (NanoTel filtration, mapping, methylation)
    - Track analysis outputs
    - Collect statistics

    The R analysis consists of three main components:
    1. NanoTel filtration - Filters telomere reads (requires FASTQ ג†’ nanotel_output)
    2. Mapping analysis - Alignment and genomic position analysis (requires BAMs)
    3. Methylation analysis - CpG methylation patterns (requires BAMs)

    Workflow logic:
    - FASTQ files ג†’ Can run NanoTel filtration only
    - BAM files ג†’ Can run mapping and methylation only
    - Both FASTQ+BAM ג†’ Can run complete R analysis

    Configuration used:
    - Uses existing config from ConfigManager (no separate JSON file)
    - run_nanotel_filtration: Enable/disable NanoTel filtration
    - run_mapping_analysis: Enable/disable mapping analysis
    - run_methylation_analysis: Enable/disable methylation analysis
    """

    def __init__(self, context: WorkflowContext):
        """
        Initialize R analyzer processor.

        Args:
            context: WorkflowContext with all shared resources
        """
        super().__init__(context)

        # Use PathManager's directory structure
        # NanoTel raw output and filtered summaries go to results/nanotel/.
        self.nanotel_output_dir = self.context.path_manager.get_nanotel_output_dir_path()

        # R analysis outputs share the results/ folder with NanoTel.
        self.r_analysis_dir = self.context.path_manager.get_r_analysis_dir_path()
        self.reports_dir = self.context.path_manager.get_reports_dir_path()
        self.mapping_output_dir = self.context.path_manager.get_r_mapping_output_dir_path()
        self.methylation_output_dir = self.context.path_manager.get_r_methylation_output_dir_path()

    def validate_inputs(self, run_filtration: bool = True,
                       run_mapping: bool = True,
                       run_methylation: bool = True) -> bool:
        """
        Validate that prerequisites for R analysis are met based on which analyses to run.

        Args:
            run_filtration: If True, validate NanoTel filtration prerequisites
            run_mapping: If True, validate mapping analysis prerequisites
            run_methylation: If True, validate methylation analysis prerequisites

        Returns:
            True if validation passes, False otherwise
        """
        self.context.logger.info("Validating post-analysis prerequisites...")

        # Check if Rscript is available
        if not self.context.validate_tools(['Rscript']):
            self.context.logger.error("Rscript not found. R must be installed.")
            return False

        # Validate NanoTel filtration prerequisites (needs summary.csv files)
        if run_filtration:
            if not self._validate_nanotel_summaries():
                return False

        # Validate mapping/methylation prerequisites.
        if run_mapping or run_methylation:
            if not self._validate_aligned_bams():
                return False
        if run_methylation:
            if not self._check_bam_methylation():
                return False

        # Ensure only the output directories needed for this run exist.
        self.r_analysis_dir.mkdir(parents=True, exist_ok=True)
        if run_mapping:
            self.mapping_output_dir.mkdir(parents=True, exist_ok=True)

        self.context.logger.info("OK All post-analysis prerequisites validated")
        return True

    def execute(self, run_filtration: bool = True,
                run_mapping: bool = True,
                run_methylation: bool = True) -> ProcessorResult:
        """
        Execute the R analysis pipeline.

        Args:
            run_filtration: If True, run NanoTel filtration (needs summary.csv files)
            run_mapping: If True, run mapping analysis (needs BAMs)
            run_methylation: If True, run methylation analysis (needs BAMs with methylation)

        Returns:
            ProcessorResult with success status, output directories, and statistics
        """
        self.log_start()
        # Load this before validation: mapping checks can fail after NanoTel has
        # already produced CSVs that still need to be preserved in the workbook.
        nanotel_params = self.context.config_manager.get_nanotel_params()
        pipeline_config = {}

        # Validate inputs first
        if not self.validate_inputs(run_filtration, run_mapping, run_methylation):
            if run_filtration and bool(nanotel_params.get("summary_only", False)):
                if run_mapping or run_methylation:
                    # Mapping prerequisites do not affect NanoTel filtration.
                    # Finish that step alone so the workbook has real statistics.
                    filtration_result = self.execute(
                        run_filtration=True,
                        run_mapping=False,
                        run_methylation=False,
                    )
                    if filtration_result.success:
                        self.context.logger.info(
                            "NanoTel Excel summary saved despite mapping "
                            f"validation failure: "
                            f"{filtration_result.get_output('nanotel_summary_workbook')}"
                        )
                else:
                    # Filtration itself could not start; keep raw files for
                    # diagnosis and never label unknown counts as zero.
                    recovery_workbook = self._try_create_summary_workbook_after_failure()
                    if recovery_workbook is not None:
                        self.context.logger.info(
                            "NanoTel Excel summary saved despite post-analysis "
                            f"validation failure: {recovery_workbook}"
                        )
            result = ProcessorResult(
                success=False,
                error="Post-analysis prerequisite validation failed"
            )
            self.log_complete(result)
            return result

        try:
            # Build R pipeline configuration JSON for this trial
            config_mgr = self.context.config_manager
            path_mgr = self.context.path_manager

            # 1. Base path structure for the R pipeline (per-trial)
            pipeline_config = path_mgr.generate_r_pipeline_config()

            # 2. Add NanoTel parameters (density thresholds etc.)
            nanotel_params = config_mgr.get_nanotel_params()
            pipeline_config["nanotel_analysis"].update(nanotel_params)

            # 3. Add mapping / methylation parameters and run flags
            r_analysis_params = config_mgr.get_r_analysis_params()
            mapping_params = config_mgr.get_r_mapping_params()
            methylation_params = config_mgr.get_r_methylation_params()

            # Top-level run flags: combine config defaults with runtime flags
            pipeline_config["run_nanotel_analysis"] = (
                    r_analysis_params.get("run_nanotel_analysis", True) and run_filtration
            )
            pipeline_config["run_mapping_analysis"] = (
                    r_analysis_params.get("run_mapping_analysis", True) and run_mapping
            )
            pipeline_config["run_methylation_analysis"] = (
                    r_analysis_params.get("run_methylation_analysis", True) and run_methylation
            )
            pipeline_config["stop_on_error"] = r_analysis_params.get("stop_on_error", True)

            # Merge mapping / methylation thresholds into their respective sections
            pipeline_config["mapping_analysis"].update(mapping_params)
            pipeline_config["methylation_analysis"].update(methylation_params)

            # 4. Write JSON config into the trial's reports directory
            config_path = self.reports_dir / "r_pipeline_config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)

            with config_path.open("w") as f:
                json.dump(pipeline_config, f, indent=2)

            # 5. Build and run R command: pass config file AND trial name
            enabled_steps = []
            if pipeline_config["run_nanotel_analysis"]:
                enabled_steps.append("filtering")
            if pipeline_config["run_mapping_analysis"]:
                enabled_steps.append("mapping")
            if pipeline_config["run_methylation_analysis"]:
                enabled_steps.append("methylation")
            self.context.logger.info(
                f"Post-analysis steps: {', '.join(enabled_steps) or 'none'}"
            )
            self.context.logger.info("Running post-analysis pipeline")
            r_script_path = Path(__file__).parent.parent / "r_analysis" / "main_analysis_pipeline.R"

            if not r_script_path.exists():
                raise FileNotFoundError(f"R script not found at: {r_script_path}")

            # Working directory for R so that utils.R, batch_* scripts are found
            r_analysis_dir = r_script_path.parent
            trial_name = path_mgr.trial_name

            command = format_command([
                "Rscript",
                str(r_script_path),
                str(config_path),
                str(trial_name),
            ])

            self.context.logger.info(f"Command: {command}", gui_visible=False)
            self.context.command_executor.execute(command, cwd=r_analysis_dir)

            # Capture counts before Summary mode removes its CSV intermediates.
            stats = self._collect_statistics()
            workbook_path = None
            if (
                pipeline_config["run_nanotel_analysis"]
                and bool(nanotel_params.get("summary_only", False))
            ):
                workbook_path = self._create_nanotel_summary_workbook(
                    cleanup_sources=True
                )
                self.context.logger.info(
                    f"NanoTel Excel summary saved to: {workbook_path}"
                )

            # Create successful result
            result = ProcessorResult(
                success=True,
                output_paths={
                    'r_analysis_dir': self.r_analysis_dir,
                    'reports_dir': self.reports_dir,
                    'nanotel_filtered': workbook_path or self.nanotel_output_dir,
                    'mapping_output': self.mapping_output_dir,
                    'methylation_output': self.methylation_output_dir,
                    'nanotel_summary_workbook': (
                        workbook_path
                    ),
                },
                statistics=stats
            )

            self.log_complete(result)
            return result

        except WorkflowCancelled:
            raise
        except Exception as e:
            if bool(nanotel_params.get("summary_only", False)):
                recovery_workbook = self._try_create_summary_workbook_after_failure()
                if recovery_workbook is not None:
                    self.context.logger.info(
                        f"NanoTel Excel summary saved before the later failure: "
                        f"{recovery_workbook}"
                    )
            error_msg = f"Post-analysis failed: {str(e)}"
            self.context.logger.error(error_msg)
            result = ProcessorResult(
                success=False,
                error=error_msg
            )
            self.log_complete(result)
            return result


    def _create_nanotel_summary_workbook(self, cleanup_sources: bool = True) -> Path:
        """Save the report atomically, then optionally remove temporary CSVs.

        Returns the workbook path. Recovery after a failed analysis keeps the
        source CSVs by passing ``cleanup_sources=False``.
        """
        writer = NanoTelWorkbookWriter(
            self.nanotel_output_dir,
            self.r_analysis_dir,
            self.context.config_manager.get_nanotel_params().get(
                "short_telomere_threshold_bp", 2000
            ),
        )
        workbook_path = writer.write()
        if cleanup_sources:
            self._cleanup_summary_workspace()
        return workbook_path

    def _try_create_summary_workbook_after_failure(self) -> Optional[Path]:
        """Preserve completed NanoTel results when a later analysis step fails."""
        # Without this file, filtering may have failed. Do not turn unknown
        # results into a workbook that claims every barcode has zero reads.
        if not (self.nanotel_output_dir / "nanotel_summary_statistics.csv").exists():
            return None
        try:
            return self._create_nanotel_summary_workbook(cleanup_sources=False)
        except (OSError, ValueError):
            return None


    def _cleanup_summary_workspace(self) -> None:
        """Remove the temporary NanoTel tree after its workbook is safely saved."""
        results_dir = self.context.path_manager.get_results_dir_path().resolve(strict=False)
        source_dir = self.nanotel_output_dir.resolve(strict=False)
        if source_dir == results_dir or results_dir not in source_dir.parents:
            raise ValueError(f"Refusing to remove unexpected NanoTel path: {source_dir}")
        removed = self.context.path_manager.remove_generated_path(source_dir)
        if not removed:
            remaining = sorted(path.name for path in source_dir.iterdir())
            self.context.logger.warning(
                "Excel was saved, but the temporary NanoTel folder could not "
                f"be fully removed. Remaining items: {', '.join(remaining)}"
            )


    def _validate_nanotel_summaries(self) -> bool:
        """
        Validate that NanoTel summary.csv files exist (for filtration).

        Returns:
            True if valid, False otherwise
        """
        nanotel_dir = self.nanotel_output_dir

        if not nanotel_dir.exists():
            self.context.logger.error(
                f"NanoTel output directory not found: {nanotel_dir}\n"
                "Run NanoTel analysis first to generate summary files."
            )
            return False

        # Full runs store summaries inside barcode directories; Summary runs
        # store the same barcode-named files directly in the NanoTel directory.
        summary_files = [
            path
            for path in nanotel_dir.rglob("*_summary.csv")
            if path.is_file()
            and not path.name.lower().startswith("filtered_")
            and "statistics" not in path.name.lower()
        ]
        found_barcodes = {
            barcode
            for path in summary_files
            if (barcode := barcode_from_summary_filename(path.name)) is not None
        }

        if not found_barcodes:
            self.context.logger.error(
                f"No barcode NanoTel summary CSV files found in {nanotel_dir}"
            )
            return False

        self.context.logger.info(
            f"Found NanoTel summaries for {len(found_barcodes)} barcodes"
        )
        return True


    def _validate_aligned_bams(self) -> bool:
        """
        Validate that aligned directory has BAM files (for mapping/methylation).

        Returns:
            True if valid, False otherwise
        """
        aligned_dir = self.context.path_manager.get_aligned_dir_path()

        if not aligned_dir.exists():
            self.context.logger.error(
                f"Aligned directory not found: {aligned_dir}\n"
                "Run alignment first to generate BAM files."
            )
            return False

        # Find BAM files
        bam_files = list(aligned_dir.rglob("*.bam"))
        if not bam_files:
            self.context.logger.error(
                f"No BAM files found in {aligned_dir}\n"
                "Ensure alignment completed successfully."
            )
            return False

        self.context.logger.info(f"Found {len(bam_files)} BAM files for mapping/methylation analysis")
        return True

    def _check_bam_methylation(self, read_limit: int = 1000) -> bool:
        """
        Check if BAM files contain methylation data.

        Returns:
            True if methylation data found, False otherwise
        """
        aligned_dir = self.context.path_manager.get_aligned_dir_path()
        bam_files = list(aligned_dir.rglob("*.bam"))

        if not bam_files:
            return False

        # Check first few BAM files for methylation tags
        check_count = min(3, len(bam_files))
        has_methylation = False

        for bam in bam_files[:check_count]:
            try:
                count = self._count_methylation_tags(bam, limit=read_limit)

                if count > 0:
                    has_methylation = True
                    break

            except WorkflowCancelled:
                raise
            except Exception as e:
                self.context.logger.warning(f"Could not check methylation in {bam}: {e}")
                continue

        if not has_methylation:
            self.context.logger.warning(
                f"No methylation data found in the first {read_limit} reads of sampled BAM files.\n"
                "BAMs must be basecalled with --modified-bases flag.\n"
                "Methylation analysis may fail or produce empty results."
            )
            # Return True anyway - let R analysis handle this
            return True

        self.context.logger.info("OK Methylation data detected in BAM files")
        return True

    def _count_methylation_tags(self, bam: Path, limit: int = 100) -> int:
        """Count reads with modified-base tags using samtools."""
        command = ["samtools", "view", str(bam)]
        process = self.context.command_executor.popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        count = 0
        checked = 0
        try:
            for line in process.stdout or []:
                checked += 1
                if "\tMM:Z:" in line or "\tMm:Z:" in line or "\tML:B:" in line:
                    count += 1
                if checked >= limit:
                    break
        finally:
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()
            process.terminate()
            process.wait(timeout=5)

        self.context.command_executor.check_cancelled()
        return count

    def _collect_statistics(self) -> Dict:
        """
        Collect statistics about the R analysis outputs.

        Returns:
            Dictionary of statistics
        """
        stats = {}

        # Count filtered summaries in nanotel_output
        if self.nanotel_output_dir.exists():
            filtered_files = list(self.nanotel_output_dir.rglob("*filtered*.csv"))
            stats['nanotel_filtered_files'] = len(filtered_files)

        # Count output files in r_analysis subdirectories
        if self.mapping_output_dir.exists():
            mapping_files = list(self.mapping_output_dir.rglob("*.*"))
            stats['mapping_output_files'] = len(mapping_files)

        if self.methylation_output_dir.exists():
            methylation_files = list(self.methylation_output_dir.rglob("*.*"))
            stats['methylation_output_files'] = len(methylation_files)

        return stats

    def get_output_paths(self) -> Dict[str, Path]:
        """
        Get the expected output paths for this processor.

        Returns:
            Dictionary with output directory paths
        """
        return {
            'r_analysis_dir': self.r_analysis_dir,
            'reports_dir': self.reports_dir,
            'nanotel_filtered': self.nanotel_output_dir,  # Filtered summaries here
            'mapping_output': self.mapping_output_dir,
            'methylation_output': self.methylation_output_dir
        }
