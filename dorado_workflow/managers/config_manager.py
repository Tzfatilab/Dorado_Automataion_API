"""
Config Manager Module
====================

Handles loading, merging, and accessing workflow configuration.
Automatically locates config file in the package's configs directory.
"""

import json
from copy import deepcopy
from pathlib import Path
from typing import Dict, Any, Optional
from ..utils.analysis_validation import validate_nanotel_settings


def organism_nanotel_settings(config, organism):
    """Resolve organism analysis defaults with legacy profile-wide fallback.

    Args:
        config: Configuration values to read or update.
        organism: Organism label selecting reference and analysis defaults.

    Returns:
        Independent NanoTel settings with organism defaults applied.
    """
    organism = str(organism).strip().lower()
    if organism in {"fish", "zebra fish", "zabra fish"}:
        organism = "zebrafish"
    settings = deepcopy(config.get("nanotel", {}))
    settings.update(config.get("organism_specific", {}).get(organism, {}).get("nanotel", {}))
    return settings

class ConfigManager:
    """
    Manages workflow configuration with organism-specific parameter merging.

    Features:
    - Auto-locates config in package's configs/ directory
    - Dynamic organism switching with parameter merging
    - Helper methods for easy config access
    - Validate supplied NanoTel numerical settings without changing defaults
    """

    # Default config filename
    DEFAULT_CONFIG_NAME = "default_config.json"

    def __init__(self, config_path: Optional[Path] = None, config_data: Optional[Dict[str, Any]] = None):
        """Initialize the config manager.

        Args:
            config_path: Optional explicit path to config file.
                        If None, auto-locates in package's configs/ directory.
            config_data: Optional[Dict[str, Any]]; configuration snapshot supplied for this run. Default: None.

        Raises:
            FileNotFoundError: If config file not found
            json.JSONDecodeError: If config file is invalid JSON

        Returns:
            None; initializes the instance.
        """
        if config_path:
            self.config_path = Path(config_path)
        else:
            # Auto-locate config in package's configs/ directory
            self.config_path = self._find_default_config()

        # Load configuration
        self.config = deepcopy(config_data) if config_data is not None else self._load_config()
        self._nanotel_run_overrides = {}
        if not isinstance(self.config, dict):
            raise ValueError(f"Configuration must be a JSON object: {self.config_path}")
        if not isinstance(self.config.get('nanotel', {}), dict):
            raise ValueError("Configuration section 'nanotel' must be a JSON object")
        validate_nanotel_settings(self.config.get('nanotel', {}))

        # Current organism (can be changed dynamically)
        self._current_organism = self.config.get('lab_info', {}).get('default_organism', 'mouse')

        # Merged config cache (updated when organism changes)
        self._merged_config = None
        self._update_merged_config()

    def _find_default_config(self) -> Path:
        """Auto-locate default config file in package's configs/ directory.

        Returns:
            Path to default_config.json

        Raises:
            FileNotFoundError: If config not found with helpful message

        Inputs:
            None; uses instance state.
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
                f"Restore configs/default_config.json from the repository or reinstall the package.\n\n"
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
        """Load configuration from JSON file.

        Returns:
            Configuration dictionary

        Raises:
            json.JSONDecodeError: If config file is invalid JSON

        Inputs:
            None; uses instance state.
        """
        with open(self.config_path, 'r') as f:
            config = json.load(f)

        return config

    def _update_merged_config(self) -> None:
        """Update merged config by applying organism-specific parameters.

        Merges organism-specific parameters into the main config sections.

        Inputs:
            None; uses instance state.

        Returns:
            None.
        """
        # Isolate effective run settings from the saved profile and its presets.
        merged = deepcopy(self.config)

        # Get organism-specific overrides
        organism_params = self.config.get('organism_specific', {}).get(self._current_organism, {})

        # Merge organism-specific parameters
        if organism_params:
            # Legacy organism presets store mapping/methylation overrides flat;
            # route only recognized keys to their nested analysis sections.

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

        merged["nanotel"] = organism_nanotel_settings(self.config, self._current_organism)
        # Explicit run choices take precedence over organism defaults.
        merged["nanotel"].update(self._nanotel_run_overrides)
        validate_nanotel_settings(merged["nanotel"])
        self._merged_config = merged

    # ==================== Organism Management ====================

    def _normalize_organism(self, organism: str) -> str:
        """Normalize common organism labels to config keys.

        Args:
            organism: str; organism label selecting reference and analysis defaults.

        Returns:
            Normalized organism key used by the configuration.
        """
        if organism is None:
            return self._current_organism

        normalized = str(organism).strip().lower()
        if normalized in {"fish", "zabra fish", "zebra fish", "zebrafish"}:
            return "zebrafish"
        return normalized

    def set_organism(self, organism: str) -> None:
        """Set the current organism and update merged config.

        Args:
            organism: organism key or alias such as 'mouse', 'human', or 'fish'

        Raises:
            ValueError: If organism not found in config

        Returns:
            None.
        """
        organism = self._normalize_organism(organism)
        available_organisms = list(self.config.get('organism_specific', {}).keys())

        if organism not in available_organisms:
            raise ValueError(
                f"Organism '{organism}' not found in config. "
                f"Available: {available_organisms}"
            )

        self._current_organism = organism
        self._update_merged_config()

    def get_current_organism(self) -> str:
        """Get the currently selected organism.

        Inputs:
            None; uses instance state.

        Returns:
            Current organism key.
        """
        return self._current_organism

    # ==================== Path Access Methods ====================

    def get_reference_path(self, organism: Optional[str] = None) -> str:
        """
        Get reference genome path for specified organism.

        Args:
            organism: organism label or alias. If None, uses current organism.

        Returns:
            Path to reference genome
        """
        org = self._normalize_organism(organism or self._current_organism)
        return self._resolve_path(self.config['paths']['references'][org])

    def get_dorado_model_path(self) -> str:
        """Get path to Dorado model.

        Inputs:
            None; uses instance state.

        Returns:
            Resolved Dorado model path as a string.
        """
        return  self._resolve_path(self.config['paths']['dorado_model'])

    def get_nanotel_script_path(self) -> str:
        """Get path to NanoTel R script.

        Inputs:
            None; uses instance state.

        Returns:
            Resolved NanoTel R script path as a string.
        """
        return  self._resolve_path(self.config['paths']['nanotel_script'])

    def get_default_output_base(self) -> str:
        """Get default base output directory path without creating it.

        Inputs:
            None; uses instance state.

        Returns:
            Resolved default output-directory path as a string.
        """
        base = Path(self._resolve_path(self.config['paths']['default_output_base']))
        return str(base)

    # ==================== Stage-Specific Config Access ====================

    def get_basecalling_params(self) -> Dict[str, Any]:
        """Get basecalling parameters.

        Inputs:
            None; uses instance state.

        Returns:
            Dict[str, Any]: Selected stored value, or the supplied fallback when absent.
        """
        return self.config.get('basecalling', {})

    def update_basecalling_params(self, params: Dict[str, Any]) -> None:
        """Apply run-specific basecalling parameter overrides.

        Args:
            params: Dict[str, Any]; parameter values for this operation.

        Returns:
            None.
        """
        if not params:
            return

        if 'basecalling' not in self.config:
            self.config['basecalling'] = {}

        self.config['basecalling'].update(params)
        self._update_merged_config()

    def get_demuxing_params(self) -> Dict[str, Any]:
        """Get demuxing parameters.

        Inputs:
            None; uses instance state.

        Returns:
            Dict[str, Any]: Selected stored value, or the supplied fallback when absent.
        """
        return self.config.get('demuxing', {})

    def get_nanotel_params(self) -> Dict[str, Any]:
        """Get organism defaults overlaid with explicit settings for this run.

        Inputs:
            None; uses instance state.

        Returns:
            Dict[str, Any]: Selected stored value, or the supplied fallback when absent.
        """
        return self._merged_config.get('nanotel', {})

    def update_nanotel_params(self, params: Dict[str, Any]) -> None:
        """Apply run-specific NanoTel parameter overrides.

        Args:
            params: Dict[str, Any]; parameter values for this operation.

        Returns:
            None.
        """
        if not params:
            return

        validate_nanotel_settings(params)

        if 'nanotel' not in self.config:
            self.config['nanotel'] = {}

        self.config['nanotel'].update(params)
        self._nanotel_run_overrides.update(params)
        self._update_merged_config()

    def get_tvr_patterns(self, organism: Optional[str] = None) -> list:
        """Get TVR patterns configured for NanoTel/R analysis.

        Args:
            organism: Optional[str]; organism label selecting reference and analysis defaults. Default: None.

        Returns:
            Configured TVR motif list for the selected organism.
        """
        org = self._normalize_organism(organism or self._current_organism)
        organism_config = self.config.get('organism_specific', {}).get(org, {})
        if 'tvr_patterns' in organism_config:
            return organism_config.get('tvr_patterns', [])
        return self.config.get('nanotel', {}).get('tvr_patterns', [])

    def get_tsq1_pattern(self) -> str:
        """Get the TSQ1 pattern from the NanoTel configuration.

        Inputs:
            None; uses instance state.

        Returns:
            Configured TSQ1 motif string.
        """
        return self.config.get('nanotel', {}).get('tsq1_pattern', 'AACCGC')

    def get_alignment_params(self) -> Dict[str, Any]:
        """Get alignment parameters.

        Inputs:
            None; uses instance state.

        Returns:
            Dict[str, Any]: Selected stored value, or the supplied fallback when absent.
        """
        return self.config.get('alignment', {})

    def get_r_analysis_params(self) -> Dict[str, Any]:
        """Get R analysis parameters with organism-specific merging applied.

        Returns:
            Merged R analysis parameters for current organism

        Inputs:
            None; uses instance state.
        """
        return self._merged_config.get('r_analysis', {})

    # def get_r_nanotel_params(self) -> Dict[str, Any]:
    #     """Get R NanoTel analysis parameters."""
    #     return self.get_r_analysis_params().get('nanotel', {})

    def get_r_mapping_params(self) -> Dict[str, Any]:
        """Get R mapping analysis parameters (with organism-specific merging).

        Inputs:
            None; uses instance state.

        Returns:
            Dict[str, Any]: Selected stored value, or the supplied fallback when absent.
        """
        return self.get_r_analysis_params().get('mapping', {})

    def get_r_methylation_params(self) -> Dict[str, Any]:
        """Get R methylation analysis parameters (with organism-specific merging).

        Inputs:
            None; uses instance state.

        Returns:
            Dict[str, Any]: Selected stored value, or the supplied fallback when absent.
        """
        return self.get_r_analysis_params().get('methylation', {})

    # ==================== General Config Access ====================

    def get_processing_options(self) -> Dict[str, Any]:
        """Get processing options.

        Inputs:
            None; uses instance state.

        Returns:
            Dict[str, Any]: Selected stored value, or the supplied fallback when absent.
        """
        return self.config.get('processing_options', {})

    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration.

        Inputs:
            None; uses instance state.

        Returns:
            Dict[str, Any]: Selected stored value, or the supplied fallback when absent.
        """
        return self.config.get('logging', {})

    def get_directory_structure(self) -> Dict[str, str]:
        """Get directory structure naming conventions.

        Inputs:
            None; uses instance state.

        Returns:
            Dict[str, str]: Selected stored value, or the supplied fallback when absent.
        """
        return self.config.get('directory_structure', {})

    def get_lab_info(self) -> Dict[str, Any]:
        """Get lab information.

        Inputs:
            None; uses instance state.

        Returns:
            Dict[str, Any]: Selected stored value, or the supplied fallback when absent.
        """
        return self.config.get('lab_info', {})

    # ==================== Utility Methods ====================

    def get_config_dict(self) -> Dict[str, Any]:
        """Get the complete merged configuration dictionary.
        Includes organism-specific parameters merged in.

        Returns:
            Complete merged config

        Inputs:
            None; uses instance state.
        """
        return self._merged_config.copy()

    def save_config(self, output_path: Path) -> None:
        """Save current configuration to a file.
        Useful for creating run-specific config records.

        Args:
            output_path: Path where config should be saved

        Returns:
            None.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(self._merged_config, f, indent=2)

    @property
    def package_root(self) -> Path:
        """Root of the dorado_workflow package (parent of configs/, data/, etc.).

        Inputs:
            None; uses instance state.

        Returns:
            Path to the installed workflow package directory.
        """
        return Path(__file__).parent.parent

    def _resolve_path(self, path_str: str) -> str:
        """Resolve a config path against the package root.
        Absolute paths are returned unchanged; relative paths are
        resolved relative to the package, not the current directory.

        Args:
            path_str: str; path text to expand and resolve.

        Returns:
            str: Text representation of the value.
        """
        p = Path(path_str).expanduser()
        if p.is_absolute():
            return str(p)
        return str((self.package_root / p).resolve())

    def __repr__(self) -> str:
        """String representation of ConfigManager.

        Inputs:
            None; uses instance state.

        Returns:
            Readable string describing the instance.
        """
        return (
            f"ConfigManager("
            f"config_path={self.config_path}, "
            f"organism={self._current_organism})"
        )
