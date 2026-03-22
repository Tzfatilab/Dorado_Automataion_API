"""
NanoTel Processor Module
========================

Handles telomere analysis using the NanoTel R script.
Processes FASTQ files to identify and analyze telomeric sequences.
"""

from pathlib import Path
from typing import Dict, List, Optional
from .base import ProcessorBase, ProcessorResult, WorkflowContext


class NanoTelProcessor(ProcessorBase):
    """
    Processor for running NanoTel telomere analysis.

    Responsibilities:
    - Validate FASTQ input directory exists
    - Validate NanoTel R script is available
    - Process each barcode's FASTQ files through NanoTel
    - Organize output by barcode
    - Track success/failure per barcode
    - Collect statistics on telomere analysis

    Configuration used:
    - nanotel_script: Path to NanoTel.R script
    - telomere_pattern: Pattern to search for (e.g., "CCCTAA")
    - min_density: Minimum telomere density threshold
    - use_filter: Apply filtering
    """

    def __init__(self, context: WorkflowContext):
        """
        Initialize NanoTel processor.

        Args:
            context: WorkflowContext with all shared resources
        """
        super().__init__(context)

        # Define output directory
        self.output_dir = self.context.path_manager.get_nanotel_output_dir()

    def validate_inputs(self, fastq_dir: str) -> bool:
        """
        Validate that all prerequisites for NanoTel analysis are met.

        Args:
            fastq_dir: Path to directory containing FASTQ files (with barcode subdirs)

        Returns:
            True if validation passes, False otherwise
        """
        self.context.logger.info("Validating NanoTel inputs...")

        # Check if input directory exists
        fastq_path = Path(fastq_dir)
        if not fastq_path.exists():
            self.context.logger.error(f"FASTQ directory not found: {fastq_dir}")
            return False

        if not fastq_path.is_dir():
            self.context.logger.error(f"FASTQ path is not a directory: {fastq_dir}")
            return False

        # Check if Rscript is available
        if not self.context.validate_tools(['Rscript']):
            return False

        # Validate NanoTel script exists
        nanotel_script = self.context.config_manager.get_nanotel_script_path()
        if not Path(nanotel_script).exists():
            self.context.logger.error(f"NanoTel script not found: {nanotel_script}")
            return False

        # Check if there are any FASTQ files or barcode directories
        fastq_files = list(fastq_path.rglob("*.fastq*"))
        if not fastq_files:
            self.context.logger.error(f"No FASTQ files found in: {fastq_dir}")
            return False

        self.context.logger.info(f"Found {len(fastq_files)} FASTQ files")

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.context.logger.info("✓ All NanoTel prerequisites validated")
        return True

    def execute(self, fastq_dir: str, parallel: bool = False) -> ProcessorResult:
        """
        Execute the NanoTel telomere analysis.

        Args:
            fastq_dir: Path to directory containing FASTQ files (with barcode subdirs)
            parallel: Run barcode processing in parallel (currently not implemented)

        Returns:
            ProcessorResult with success status, output directories, and statistics
        """
        self.log_start()

        # Validate inputs first
        if not self.validate_inputs(fastq_dir):
            result = ProcessorResult(
                success=False,
                error="Input validation failed"
            )
            self.log_complete(result)
            return result

        try:
            # Discover barcode directories
            barcode_tasks = self._create_barcode_tasks(fastq_dir)

            if not barcode_tasks:
                result = ProcessorResult(
                    success=False,
                    error="No barcode directories with FASTQ files found"
                )
                self.log_complete(result)
                return result

            self.context.logger.info(f"Processing {len(barcode_tasks)} barcodes")

            # Process each barcode
            # Note: parallel processing could be added later if needed
            results_per_barcode = self._process_barcodes_sequential(barcode_tasks)

            # Collect statistics
            stats = self._collect_statistics(results_per_barcode)

            # Determine overall success
            failed_barcodes = [bc for bc, success in results_per_barcode.items() if not success]
            overall_success = len(failed_barcodes) == 0

            if not overall_success:
                self.context.logger.warning(
                    f"NanoTel failed for {len(failed_barcodes)} barcodes: {failed_barcodes}"
                )

            # Create result
            result = ProcessorResult(
                success=overall_success,
                output_paths={
                    'output_dir': self.output_dir
                },
                statistics=stats,
                error=None if overall_success else f"Failed for barcodes: {failed_barcodes}"
            )

            self.context.logger.info(f"NanoTel output: {self.output_dir}")
            self.log_complete(result)
            return result

        except Exception as e:
            error_msg = f"NanoTel analysis failed: {str(e)}"
            self.context.logger.error(error_msg)
            result = ProcessorResult(
                success=False,
                error=error_msg
            )
            self.log_complete(result)
            return result

    def _create_barcode_tasks(self, fastq_dir: str) -> List[Dict]:
        """
        Create processing tasks for each barcode directory.

        Args:
            fastq_dir: Path to directory containing barcode subdirectories

        Returns:
            List of task dictionaries with barcode info
        """
        fastq_path = Path(fastq_dir)
        tasks = []

        # Find barcode directories
        barcode_dirs = sorted([
            d for d in fastq_path.iterdir()
            if d.is_dir() and 'barcode' in d.name.lower()
        ])

        for barcode_dir in barcode_dirs:
            # Check if this directory has FASTQ files
            fastq_files = list(barcode_dir.glob("*.fastq*"))
            if not fastq_files:
                self.context.logger.warning(
                    f"No FASTQ files found in {barcode_dir.name}, skipping"
                )
                continue

            # Extract and normalize barcode name
            barcode_name = self.context.barcode_manager.extract_barcode(str(barcode_dir))
            if barcode_name:
                barcode_name = self.context.barcode_manager.normalize_barcode(barcode_name)
            else:
                barcode_name = barcode_dir.name

            # Create output directory for this barcode
            barcode_output_dir = self.output_dir / barcode_name
            barcode_output_dir.mkdir(parents=True, exist_ok=True)

            tasks.append({
                'barcode': barcode_name,
                'input_dir': barcode_dir,
                'output_dir': barcode_output_dir,
                'fastq_count': len(fastq_files)
            })

        return tasks

    def _process_barcodes_sequential(self, tasks: List[Dict]) -> Dict[str, bool]:
        """
        Process each barcode sequentially.

        Args:
            tasks: List of barcode processing tasks

        Returns:
            Dictionary mapping barcode names to success status
        """
        results = {}

        for task in tasks:
            barcode = task['barcode']
            self.context.logger.info(
                f"Processing {barcode} ({task['fastq_count']} FASTQ files)..."
            )

            try:
                command = self._build_command(task)
                self.context.command_executor.execute(command)

                # Mark as successful in barcode manager
                self.context.barcode_manager.register_success(barcode, 'nanotel')

                results[barcode] = True
                self.context.logger.info(f"✓ NanoTel completed for {barcode}")

            except Exception as e:
                # Mark as failed in barcode manager
                self.context.barcode_manager.register_failure(
                    barcode, 'nanotel', str(e)
                )

                results[barcode] = False
                self.context.logger.error(f"✗ NanoTel failed for {barcode}: {str(e)}")

        return results

    def _build_command(self, task: Dict) -> str:
        """
        Build the NanoTel R script command.

        Args:
            task: Task dictionary with barcode info

        Returns:
            Command string
        """
        # Get configuration parameters
        config = self.context.config_manager
        nanotel_params = config.get_nanotel_params()

        nanotel_script = config.get_nanotel_script_path()
        telomere_pattern = nanotel_params.get('telomere_pattern', 'CCCTAA')
        min_density = nanotel_params.get('min_density', 0.5)
        use_filter = nanotel_params.get('use_filter', True)

        # Build command parts
        cmd_parts = [
            "Rscript", "--vanilla",
            nanotel_script,
            f"-i {task['input_dir']}",
            f"--save_path {task['output_dir']}",
            f"--patterns {telomere_pattern}",
            f"--min_density {min_density}",
        ]

        # Add filter flag if enabled
        if use_filter:
            cmd_parts.append("--use_filter")

        # Join command parts
        command = " ".join(cmd_parts)

        return command

    def _collect_statistics(self, results_per_barcode: Dict[str, bool]) -> Dict[str, any]:
        """
        Collect statistics about the NanoTel analysis.

        Args:
            results_per_barcode: Dictionary of barcode processing results

        Returns:
            Dictionary of statistics
        """
        successful_barcodes = [bc for bc, success in results_per_barcode.items() if success]
        failed_barcodes = [bc for bc, success in results_per_barcode.items() if not success]

        stats = {
            'total_barcodes': len(results_per_barcode),
            'successful_barcodes': len(successful_barcodes),
            'failed_barcodes': len(failed_barcodes),
            'barcode_results': results_per_barcode,
        }

        # Count output files per barcode
        output_files_per_barcode = {}
        for barcode in successful_barcodes:
            barcode_dir = self.output_dir / barcode
            if barcode_dir.exists():
                output_files = list(barcode_dir.glob("*"))
                output_files_per_barcode[barcode] = len(output_files)

        stats['output_files_per_barcode'] = output_files_per_barcode

        return stats

    def get_output_paths(self) -> Dict[str, Path]:
        """
        Get the expected output paths for this processor.

        Returns:
            Dictionary with 'output_dir' key
        """
        return {
            'output_dir': self.output_dir
        }

    def get_barcode_output_dirs(self) -> Dict[str, Path]:
        """
        Get output directories for each processed barcode.

        Returns:
            Dictionary mapping barcode names to their output directory paths
        """
        barcode_dirs = {}

        if not self.output_dir.exists():
            return barcode_dirs

        # Find all barcode subdirectories
        for subdir in self.output_dir.iterdir():
            if subdir.is_dir():
                barcode_dirs[subdir.name] = subdir

        return barcode_dirs