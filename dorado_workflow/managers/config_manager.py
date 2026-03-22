"""
Config Manager Module
====================

Handles loading, merging, and accessing workflow configuration.
Automatically locates config file in the package's configs directory.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigManager:
    """
    Manages workflow configuration with organism-specific parameter merging.

    Features:
    - Auto-locates config in package's configs/ directory
    - Dynamic organism switching with parameter merging
    - Helper methods for easy config access
    - No validation (trust the config is correct)
    """

    # Default config filename
    DEFAULT_CONFIG_NAME = "default_config.json"

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the config manager.

        Args:
            config_path: Optional explicit path to config file.
                        If None, auto-locates in package's configs/ directory.

        Raises:
            FileNotFoundError: If config file not found
            json.JSONDecodeError: If config file is invalid JSON
        """
        if config_path:
            self.config_path = Path(config_path)
        else:
            # Auto-locate config in package's configs/ directory
            self.config_path = self._find_default_config()

        # Load configuration
        self.config = self._load_config()

        # Current organism (can be changed dynamically)
        self._current_organism = self.config.get('lab_info', {}).get('default_organism', 'mouse')

        # Merged config cache (updated when organism changes)
        self._merged_config = None
        self._update_merged_config()

    def _find_default_config(self) -> Path:
        """
        Auto-locate default config file in package's configs/ directory.

        Returns:
            Path to default_config.json

        Raises:
            FileNotFoundError: If config not found with helpful message
        """
        # Get the package root directory (dorado_workflow/)
        # This file is in: dorado_workflow/managers/config_manager.py
        package_root = Path(__file__).parent.parent
        config_path = package_root / "configs" / self.DEFAULT_CONFIG_NAME

        if not config_path.exists():
            error_msg = (
                f"\n{'=' * 80}\n"
                f"Configuration file not found!\n"
                f"{'=' * 80}\n"
                f"Expected location: {config_path}\n\n"
                f"The configuration file must be created before running the workflow.\n"
                f"This file contains lab-specific paths and settings.\n\n"
                f"To create a default configuration file, run:\n"
                f"  python main.py --create-config\n\n"
                f"Then edit the file with your lab's paths:\n"
                f"  - Dorado model path\n"
                f"  - Reference genome paths (mouse/human)\n"
                f"  - NanoTel script path\n"
                f"  - Default output directory\n"
                f"{'=' * 80}\n"
            )
            raise FileNotFoundError(error_msg)

        return config_path

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from JSON file.

        Returns:
            Configuration dictionary

        Raises:
            json.JSONDecodeError: If config file is invalid JSON
        """
        with open(self.config_path, 'r') as f:
            config = json.load(f)

        return config

    # def _update_merged_config(self) -> None:
    #     """
    #     Update merged config by applying organism-specific parameters.
    #
    #     Merges organism-specific parameters into the main config sections.
    #     """
    #     # Start with base config
    #     merged = self.config.copy()
    #
    #     # Get organism-specific overrides
    #     organism_params = self.config.get('organism_specific', {}).get(self._current_organism, {})
    #
    #     # Merge organism-specific parameters into r_analysis sections
    #     if organism_params:
    #         # Deep merge into r_analysis
    #         if 'r_analysis' not in merged:
    #             merged['r_analysis'] = {}
    #
    #         for section, params in organism_params.items():
    #             if section not in merged['r_analysis']:
    #                 merged['r_analysis'][section] = {}
    #             merged['r_analysis'][section].update(params)
    #
    #     self._merged_config = merged

    def _update_merged_config(self) -> None:
        """
        Update merged config by applying organism-specific parameters.

        Merges organism-specific parameters into the main config sections.
        """
        # Start with base config
        merged = self.config.copy()

        # Get organism-specific overrides
        organism_params = self.config.get('organism_specific', {}).get(self._current_organism, {})

        # Merge organism-specific parameters
        if organism_params:
            # Organism-specific params are flat key-value pairs
            # We need to intelligently place them in the right sections

            if 'r_analysis' not in merged:
                merged['r_analysis'] = {}

            # Map of parameter names to their target sections
            param_mapping = {
                'reference_length': 'methylation',
                'tail_min_end': 'mapping',
                'tail_min_pos': 'methylation',
                'head_max_start': 'mapping',
                'head_max_pos': 'methylation'
            }

            for param_name, param_value in organism_params.items():
                # Determine which section this parameter belongs to
                target_section = param_mapping.get(param_name)

                if target_section:
                    # Ensure the section exists
                    if target_section not in merged['r_analysis']:
                        merged['r_analysis'][target_section] = {}

                    # Update the parameter
                    merged['r_analysis'][target_section][param_name] = param_value

        self._merged_config = merged

    # ==================== Organism Management ====================

    def set_organism(self, organism: str) -> None:
        """
        Set the current organism and update merged config.

        Args:
            organism: 'mouse' or 'human'

        Raises:
            ValueError: If organism not found in config
        """
        available_organisms = list(self.config.get('organism_specific', {}).keys())

        if organism not in available_organisms:
            raise ValueError(
                f"Organism '{organism}' not found in config. "
                f"Available: {available_organisms}"
            )

        self._current_organism = organism
        self._update_merged_config()

    def get_current_organism(self) -> str:
        """Get the currently selected organism."""
        return self._current_organism

    # ==================== Path Access Methods ====================

    def get_reference_path(self, organism: Optional[str] = None) -> str:
        """
        Get reference genome path for specified organism.

        Args:
            organism: 'mouse' or 'human'. If None, uses current organism.

        Returns:
            Path to reference genome
        """
        org = organism or self._current_organism
        return self.config['paths']['references'][org]

    def get_dorado_model_path(self) -> str:
        """Get path to Dorado model."""
        return self.config['paths']['dorado_model']

    def get_nanotel_script_path(self) -> str:
        """Get path to NanoTel R script."""
        return self.config['paths']['nanotel_script']

    def get_default_output_base(self) -> str:
        """Get default base output directory."""
        return self.config['paths']['default_output_base']

    # ==================== Stage-Specific Config Access ====================

    def get_basecalling_params(self) -> Dict[str, Any]:
        """Get basecalling parameters."""
        return self.config.get('basecalling', {})

    def get_demuxing_params(self) -> Dict[str, Any]:
        """Get demuxing parameters."""
        return self.config.get('demuxing', {})

    def get_nanotel_params(self) -> Dict[str, Any]:
        """Get NanoTel parameters."""
        return self.config.get('nanotel', {})

    def get_alignment_params(self) -> Dict[str, Any]:
        """Get alignment parameters."""
        return self.config.get('alignment', {})

    def get_r_analysis_params(self) -> Dict[str, Any]:
        """
        Get R analysis parameters with organism-specific merging applied.

        Returns:
            Merged R analysis parameters for current organism
        """
        return self._merged_config.get('r_analysis', {})

    # def get_r_nanotel_params(self) -> Dict[str, Any]:
    #     """Get R NanoTel analysis parameters."""
    #     return self.get_r_analysis_params().get('nanotel', {})

    def get_r_mapping_params(self) -> Dict[str, Any]:
        """Get R mapping analysis parameters (with organism-specific merging)."""
        return self.get_r_analysis_params().get('mapping', {})

    def get_r_methylation_params(self) -> Dict[str, Any]:
        """Get R methylation analysis parameters (with organism-specific merging)."""
        return self.get_r_analysis_params().get('methylation', {})

    # ==================== General Config Access ====================

    def get_processing_options(self) -> Dict[str, Any]:
        """Get processing options."""
        return self.config.get('processing_options', {})

    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self.config.get('logging', {})

    def get_directory_structure(self) -> Dict[str, str]:
        """Get directory structure naming conventions."""
        return self.config.get('directory_structure', {})

    def get_lab_info(self) -> Dict[str, Any]:
        """Get lab information."""
        return self.config.get('lab_info', {})

    # ==================== Utility Methods ====================

    def get_config_dict(self) -> Dict[str, Any]:
        """
        Get the complete merged configuration dictionary.
        Includes organism-specific parameters merged in.

        Returns:
            Complete merged config
        """
        return self._merged_config.copy()

    def save_config(self, output_path: Path) -> None:
        """
        Save current configuration to a file.
        Useful for creating run-specific config records.

        Args:
            output_path: Path where config should be saved
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(self._merged_config, f, indent=2)

    def __repr__(self) -> str:
        """String representation of ConfigManager."""
        return (
            f"ConfigManager("
            f"config_path={self.config_path}, "
            f"organism={self._current_organism})"
        )