"""
Demux Processor Module
======================

Handles demultiplexing of basecalled BAM files using Dorado.
Separates reads by barcode and organizes output into barcode directories.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional
from .base import ProcessorBase, ProcessorResult, WorkflowContext


class DemuxProcessor(ProcessorBase):
    """
    Processor for running Dorado demultiplexing.

    Responsibilities:
    - Validate basecalled BAM input exists
    - Build demultiplexing command with appropriate parameters
    - Execute demultiplexing
    - Organize demuxed files into barcode subdirectories
    - Register discovered barcodes with BarcodeManager
    - Collect statistics (barcode counts, file counts)

    Configuration used:
    - kit_name: Sequencing kit used for demultiplexing
    - no_trim: Don't trim adapters
    - sort_bam: Sort output BAM files
    - emit_summary: Generate demux summary file
    """

    def __init__(self, context: WorkflowContext):
        """
        Initialize demux processor.

        Args:
            context: WorkflowContext with all shared resources
        """
        super().__init__(context)

        # Define output directory
        self.output_dir = self.context.path_manager.get_demuxed_dir()

    def validate_inputs(self, basecalled_bam: str) -> bool:
        """
        Validate that all prerequisites for demultiplexing are met.

        Args:
            basecalled_bam: Path to basecalled BAM file

        Returns:
            True if validation passes, False otherwise
        """
        self.context.logger.info("Validating demultiplexing inputs...")

        # Check if basecalled BAM exists
        bam_path = Path(basecalled_bam)
        if not bam_path.exists():
            self.context.logger.error(f"Basecalled BAM not found: {basecalled_bam}")
            return False

        if not bam_path.suffix == '.bam':
            self.context.logger.error(f"Input is not a BAM file: {basecalled_bam}")
            return False

        # Check if dorado is available
        if not self.context.validate_tools(['dorado']):
            return False

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.context.logger.info("✓ All demultiplexing prerequisites validated")
        return True

    def execute(self, basecalled_bam: str) -> ProcessorResult:
        """
        Execute the demultiplexing process.

        Args:
            basecalled_bam: Path to basecalled BAM file

        Returns:
            ProcessorResult with success status, barcode directories, and statistics
        """
        self.log_start()

        # Validate inputs first
        if not self.validate_inputs(basecalled_bam):
            result = ProcessorResult(
                success=False,
                error="Input validation failed"
            )
            self.log_complete(result)
            return result

        try:
            # Build the demultiplexing command
            command = self._build_command(basecalled_bam)

            # Execute demultiplexing
            self.context.logger.info(f"Starting demultiplexing for: {basecalled_bam}")
            self.context.command_executor.execute(command)

            # Organize files into barcode subdirectories
            self.context.logger.info("Organizing demuxed files into barcode directories...")
            barcode_dirs = self._organize_demuxed_files()

            if not barcode_dirs:
                result = ProcessorResult(
                    success=False,
                    error="No demuxed files found after demultiplexing"
                )
                self.log_complete(result)
                return result

            # Register barcodes with BarcodeManager
            self._register_barcodes(barcode_dirs)

            # Collect statistics
            stats = self._collect_statistics(barcode_dirs)

            # Add barcode directories to statistics (not output_paths)
            stats['barcode_dirs'] = barcode_dirs

            # Create successful result
            result = ProcessorResult(
                success=True,
                output_paths={
                    'output_dir': self.output_dir
                },
                statistics=stats
            )

            self.context.logger.info(f"Demultiplexing completed: {len(barcode_dirs)} barcodes found")
            self.log_complete(result)
            return result

        except Exception as e:
            error_msg = f"Demultiplexing failed: {str(e)}"
            self.context.logger.error(error_msg)
            result = ProcessorResult(
                success=False,
                error=error_msg
            )
            self.log_complete(result)
            return result

    def _build_command(self, basecalled_bam: str) -> str:
        """
        Build the dorado demux command.

        Args:
            basecalled_bam: Path to basecalled BAM file

        Returns:
            Command string
        """
        # Get configuration parameters
        demuxing_params = self.context.config_manager.get_demuxing_params()

        kit_name = demuxing_params.get('kit_name')
        no_trim = demuxing_params.get('no_trim', True)
        sort_bam = demuxing_params.get('sort_bam', True)
        emit_summary = demuxing_params.get('emit_summary', True)

        # Build command parts
        cmd_parts = [
            "dorado", "demux",
            f"--output-dir {self.output_dir}",
        ]

        # Add kit name if specified
        if kit_name:
            cmd_parts.append(f"--kit-name {kit_name}")

        # Add optional flags
        if no_trim:
            cmd_parts.append("--no-trim")

        if sort_bam:
            cmd_parts.append("--sort-bam")

        if emit_summary:
            cmd_parts.append("--emit-summary")

        # Add input BAM
        cmd_parts.append(f'"{basecalled_bam}"')

        # Join command parts
        command = " ".join(cmd_parts)

        self.context.logger.info(f"Demux command: {command}")
        return command

    def _organize_demuxed_files(self) -> Dict[str, Path]:
        """
        Organize demuxed BAM files into barcode subdirectories.
        Dorado outputs files with barcode names in the filename.
        This method organizes them into separate barcode directories.

        Returns:
            Dictionary mapping barcode names to their directory paths
        """
        SKIP_FOLDERS = {'unclassified', 'mix'}

        bam_files = list(self.output_dir.rglob("*.bam"))
        bai_files = list(self.output_dir.rglob("*.bam.bai"))

        if not bam_files:
            self.context.logger.warning("No BAM files found to organize")
            return {}

        barcode_files = {}

        for file_path in bam_files + bai_files:
            if 'unclassified' in file_path.name.lower():
                folder_name = 'unclassified'
            elif 'mix' in file_path.name.lower():
                folder_name = 'mix'
            else:
                barcode = self.context.barcode_manager.extract_barcode(str(file_path))
                if barcode:
                    folder_name = barcode.lower()  # keep zero-padding, don't normalize
                else:
                    self.context.logger.warning(
                        f"Could not determine barcode for file: {file_path.name}"
                    )
                    continue

            if folder_name not in barcode_files:
                barcode_files[folder_name] = []
            barcode_files[folder_name].append(file_path)

        barcode_dirs = {}
        for folder_name, files in barcode_files.items():
            if folder_name in SKIP_FOLDERS:
                continue

            target_dir = self.output_dir / folder_name
            target_dir.mkdir(exist_ok=True)

            for file_path in files:
                new_path = target_dir / file_path.name
                if file_path != new_path:  # don't rename if already in right place
                    file_path.rename(new_path)
                    self.context.logger.info(f"Moved {file_path.name} to {folder_name}/")

            barcode_dirs[folder_name] = target_dir

        self.context.logger.info(
            f"Organized {len(barcode_dirs)} directories (barcodes + unclassified)"
        )
        return barcode_dirs

    def _register_barcodes(self, barcode_dirs: Dict[str, Path]) -> None:
        """
        Register discovered barcodes with the BarcodeManager.

        Args:
            barcode_dirs: Dictionary of barcode names to directory paths
        """
        SKIP_FOLDERS = {'unclassified', 'mix'}

        for barcode_name, barcode_dir in barcode_dirs.items():
            if barcode_name in SKIP_FOLDERS:
                continue

            # Register BAM files directly into BarcodeManager
            bam_files = list(barcode_dir.rglob("*.bam"))
            for bam_file in bam_files:
                self.context.barcode_manager.barcode_files[barcode_name].append(bam_file)
                self.context.barcode_manager.discovered_barcodes.add(barcode_name)

            # Mark demux as successful
            self.context.barcode_manager.register_success(barcode_name, 'demux')

        registered = len([b for b in barcode_dirs if b not in SKIP_FOLDERS])
        self.context.logger.info(f"Registered {registered} barcodes")

    def _collect_statistics(self, barcode_dirs: Dict[str, Path]) -> Dict[str, any]:
        """
        Collect statistics about the demultiplexing output.

        Args:
            barcode_dirs: Dictionary of barcode names to directory paths

        Returns:
            Dictionary of statistics
        """
        stats = {
            'total_barcodes': len([b for b in barcode_dirs.keys() if b != 'unclassified']),
            'has_unclassified': 'unclassified' in barcode_dirs,
            'barcode_names': [b for b in barcode_dirs.keys() if b != 'unclassified'],
        }

        # Count BAM files per barcode
        bam_counts = {}
        for barcode_name, barcode_dir in barcode_dirs.items():
            bam_files = list(barcode_dir.rglob("*.bam"))
            bam_counts[barcode_name] = len(bam_files)

        stats['bam_files_per_barcode'] = bam_counts
        stats['total_bam_files'] = sum(bam_counts.values())

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

    def get_barcode_directories(self) -> Dict[str, Path]:
        """
        Get all barcode directories that exist.

        Returns:
            Dictionary mapping barcode names to their directory paths
        """
        barcode_dirs = {}

        if not self.output_dir.exists():
            return barcode_dirs

        # Find all subdirectories
        for subdir in self.output_dir.iterdir():
            if subdir.is_dir():
                barcode_dirs[subdir.name] = subdir

        return barcode_dirs