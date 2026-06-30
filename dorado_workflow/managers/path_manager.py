"""
Path Manager Module
==================

Handles all directory structure creation and path management for the workflow.
Works with ConfigManager to use configured directory naming conventions.
"""

from pathlib import Path
from typing import Optional
from datetime import datetime
import os
import re
import shutil
import stat
import time

class PathManager:
    """
    Manages directory structure and file paths for a workflow trial.

    Features:
    - Creates standardized trial directory structure
    - Provides path getter methods for all subdirectories
    - Generates timestamped log file paths
    - On-demand directory creation
    - Uses ConfigManager for directory naming conventions
    """

    def __init__(self, trial_name: str, base_output_dir: Optional[str] = None,
                 config_manager=None):
        """
        Initialize the path manager.

        Args:
            trial_name: Name of the trial (e.g., "Trial_99_Mouse")
            base_output_dir: Base output directory. If None, uses config default.
            config_manager: ConfigManager instance for accessing config

        Note: Directories are NOT created during initialization. Use the
              *_path methods to get paths without creating them, or the
              existing getters when a directory should be created immediately.
        """
        self.trial_name = trial_name
        self.config_manager = config_manager

        # Determine base output directory
        if base_output_dir:
            self.base_output_dir = Path(base_output_dir)
        elif config_manager:
            self.base_output_dir = Path(config_manager.get_default_output_base())
        else:
            raise ValueError("Either base_output_dir or config_manager must be provided")

        # Trial root directory
        self.trial_dir = self.base_output_dir / trial_name

        # Get directory naming conventions from config
        if config_manager:
            self.dir_structure = config_manager.get_directory_structure()
        else:
            # Fallback defaults if no config provided
            self.dir_structure = {
                'raw_data': 'processing',
                'results': 'results',
                'reports': 'reports',
                'rebasecalled': 'basecalled',
                'demuxed': 'demultiplexed',
                'fastqs': 'fastq',
                'nanotel_output': 'nanotel',
                'aligned': 'aligned',
                'r_analysis': 'results',
                'mapping_output': 'mapping',
                'methylation_output': 'methylation',
                'logs': 'logs'
            }

        # Cache for created directories
        self._created_dirs = set()

    # ==================== Directory Creation ====================

    def _ensure_directory(self, directory: Path) -> Path:
        """
        Ensure a directory exists, creating it if necessary.
        Thread-safe and idempotent.

        Args:
            directory: Path to ensure exists

        Returns:
            The directory path
        """
        if directory not in self._created_dirs:
            directory.mkdir(parents=True, exist_ok=True)
            self._created_dirs.add(directory)
        return directory

    def _normalize_barcode(self, barcode: str) -> str:
        """Normalize barcode name to zero-padded form (e.g., 'barcode6' -> 'barcode06')."""
        match = re.search(r'(?:barcode|bc)(\d+)', barcode, re.IGNORECASE)
        if not match:
            return barcode
        return f"barcode{int(match.group(1)):02d}"

    def _resolve_barcode_dir(self, parent: Path, barcode: str) -> Path:
        """Return canonical padded barcode dir under `parent`, merging any unpadded duplicate."""
        canonical_name = self._normalize_barcode(barcode)
        canonical_path = parent / canonical_name

        if parent.exists():
            for sibling in parent.iterdir():
                if (sibling.is_dir()
                        and sibling.name != canonical_name
                        and self._normalize_barcode(sibling.name) == canonical_name):
                    # Merge sibling contents into canonical, then remove sibling
                    canonical_path.mkdir(parents=True, exist_ok=True)
                    for child in sibling.iterdir():
                        dest = canonical_path / child.name
                        if not dest.exists():
                            shutil.move(str(child), str(dest))
                    try:
                        sibling.rmdir()
                    except OSError:
                        pass  # not empty due to conflicts — leave for manual review

        return self._ensure_directory(canonical_path)

    def create_all_directories(self) -> None:
        """
        Create all standard directories for the trial.
        This is a convenience method to create everything upfront.
        """
        # Main trial directories
        self._ensure_directory(self.get_trial_dir())
        self._ensure_directory(self.get_raw_data_dir())
        self._ensure_directory(self.get_results_dir())
        self._ensure_directory(self.get_reports_dir())
        self._ensure_directory(self.get_rebasecalled_dir())
        self._ensure_directory(self.get_demuxed_dir())
        self._ensure_directory(self.get_fastq_dir())
        self._ensure_directory(self.get_nanotel_output_dir())
        self._ensure_directory(self.get_aligned_dir())
        self._ensure_directory(self.get_logs_dir())

        # R analysis directories
        self._ensure_directory(self.get_r_analysis_dir())
        self._ensure_directory(self.get_r_nanotel_output_dir())
        self._ensure_directory(self.get_r_mapping_output_dir())

    def reset_generated_outputs(
            self,
            include_results: bool = True,
            archive_existing: bool = False,
            include_basecalling_outputs: bool = True,
            include_fastq_outputs: bool = True,
            include_aligned_outputs: bool = True,
    ) -> None:
        """
        Prepare generated workflow outputs for a fresh run.

        The GUI intentionally uses a stable "Telomere Analyzer" trial folder.
        Without clearing these folders, stale barcodes/BAMs/FASTQs from a
        previous run can be picked up by later workflow stages.

        When archive_existing is enabled, previous outputs are moved under
        previous_runs/<timestamp>/ instead of being deleted.
        """
        archive_root = None
        if archive_existing:
            archive_root = (
                self.get_trial_dir_path()
                / "previous_runs"
                / datetime.now().strftime("%Y%m%d_%H%M%S")
            )

        targets = []
        if include_basecalling_outputs:
            targets.extend([
                self.get_rebasecalled_dir_path(),
                self.get_demuxed_dir_path(),
            ])
        if include_fastq_outputs:
            targets.append(self.get_fastq_dir_path())
        if include_aligned_outputs:
            targets.append(self.get_aligned_dir_path())
        remove_only_targets = [
            self.get_processing_dir_path() / "alignment_input",
        ]

        if include_results:
            targets.extend([
                self.get_nanotel_output_dir_path(),
                self.get_r_mapping_output_dir_path(),
                self.get_reports_dir_path(),
            ])

        for target in targets:
            self._reset_generated_path(target, archive_root=archive_root)
        for target in remove_only_targets:
            self._reset_generated_path(
                target,
                archive_root=archive_root,
                recreate=False,
            )

    def _reset_generated_path(
            self,
            target: Path,
            archive_root: Optional[Path] = None,
            recreate: bool = True,
    ) -> None:
        """Archive or remove a generated path, guarded to stay inside trial_dir."""
        trial_root = self.trial_dir.resolve(strict=False)
        resolved = target.resolve(strict=False)

        if resolved == trial_root or trial_root not in resolved.parents:
            raise ValueError(f"Refusing to clear path outside trial directory: {target}")

        if target.exists():
            if archive_root is not None:
                self._archive_generated_path(target, archive_root)
            elif target.is_dir():
                self._clear_generated_dir(target)
            else:
                self._make_writable(target)
                target.unlink()

        self._created_dirs.discard(target)
        if recreate:
            self._ensure_directory(target)

    def _archive_generated_path(self, target: Path, archive_root: Path) -> None:
        """Move a generated path into previous_runs while preserving its layout."""
        trial_root = self.trial_dir.resolve(strict=False)
        resolved_archive = archive_root.resolve(strict=False)

        if resolved_archive == trial_root or trial_root not in resolved_archive.parents:
            raise ValueError(f"Refusing to archive outside trial directory: {archive_root}")

        relative_target = target.resolve(strict=False).relative_to(trial_root)
        destination = archive_root / relative_target

        for _ in range(3):
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination = self._unique_archive_destination(destination)
                shutil.move(str(target), str(destination))
                return
            except (OSError, PermissionError):
                time.sleep(0.2)

        raise OSError(
            f"Could not archive previous output path: {target}. "
            "Close any open files in that folder and try again."
        )

    @staticmethod
    def _unique_archive_destination(destination: Path) -> Path:
        """Avoid replacing an existing archived path in the same timestamp folder."""
        if not destination.exists():
            return destination

        suffix = datetime.now().strftime("%H%M%S_%f")
        return destination.with_name(f"{destination.name}_{suffix}")

    def _clear_generated_dir(self, target: Path) -> None:
        """Clear a generated directory while tolerating Windows/OneDrive locks."""
        for _ in range(3):
            try:
                shutil.rmtree(target, onerror=self._handle_remove_readonly)
                if not target.exists() or not any(target.iterdir()):
                    return
            except (OSError, PermissionError):
                time.sleep(0.2)

        # If Windows refuses to remove the directory itself, remove its children
        # and leave the empty directory in place for the new run.
        if not target.exists():
            return

        for child in target.iterdir():
            self._remove_generated_child(child)

    def _remove_generated_child(self, child: Path) -> None:
        """Best-effort removal for generated files/folders on Windows."""
        for _ in range(3):
            try:
                if child.is_dir():
                    shutil.rmtree(child, onerror=self._handle_remove_readonly)
                else:
                    self._make_writable(child)
                    child.unlink()
                if not child.exists():
                    return
            except (OSError, PermissionError):
                time.sleep(0.2)

    def _handle_remove_readonly(self, func, path, exc_info) -> None:
        self._make_writable(Path(path))
        try:
            func(path)
        except (OSError, PermissionError):
            pass

    @staticmethod
    def _make_writable(path: Path) -> None:
        if path.exists():
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)

    # ==================== Main Directory Getters ====================

    def _raw_data_path(self) -> Path:
        """Return the processing/intermediate data root path without creating it."""
        return self.trial_dir / self.dir_structure.get('raw_data', 'processing')

    def _results_path(self) -> Path:
        """Return the analysis results root path without creating it."""
        return self.trial_dir / self.dir_structure.get('results', 'results')

    def _directory_path(self, key: str) -> Path:
        """Return a configured trial subdirectory path without creating it."""
        return self.trial_dir / self.dir_structure[key]

    def get_trial_dir_path(self) -> Path:
        """Get the trial root directory path without creating it."""
        return self.trial_dir

    def get_raw_data_dir_path(self) -> Path:
        """Get the processing/intermediate data root path without creating it."""
        return self._raw_data_path()

    def get_processing_dir_path(self) -> Path:
        """Get the processing/intermediate data root path without creating it."""
        return self._raw_data_path()

    def get_results_dir_path(self) -> Path:
        """Get the analysis results root path without creating it."""
        return self._results_path()

    def get_reports_dir_path(self) -> Path:
        """Get the reports/configuration output path without creating it."""
        return self._results_path() / self.dir_structure.get('reports', 'reports')

    def get_rebasecalled_dir_path(self) -> Path:
        """Get the rebasecalled directory path without creating it."""
        return self._raw_data_path() / self.dir_structure['rebasecalled']

    def get_demuxed_dir_path(self) -> Path:
        """Get the demuxed directory path without creating it."""
        return self._raw_data_path() / self.dir_structure['demuxed']

    def get_fastq_dir_path(self) -> Path:
        """Get the FASTQ files directory path without creating it."""
        return self._raw_data_path() / self.dir_structure['fastqs']

    def get_nanotel_output_dir_path(self) -> Path:
        """Get the NanoTel output directory path without creating it."""
        return self._results_path() / self.dir_structure['nanotel_output']

    def get_aligned_dir_path(self) -> Path:
        """Get the aligned directory path without creating it."""
        return self._raw_data_path() / self.dir_structure['aligned']

    def get_logs_dir_path(self) -> Path:
        """Get the logs directory path without creating it."""
        return self._results_path() / self.dir_structure['logs']

    def get_r_analysis_dir_path(self) -> Path:
        """Get the R analysis base directory path without creating it."""
        return self.trial_dir / self.dir_structure.get(
            'r_analysis',
            self.dir_structure.get('results', 'results')
        )

    def get_r_nanotel_output_dir_path(self) -> Path:
        """Get the R NanoTel analysis output directory path without creating it."""
        return self.get_nanotel_output_dir_path()

    def get_r_mapping_output_dir_path(self) -> Path:
        """Get the R mapping analysis output directory path without creating it."""
        return self.get_r_analysis_dir_path() / self.dir_structure['mapping_output']

    def get_r_methylation_output_dir_path(self) -> Path:
        """Get the R methylation analysis output directory path without creating it."""
        return self.get_r_analysis_dir_path() / self.dir_structure['methylation_output']

    def get_trial_dir(self) -> Path:
        """Get the trial root directory."""
        return self._ensure_directory(self.trial_dir)

    def get_raw_data_dir(self) -> Path:
        """Get the processing/intermediate data root directory."""
        return self._ensure_directory(self.get_raw_data_dir_path())

    def get_processing_dir(self) -> Path:
        """Get the processing/intermediate data root directory."""
        return self._ensure_directory(self.get_processing_dir_path())

    def get_results_dir(self) -> Path:
        """Get the analysis results root directory."""
        return self._ensure_directory(self.get_results_dir_path())

    def get_reports_dir(self) -> Path:
        """Get the reports/configuration output directory."""
        return self._ensure_directory(self.get_reports_dir_path())

    def get_rebasecalled_dir(self) -> Path:
        """Get the rebasecalled directory."""
        return self._ensure_directory(self.get_rebasecalled_dir_path())

    def get_demuxed_dir(self) -> Path:
        """Get the demuxed directory."""
        return self._ensure_directory(self.get_demuxed_dir_path())

    def get_fastq_dir(self) -> Path:
        """Get the FASTQ files directory."""
        return self._ensure_directory(self.get_fastq_dir_path())

    def get_nanotel_output_dir(self) -> Path:
        """Get the NanoTel output directory."""
        return self._ensure_directory(self.get_nanotel_output_dir_path())

    def get_aligned_dir(self) -> Path:
        """Get the aligned directory."""
        return self._ensure_directory(self.get_aligned_dir_path())

    def get_logs_dir(self) -> Path:
        """Get the logs directory."""
        return self._ensure_directory(self.get_logs_dir_path())

    # ==================== R Analysis Directory Getters ====================

    def get_r_analysis_dir(self) -> Path:
        """Get the R analysis base directory."""
        return self._ensure_directory(self.get_r_analysis_dir_path())

    def get_r_nanotel_output_dir(self) -> Path:
        """Get the R NanoTel analysis output directory."""
        return self._ensure_directory(self.get_r_nanotel_output_dir_path())

    def get_r_mapping_output_dir(self) -> Path:
        """Get the R mapping analysis output directory."""
        return self._ensure_directory(self.get_r_mapping_output_dir_path())

    def get_r_methylation_output_dir(self) -> Path:
        """Get the R methylation analysis output directory."""
        return self._ensure_directory(self.get_r_methylation_output_dir_path())

    # ==================== Barcode Subdirectory Helpers ====================

    def get_barcode_fastq_dir(self, barcode: str) -> Path:
        """
        Get FASTQ directory for a specific barcode.

        Args:
            barcode: Barcode name (e.g., "barcode01")

        Returns:
            Path to barcode's FASTQ directory
        """
        return self._resolve_barcode_dir(self.get_fastq_dir(), barcode)

    def get_barcode_nanotel_dir(self, barcode: str) -> Path:
        """
        Get NanoTel output directory for a specific barcode.

        Args:
            barcode: Barcode name (e.g., "barcode01")

        Returns:
            Path to barcode's NanoTel directory
        """
        return self._resolve_barcode_dir(self.get_nanotel_output_dir(), barcode)

    def get_barcode_mapping_dir(self, barcode: str) -> Path:
        """
        Get mapping output directory for a specific barcode.

        Args:
            barcode: Barcode name (e.g., "barcode01")

        Returns:
            Path to barcode's mapping directory
        """
        return self._resolve_barcode_dir(self.get_r_mapping_output_dir(), barcode)

    def get_barcode_demuxed_dir(self, barcode: str) -> Path:
        """
        Get demuxed directory for a specific barcode.

        Args:
            barcode: Barcode name (e.g., "barcode01")

        Returns:
            Path to barcode's demuxed directory
        """
        return self._resolve_barcode_dir(self.get_demuxed_dir(), barcode)

    def get_barcode_aligned_dir(self, barcode: str) -> Path:
        """
        Get aligned directory for a specific barcode.

        Args:
            barcode: Barcode name (e.g., "barcode01")

        Returns:
            Path to barcode's aligned directory
        """
        return self._resolve_barcode_dir(self.get_aligned_dir(), barcode)

    # ==================== File Path Generators ====================

    def get_log_file_path(self, timestamp: Optional[str] = None) -> Path:
        """
        Generate log file path with timestamp.

        Args:
            timestamp: Optional timestamp string. If None, generates current timestamp.

        Returns:
            Path to log file
        """
        if timestamp is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        log_filename = f"{self.trial_name}_{timestamp}.log"
        return self.get_logs_dir() / log_filename

    def get_command_history_path(self, timestamp: Optional[str] = None) -> Path:
        """
        Generate command history script path.

        Args:
            timestamp: Optional timestamp string. If None, generates current timestamp.

        Returns:
            Path to command history script
        """
        if timestamp is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        script_filename = f"commands_executed_{timestamp}.sh"
        return self.get_logs_dir() / script_filename

    def get_summary_report_path(self, timestamp: Optional[str] = None) -> Path:
        """
        Generate summary report path.

        Args:
            timestamp: Optional timestamp string. If None, generates current timestamp.

        Returns:
            Path to summary report
        """
        if timestamp is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        report_filename = f"{self.trial_name}_summary_{timestamp}.txt"
        return self.get_logs_dir() / report_filename

    def get_basecalled_bam_path(self, timestamp: Optional[str] = None) -> Path:
        """
        Generate basecalled BAM file path.

        Args:
            timestamp: Optional timestamp string. If None, generates current timestamp.

        Returns:
            Path to basecalled BAM file
        """
        if timestamp is None:
            timestamp = datetime.now().strftime('%Y-%m-%d_T%H-%M-%S')

        bam_filename = f"calls_{timestamp}.bam"
        return self.get_rebasecalled_dir() / bam_filename

    def get_alignment_summary_path(self) -> Path:
        """
        Get path to alignment summary file.

        Returns:
            Path to Dorado alignment summary.
        """
        aligned_dir = self.get_aligned_dir_path()
        candidates = [
            aligned_dir / "sequencing_summary.txt",
            aligned_dir / "alignment_summary.txt",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    # ==================== R Config Generation ====================

    def generate_r_pipeline_config(self) -> dict:
        """
        Generate R pipeline configuration with all required paths.
        This config will be passed to the R analysis scripts.

        Returns:
            Dictionary with R pipeline configuration
        """
        return {
            "base_output_dir": str(self.get_results_dir_path()),
            "raw_data_dir": str(self.get_raw_data_dir_path()),
            "processing_dir": str(self.get_processing_dir_path()),
            "results_dir": str(self.get_results_dir_path()),
            "reports_dir": str(self.get_reports_dir_path()),

            "nanotel_analysis": {
                "input_dir": str(self.get_nanotel_output_dir_path()),
                "output_dir": str(self.get_r_nanotel_output_dir_path())
            },

            "mapping_analysis": {
                "alignment_summary_path": str(self.get_alignment_summary_path()),
                "filtered_nanotel_dir": str(self.get_r_nanotel_output_dir_path()),
                "bam_dir": str(self.get_aligned_dir_path()),
                "output_dir": str(self.get_r_mapping_output_dir_path())
            },

            "methylation_analysis": {
                "pileup_bed_dir": str(self.get_r_mapping_output_dir_path()),
                "output_dir": str(self.get_r_methylation_output_dir_path())
            }
        }

    # ==================== Utility Methods ====================

    def get_all_paths_summary(self) -> dict:
        """
        Get a summary of all main paths.
        Useful for logging/debugging.

        Returns:
            Dictionary with all main directory paths
        """
        return {
            'trial_dir': str(self.trial_dir),
            'raw_data': str(self.get_raw_data_dir_path()),
            'processing': str(self.get_processing_dir_path()),
            'results': str(self.get_results_dir_path()),
            'reports': str(self.get_reports_dir_path()),
            'rebasecalled': str(self.get_rebasecalled_dir_path()),
            'demuxed': str(self.get_demuxed_dir_path()),
            'fastqs': str(self.get_fastq_dir_path()),
            'nanotel_output': str(self.get_nanotel_output_dir_path()),
            'aligned': str(self.get_aligned_dir_path()),
            'r_analysis': str(self.get_r_analysis_dir_path()),
            'mapping_output': str(self.get_r_mapping_output_dir_path()),
            'methylation_output': str(self.get_r_methylation_output_dir_path()),
            'logs': str(self.get_logs_dir_path())
        }

    def __repr__(self) -> str:
        """String representation of PathManager."""
        return f"PathManager(trial_name={self.trial_name}, trial_dir={self.trial_dir})"
