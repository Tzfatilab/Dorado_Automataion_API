"""
Alignment Processor Module
==========================

Handles alignment of demuxed BAM or FASTQ files to reference genome using Dorado aligner.
"""

from pathlib import Path
from typing import Dict, Optional
from .base import ProcessorBase, ProcessorResult, WorkflowContext


class AlignmentProcessor(ProcessorBase):
    """
    Processor for running Dorado alignment.

    Responsibilities:
    - Validate input directory exists and contains BAM/FASTQ files
    - Auto-detect input type (BAM or FASTQ)
    - Build alignment command with appropriate parameters
    - Execute alignment to reference genome
    - Track output and collect statistics

    Configuration used:
    - reference genome path (organism-specific)
    - emit_summary option
    """

    def __init__(self, context: WorkflowContext):
        """
        Initialize alignment processor.

        Args:
            context: WorkflowContext with all shared resources
        """
        super().__init__(context)

        # Define output directory
        self.output_dir = self.context.path_manager.get_aligned_dir()

    def validate_inputs(self, input_dir: str, organism: str = "mouse") -> bool:
        """
        Validate that all prerequisites for alignment are met.

        Args:
            input_dir: Path to directory containing BAM or FASTQ files
            organism: Organism type ('mouse' or 'human') for reference selection

        Returns:
            True if validation passes, False otherwise
        """
        self.context.logger.info("Validating alignment inputs...")

        # Check if input directory exists
        input_path = Path(input_dir)
        if not input_path.exists():
            self.context.logger.error(f"Input directory not found: {input_dir}")
            return False

        if not input_path.is_dir():
            self.context.logger.error(f"Input path is not a directory: {input_dir}")
            return False

        # Check if dorado is available
        if not self.context.validate_tools(['dorado']):
            return False

        # Validate reference path exists
        reference_path = self.context.config_manager.get_reference_path(organism)
        if not Path(reference_path).exists():
            self.context.logger.error(f"Reference genome not found: {reference_path}")
            return False

        # Check if input directory contains BAM or FASTQ files
        input_type = self._detect_input_type(input_path)
        if not input_type:
            self.context.logger.error(f"No BAM or FASTQ files found in: {input_dir}")
            return False

        self.context.logger.info(f"Detected input type: {input_type}")

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.context.logger.info("✓ All alignment prerequisites validated")
        return True

    def execute(self, input_dir: str, organism: str = "mouse",
                input_type: str = "auto") -> ProcessorResult:
        """
        Execute the alignment process.

        Args:
            input_dir: Path to directory containing BAM or FASTQ files
            organism: Organism type ('mouse' or 'human') for reference selection
            input_type: 'bam', 'fastq', or 'auto' (auto-detect)

        Returns:
            ProcessorResult with success status, output directory, and statistics
        """
        self.log_start()

        # Validate inputs first
        if not self.validate_inputs(input_dir, organism):
            result = ProcessorResult(
                success=False,
                error="Input validation failed"
            )
            self.log_complete(result)
            return result

        try:
            # Auto-detect input type if needed
            if input_type == "auto":
                input_type = self._detect_input_type(Path(input_dir))
                self.context.logger.info(f"Auto-detected input type: {input_type}")

            # Build the alignment command
            command = self._build_command(input_dir, organism, input_type)

            # Execute alignment
            self.context.logger.info(f"Starting alignment for: {input_dir}")
            self.context.logger.info(f"Using {input_type.upper()} input")
            self.context.command_executor.execute(command)

            # Collect statistics
            stats = self._collect_statistics(input_type)

            # Create successful result
            result = ProcessorResult(
                success=True,
                output_paths={
                    'output_dir': self.output_dir
                },
                statistics=stats
            )

            self.context.logger.info(f"Alignment output: {self.output_dir}")
            self.log_complete(result)
            return result

        except Exception as e:
            error_msg = f"Alignment failed: {str(e)}"
            self.context.logger.error(error_msg)
            result = ProcessorResult(
                success=False,
                error=error_msg
            )
            self.log_complete(result)
            return result

    def _build_command(self, input_dir: str, organism: str, input_type: str) -> str:
        """
        Build the dorado aligner command.

        Args:
            input_dir: Path to input directory
            organism: Organism type for reference selection
            input_type: 'bam' or 'fastq'

        Returns:
            Command string
        """
        # Get configuration parameters
        config = self.context.config_manager
        alignment_params = config.get_alignment_params()

        reference = config.get_reference_path(organism)
        emit_summary = alignment_params.get('emit_summary', True)

        # Build command parts
        cmd_parts = [
            "dorado", "aligner",
            "-r",  # Recursive
            f"--output-dir {self.output_dir}",
        ]

        # Add emit-summary flag if configured
        if emit_summary:
            cmd_parts.append("--emit-summary")

        # Add reference and input directory
        cmd_parts.extend([
            reference,
            input_dir
        ])

        # Join command parts
        command = " ".join(cmd_parts)

        self.context.logger.info(f"Alignment command: {command}")
        return command

    def _detect_input_type(self, input_path: Path) -> Optional[str]:
        """
        Auto-detect if input directory contains BAM or FASTQ files.

        Args:
            input_path: Path to input directory

        Returns:
            'bam', 'fastq', or None if no files found
        """
        # Look for files recursively (in case of barcode subdirectories)
        bam_files = list(input_path.rglob("*.bam"))
        fastq_files = list(input_path.rglob("*.fastq*"))

        if bam_files and not fastq_files:
            return "bam"
        elif fastq_files and not bam_files:
            return "fastq"
        elif bam_files and fastq_files:
            # Both exist - prefer BAM (more processed)
            self.context.logger.warning("Both BAM and FASTQ files found, using BAM files")
            return "bam"
        else:
            return None

    def _collect_statistics(self, input_type: str) -> Dict[str, any]:
        """
        Collect statistics about the alignment output.

        Args:
            input_type: Type of input files used

        Returns:
            Dictionary of statistics
        """
        stats = {
            'input_type': input_type,
        }

        # Count output files if directory exists
        if self.output_dir.exists():
            aligned_files = list(self.output_dir.glob("*"))
            stats['output_file_count'] = len(aligned_files)

            # Count specific file types
            bam_files = list(self.output_dir.glob("*.bam"))
            summary_files = list(self.output_dir.glob("*summary*"))

            stats['aligned_bam_count'] = len(bam_files)
            stats['summary_file_count'] = len(summary_files)

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

    def get_aligned_files(self) -> list[Path]:
        """
        Get all aligned BAM files.

        Returns:
            List of aligned BAM file paths
        """
        if not self.output_dir.exists():
            return []

        return list(self.output_dir.glob("*.bam"))