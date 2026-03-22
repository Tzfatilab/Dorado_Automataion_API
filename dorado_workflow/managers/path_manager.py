"""
Path Manager Module
==================

Handles all directory structure creation and path management for the workflow.
Works with ConfigManager to use configured directory naming conventions.
"""

from pathlib import Path
from typing import Optional
from datetime import datetime


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

        Note: Directories are NOT created during initialization.
              Use create_all_directories() or individual getters to create them.
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
                'rebasecalled': 'rebasecalled',
                'demuxed': 'demuxed',
                'fastqs': 'fastqs',
                'nanotel_output': 'nanotel_output',
                'aligned': 'aligned',
                'r_analysis': 'r_analysis',
                'mapping_output': 'mapping_output',
                'methylation_output': 'methylation_output',
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

    def create_all_directories(self) -> None:
        """
        Create all standard directories for the trial.
        This is a convenience method to create everything upfront.
        """
        # Main trial directories
        self._ensure_directory(self.get_trial_dir())
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
        self._ensure_directory(self.get_r_methylation_output_dir())

    # ==================== Main Directory Getters ====================

    def get_trial_dir(self) -> Path:
        """Get the trial root directory."""
        return self._ensure_directory(self.trial_dir)

    def get_rebasecalled_dir(self) -> Path:
        """Get the rebasecalled directory."""
        dir_path = self.trial_dir / self.dir_structure['rebasecalled']
        return self._ensure_directory(dir_path)

    def get_demuxed_dir(self) -> Path:
        """Get the demuxed directory."""
        dir_path = self.trial_dir / self.dir_structure['demuxed']
        return self._ensure_directory(dir_path)

    def get_fastq_dir(self) -> Path:
        """Get the FASTQ files directory."""
        dir_path = self.trial_dir / self.dir_structure['fastqs']
        return self._ensure_directory(dir_path)

    def get_nanotel_output_dir(self) -> Path:
        """Get the NanoTel output directory."""
        dir_path = self.trial_dir / self.dir_structure['nanotel_output']
        return self._ensure_directory(dir_path)

    def get_aligned_dir(self) -> Path:
        """Get the aligned directory."""
        dir_path = self.trial_dir / self.dir_structure['aligned']
        return self._ensure_directory(dir_path)

    def get_logs_dir(self) -> Path:
        """Get the logs directory."""
        dir_path = self.trial_dir / self.dir_structure['logs']
        return self._ensure_directory(dir_path)

    # ==================== R Analysis Directory Getters ====================

    def get_r_analysis_dir(self) -> Path:
        """Get the R analysis base directory."""
        dir_path = self.trial_dir / self.dir_structure['r_analysis']
        return self._ensure_directory(dir_path)

    def get_r_nanotel_output_dir(self) -> Path:
        """Get the R NanoTel analysis output directory."""
        dir_path = self.trial_dir / self.dir_structure['nanotel_output']
        return self._ensure_directory(dir_path)

    def get_r_mapping_output_dir(self) -> Path:
        """Get the R mapping analysis output directory."""
        dir_path = self.get_r_analysis_dir() / self.dir_structure['mapping_output']
        return self._ensure_directory(dir_path)

    def get_r_methylation_output_dir(self) -> Path:
        """Get the R methylation analysis output directory."""
        dir_path = self.get_r_analysis_dir() / self.dir_structure['methylation_output']
        return self._ensure_directory(dir_path)

    # ==================== Barcode Subdirectory Helpers ====================

    def get_barcode_fastq_dir(self, barcode: str) -> Path:
        """
        Get FASTQ directory for a specific barcode.

        Args:
            barcode: Barcode name (e.g., "barcode01")

        Returns:
            Path to barcode's FASTQ directory
        """
        dir_path = self.get_fastq_dir() / barcode
        return self._ensure_directory(dir_path)

    def get_barcode_nanotel_dir(self, barcode: str) -> Path:
        """
        Get NanoTel output directory for a specific barcode.

        Args:
            barcode: Barcode name (e.g., "barcode01")

        Returns:
            Path to barcode's NanoTel directory
        """
        dir_path = self.get_nanotel_output_dir() / barcode
        return self._ensure_directory(dir_path)

    def get_barcode_mapping_dir(self, barcode: str) -> Path:
        """
        Get mapping output directory for a specific barcode.

        Args:
            barcode: Barcode name (e.g., "barcode01")

        Returns:
            Path to barcode's mapping directory
        """
        dir_path = self.get_r_mapping_output_dir() / barcode
        return self._ensure_directory(dir_path)

    def get_barcode_demuxed_dir(self, barcode: str) -> Path:
        """
        Get demuxed directory for a specific barcode.

        Args:
            barcode: Barcode name (e.g., "barcode01")

        Returns:
            Path to barcode's demuxed directory
        """
        dir_path = self.get_demuxed_dir() / barcode
        return self._ensure_directory(dir_path)

    def get_barcode_aligned_dir(self, barcode: str) -> Path:
        """
        Get aligned directory for a specific barcode.

        Args:
            barcode: Barcode name (e.g., "barcode01")

        Returns:
            Path to barcode's aligned directory
        """
        dir_path = self.get_aligned_dir() / barcode
        return self._ensure_directory(dir_path)

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
            Path to alignment_summary.txt
        """
        return self.get_aligned_dir() / "alignment_summary.txt"

    # ==================== R Config Generation ====================

    def generate_r_pipeline_config(self) -> dict:
        """
        Generate R pipeline configuration with all required paths.
        This config will be passed to the R analysis scripts.

        Returns:
            Dictionary with R pipeline configuration
        """
        return {
            "base_output_dir": str(self.trial_dir),

            "nanotel_analysis": {
                "input_dir": str(self.get_nanotel_output_dir()),
                "output_dir": str(self.get_r_nanotel_output_dir())
            },

            "mapping_analysis": {
                "alignment_summary_path": str(self.get_alignment_summary_path()),
                "filtered_nanotel_dir": str(self.get_r_nanotel_output_dir()),
                "bam_dir": str(self.get_aligned_dir()),
                "output_dir": str(self.get_r_mapping_output_dir())
            },

            "methylation_analysis": {
                "pileup_bed_dir": str(self.get_r_mapping_output_dir()),
                "output_dir": str(self.get_r_methylation_output_dir())
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
            'rebasecalled': str(self.trial_dir / self.dir_structure['rebasecalled']),
            'demuxed': str(self.trial_dir / self.dir_structure['demuxed']),
            'fastqs': str(self.trial_dir / self.dir_structure['fastqs']),
            'nanotel_output': str(self.trial_dir / self.dir_structure['nanotel_output']),
            'aligned': str(self.trial_dir / self.dir_structure['aligned']),
            'r_analysis': str(self.trial_dir / self.dir_structure['r_analysis']),
            'mapping_output': str(self.trial_dir / self.dir_structure['mapping_output']),
            'methylation_output': str(self.trial_dir / self.dir_structure['methylation_output']),
            'logs': str(self.trial_dir / self.dir_structure['logs'])
        }

    def __repr__(self) -> str:
        """String representation of PathManager."""
        return f"PathManager(trial_name={self.trial_name}, trial_dir={self.trial_dir})"