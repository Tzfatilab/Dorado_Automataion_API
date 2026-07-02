"""
Basecaller Processor Module
===========================

Handles the basecalling step of the workflow using Dorado.
Converts POD5 files to BAM format with base modifications.
"""

from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import os
import shlex
import subprocess
from .base import ProcessorBase, ProcessorResult, WorkflowContext


class BasecallerProcessor(ProcessorBase):
    """
    Processor for running Dorado basecalling.

    Responsibilities:
    - Validate POD5 input exists
    - Build basecalling command with appropriate parameters
    - Execute basecalling
    - Track output BAM file
    - Collect statistics

    Configuration used:
    - model: Path to Dorado model
    - min_qscore: Minimum quality score filter
    - modified_bases: Base modification detection (e.g., '5mCG_5hmCG')
    - kit_name: Sequencing kit used
    - reference: Reference genome for alignment during basecalling
    - recursive: Process POD5 files recursively
    - no_trim: Don't trim adapters
    """

    def __init__(self, context: WorkflowContext):
        """
        Initialize basecaller processor.

        Args:
            context: WorkflowContext with all shared resources
        """
        super().__init__(context)

        # Define output directory
        self.output_dir = self.context.path_manager.get_rebasecalled_dir_path()

    def validate_inputs(self, pod5_input: str, organism: str = "mouse", align : bool = False) -> bool:
        """
        Validate that all prerequisites for basecalling are met.

        Args:
            pod5_input: Path to POD5 input (file or directory)
            organism: Organism type ('mouse' or 'human') for reference selection

        Returns:
            True if validation passes, False otherwise
        """
        self.context.logger.info("Validating basecalling inputs...")

        # Check if POD5 input exists
        pod5_path = Path(pod5_input)
        if not pod5_path.exists():
            self.context.logger.error(f"POD5 input not found: {pod5_input}")
            return False

        # If it's a directory, check for POD5 files
        if pod5_path.is_dir():
            pod5_files = list(pod5_path.rglob("*.pod5"))
            if not pod5_files:
                self.context.logger.error(f"No POD5 files found in directory: {pod5_input}")
                return False
            self.context.logger.info(f"Found {len(pod5_files)} POD5 files")
        else:
            # Single file
            if not pod5_path.suffix == '.pod5':
                self.context.logger.warning(f"Input file does not have .pod5 extension: {pod5_input}")

        # Check if dorado is available
        if not self.context.validate_tools(['dorado']):
            return False

        # Validate model path exists
        model_path = self.context.config_manager.get_dorado_model_path()
        if not Path(model_path).exists():
            self.context.logger.error(f"Dorado model not found: {model_path}")
            return False

        # A reference is required only when aligning during basecalling.
        if align:
            reference_path = self.context.config_manager.get_reference_path(organism)
            if not Path(reference_path).exists():
                self.context.logger.error(f"Reference genome not found: {reference_path}")
                return False

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.context.logger.info("✓ All basecalling prerequisites validated")
        return True

    def execute(self, pod5_input: str, organism: str = "mouse", align : bool = False) -> ProcessorResult:
        """
        Execute the basecalling process.

        Args:
            pod5_input: Path to POD5 input (file or directory)
            organism: Organism type ('mouse' or 'human') for reference selection

        Returns:
            ProcessorResult with success status, output BAM path, and statistics
        """
        self.log_start()

        # Validate inputs first
        if not self.validate_inputs(pod5_input, organism, align):
            result = ProcessorResult(
                success=False,
                error="Input validation failed"
            )
            self.log_complete(result)
            return result

        try:
            self.context.logger.info("Basecalling: preparing Dorado")

            # Build the basecalling command
            command, expected_output = self._build_command(pod5_input, organism, align)

            # Execute basecalling and forward Dorado's live progress to the GUI.
            self.context.logger.info("Basecalling: Dorado is running; live progress follows")
            self.context.command_executor.execute(
                command,
                stream_output=True,
                gui_output_filter=self._show_dorado_gui_line,
            )

            self.context.logger.info("Basecalling: verifying output")
            actual_output = expected_output

            if not actual_output.exists() or actual_output.stat().st_size == 0:
                result = ProcessorResult(
                    success=False,
                    error=f"No BAM output file found after basecalling: {actual_output}"
                )
                self.log_complete(result)
                return result

            # Collect statistics
            self.context.logger.info("Basecalling: collecting output statistics")
            stats = self._collect_statistics(actual_output)

            # Create successful result
            result = ProcessorResult(
                success=True,
                output_paths={
                    'bam': actual_output,
                    'output_dir': self.output_dir
                },
                statistics=stats
            )

            self.context.logger.info(f"Basecalling output: {actual_output}")
            self.log_complete(result)
            return result

        except Exception as e:
            error_msg = f"Basecalling failed: {str(e)}"
            self.context.logger.error(error_msg)
            result = ProcessorResult(
                success=False,
                error=error_msg
            )
            self.log_complete(result)
            return result

    def _build_command(self, pod5_input: str, organism: str, align : bool = False) -> tuple[str, Path]:
        """
        Build the dorado basecalling command.

        Args:
            pod5_input: Path to POD5 input
            organism: Organism type for reference selection

        Returns:
            Tuple of (command string, expected output path)
        """
        # Get configuration parameters
        config = self.context.config_manager
        basecalling_params = config.get_basecalling_params()

        model = config.get_dorado_model_path()
        min_qscore = basecalling_params.get('min_qscore', 9)
        modified_bases = basecalling_params.get('modified_bases', '5mCG_5hmCG')
        kit_name = basecalling_params.get('kit_name')
        reference = config.get_reference_path(organism)
        recursive = basecalling_params.get('recursive', True)
        no_trim = basecalling_params.get('no_trim', True)

        # Generate output filename with timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d_T%H-%M-%S')
        output_file = self.output_dir / f"calls_{timestamp}.bam"

        # Build command parts
        cmd_parts = [
            "dorado", "basecaller",
            "--min-qscore", int(min_qscore),
        ]

        # Add optional flags
        if recursive:
            cmd_parts.append("-r")

        if modified_bases:
            cmd_parts.extend(["--modified-bases", modified_bases])

        if no_trim:
            cmd_parts.append("--no-trim")

        if kit_name:
            cmd_parts.extend(["--kit-name", kit_name])

        if align:
            reference = config.get_reference_path(organism)
            cmd_parts.extend(["--reference", reference])

        # Dorado basecaller writes BAM to stdout; redirect it to the known output file.
        cmd_parts.extend([
            model,
            pod5_input,
        ])

        command = f"{self._format_command(cmd_parts)} > {self._quote_shell_path(output_file)}"

        self.context.logger.info(f"Basecall command: {command}")
        return command, output_file

    def _format_command(self, cmd_parts: list) -> str:
        args = [str(part) for part in cmd_parts]
        if os.name == "nt":
            return subprocess.list2cmdline(args)
        return shlex.join(args)

    def _quote_shell_path(self, path: Path) -> str:
        if os.name == "nt":
            return subprocess.list2cmdline([str(path)])
        return shlex.quote(str(path))

    @staticmethod
    def _show_dorado_gui_line(line: str) -> bool:
        lower = line.lower()
        return "[error]" in lower or "[warning]" in lower

    def _find_output_bam(self) -> Optional[Path]:
        # Look for any BAM file (not per-barcode, so exclude barcode subdirs)
        bam_files = [
            f for f in self.output_dir.rglob("*.bam")
            if 'barcode' not in f.parent.name and 'unclassified' not in f.parent.name
        ]

        if not bam_files:
            self.context.logger.warning("No BAM files found in output directory")
            return None

        latest_bam = max(bam_files, key=lambda x: x.stat().st_mtime)
        self.context.logger.info(f"Found output BAM: {latest_bam}")
        return latest_bam

    def _collect_statistics(self, bam_path: Path) -> Dict[str, any]:
        """
        Collect statistics about the basecalling output.

        Args:
            bam_path: Path to output BAM file

        Returns:
            Dictionary of statistics
        """
        stats = {
            'output_file': bam_path.name,
            'file_size_mb': round(bam_path.stat().st_size / (1024 * 1024), 2),
            'timestamp': datetime.now().isoformat()
        }

        # Could add more statistics here if needed:
        # - Read count (requires parsing BAM)
        # - Quality distribution
        # - etc.

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

    def get_latest_output(self) -> Optional[Path]:
        """
        Convenience method to get the latest basecalled BAM file.

        Returns:
            Path to most recent BAM file, or None if not found
        """
        return self._find_output_bam()
