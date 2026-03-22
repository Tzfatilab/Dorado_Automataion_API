"""
R Analyzer Processor Module
===========================

Handles the R analysis pipeline execution for NanoTel filtration, mapping, and methylation analysis.
Coordinates with R scripts to process aligned BAM files and NanoTel outputs.
"""

from pathlib import Path
from typing import Dict, Optional, List
import subprocess
import json
from .base import ProcessorBase, ProcessorResult, WorkflowContext


class RAnalyzer(ProcessorBase):
    """
    Processor for running R analysis pipeline.

    Responsibilities:
    - Validate prerequisites based on analysis type
    - Execute R analysis scripts (NanoTel filtration, mapping, methylation)
    - Track analysis outputs
    - Collect statistics

    The R analysis consists of three main components:
    1. NanoTel filtration - Filters telomere reads (requires FASTQ → nanotel_output)
    2. Mapping analysis - Alignment and genomic position analysis (requires BAMs)
    3. Methylation analysis - CpG methylation patterns (requires BAMs)

    Workflow logic:
    - FASTQ files → Can run NanoTel filtration only
    - BAM files → Can run mapping and methylation only
    - Both FASTQ+BAM → Can run complete R analysis

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
        # NanoTel raw output and filtered summaries go to nanotel_output/
        self.nanotel_output_dir = self.context.path_manager.get_nanotel_output_dir()

        # R analysis outputs go to r_analysis/ subdirectories
        self.r_analysis_dir = self.context.path_manager.get_r_analysis_dir()
        self.mapping_output_dir = self.context.path_manager.get_r_mapping_output_dir()
        self.methylation_output_dir = self.context.path_manager.get_r_methylation_output_dir()

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
        self.context.logger.info("Validating R analysis prerequisites...")

        # Check if Rscript is available
        if not self.context.validate_tools(['Rscript']):
            self.context.logger.error("Rscript not found. R must be installed.")
            return False

        # Validate NanoTel filtration prerequisites (needs summary.csv files)
        if run_filtration:
            if not self._validate_nanotel_summaries():
                return False

        # Validate mapping/methylation prerequisites (need BAMs with methylation)
        if run_mapping or run_methylation:
            if not self._validate_aligned_bams():
                return False
            if not self._check_bam_methylation():
                return False

        # Ensure output directories exist
        self.r_analysis_dir.mkdir(parents=True, exist_ok=True)
        self.mapping_output_dir.mkdir(parents=True, exist_ok=True)
        self.methylation_output_dir.mkdir(parents=True, exist_ok=True)

        self.context.logger.info("✓ All R analysis prerequisites validated")
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

        # Validate inputs first
        if not self.validate_inputs(run_filtration, run_mapping, run_methylation):
            result = ProcessorResult(
                success=False,
                error="R analysis prerequisite validation failed"
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

            # 4. Write JSON config into the trial's r_analysis directory
            config_path = self.r_analysis_dir / "r_pipeline_config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)

            with config_path.open("w") as f:
                json.dump(pipeline_config, f, indent=2)

            # 5. Build and run R command: pass config file AND trial name
            self.context.logger.info("Starting R analysis pipeline...")
            r_script_path = Path(__file__).parent.parent / "r_analysis" / "main_analysis_pipeline.R"

            if not r_script_path.exists():
                raise FileNotFoundError(f"R script not found at: {r_script_path}")

            # Working directory for R so that utils.R, batch_* scripts are found
            r_analysis_dir = r_script_path.parent
            trial_name = path_mgr.trial_name

            command = f"Rscript {r_script_path} {config_path} {trial_name}"

            self.context.command_executor.execute(command, cwd=r_analysis_dir)

            # Collect statistics
            stats = self._collect_statistics()

            # Create successful result
            result = ProcessorResult(
                success=True,
                output_paths={
                    'r_analysis_dir': self.r_analysis_dir,
                    'nanotel_filtered': self.nanotel_output_dir,  # Filtered summaries go here
                    'mapping_output': self.mapping_output_dir,
                    'methylation_output': self.methylation_output_dir
                },
                statistics=stats
            )

            self.context.logger.info("R analysis pipeline completed successfully")
            self.log_complete(result)
            return result

        except Exception as e:
            error_msg = f"R analysis failed: {str(e)}"
            self.context.logger.error(error_msg)
            result = ProcessorResult(
                success=False,
                error=error_msg
            )
            self.log_complete(result)
            return result

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

        # Find barcode directories with summary.csv files
        found_summaries = []
        for item in nanotel_dir.iterdir():
            if item.is_dir() and item.name.startswith('barcode'):
                summary_files = list(item.glob("*summary*.csv"))
                if summary_files:
                    found_summaries.append(item.name)

        if not found_summaries:
            self.context.logger.error(
                f"No NanoTel summary.csv files found in {nanotel_dir}\n"
                "Ensure NanoTel processor completed successfully."
            )
            return False

        self.context.logger.info(f"Found NanoTel summaries for {len(found_summaries)} barcodes")
        return True

    def _validate_aligned_bams(self) -> bool:
        """
        Validate that aligned directory has BAM files (for mapping/methylation).

        Returns:
            True if valid, False otherwise
        """
        aligned_dir = self.context.path_manager.get_aligned_dir()

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

    def _check_bam_methylation(self) -> bool:
        """
        Check if BAM files contain methylation data.

        Returns:
            True if methylation data found, False otherwise
        """
        aligned_dir = self.context.path_manager.get_aligned_dir()
        bam_files = list(aligned_dir.rglob("*.bam"))

        if not bam_files:
            return False

        # Check first few BAM files for methylation tags
        check_count = min(3, len(bam_files))
        has_methylation = False

        for bam in bam_files[:check_count]:
            try:
                # Use samtools to check for MM:Z: methylation tags
                result = subprocess.run(
                    f"samtools view {bam} | head -100 | grep -c 'MM:Z:' || echo 0",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                count = int(result.stdout.strip())

                if count > 0:
                    has_methylation = True
                    break

            except Exception as e:
                self.context.logger.warning(f"Could not check methylation in {bam}: {e}")
                continue

        if not has_methylation:
            self.context.logger.warning(
                "No methylation data found in BAM files.\n"
                "BAMs must be basecalled with --modified-bases flag.\n"
                "Methylation analysis may fail or produce empty results."
            )
            # Return True anyway - let R analysis handle this
            return True

        self.context.logger.info("✓ Methylation data detected in BAM files")
        return True

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
            'nanotel_filtered': self.nanotel_output_dir,  # Filtered summaries here
            'mapping_output': self.mapping_output_dir,
            'methylation_output': self.methylation_output_dir
        }