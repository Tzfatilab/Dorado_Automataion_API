"""Validated, atomic user-profile storage, separate from packaged defaults."""
import copy
import json
import os
import re
import tempfile
from pathlib import Path

from dorado_workflow.managers.config_manager import ConfigManager
from dorado_workflow.utils.analysis_validation import validate_nanotel_settings


def canonical_patterns(config=None):
    motif = (config or {}).get("nanotel", {}).get("telomere_pattern", "CCCTAA").upper()
    return {motif, motif.translate(str.maketrans("ACGT", "TGCA"))[::-1]}


def local_paths(paths, defaults):
    """Resolve bundled resources locally and recover unavailable folder defaults."""
    result = merge_config(defaults, paths)
    package = Path(__file__).resolve().parents[2] / "dorado_workflow"
    for key in ("default_input_base", "default_output_base"):
        value = Path(result.get(key, "~")).expanduser()
        result[key] = str(value.absolute() if value.is_dir() else Path.home())
    for key in ("dorado_model", "nanotel_script"):
        value = Path(result[key]).expanduser()
        if not value.is_absolute():
            value = package / value
        if not value.exists():
            value = package / defaults[key]
        result[key] = str(value.resolve())
    for org, path in result["references"].items():
        value = Path(path).expanduser()
        if not value.is_absolute():
            value = package / value
        if not value.exists():
            value = package / defaults["references"][org]
        result["references"][org] = str(value.resolve())
    return result


def remove_legacy_canonical(config):
    forbidden = canonical_patterns(config)
    for section in [config["nanotel"], *config["organism_specific"].values()]:
        if isinstance(section.get("tvr_patterns"), list):
            section["tvr_patterns"] = [p for p in section["tvr_patterns"] if p not in forbidden]


def parse_patterns(text, canonical=None):
    patterns = list(dict.fromkeys(re.split(r"[\s,;]+", text.strip().upper())))
    patterns = [pattern for pattern in patterns if pattern]
    if any(not re.fullmatch(r"[ACGT]+", pattern) for pattern in patterns):
        raise ValueError("Sequences may contain only A, C, G and T.")
    if any(len(pattern) < 5 for pattern in patterns):
        raise ValueError("Each TVR sequence must contain at least 5 bases.")
    if set(patterns) & (canonical or canonical_patterns()):
        raise ValueError("Canonical telomere repeats (including the reverse complement) cannot be added as TVRs.")
    return patterns


def merge_config(defaults, supplied):
    """Merge a partial imported config while rejecting incompatible types."""
    if not isinstance(supplied, dict):
        raise ValueError("Configuration must be a JSON object.")
    result = copy.deepcopy(defaults)
    for key, value in supplied.items():
        if isinstance(result.get(key), dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def validate_config(config):
    validate_nanotel_settings(config["nanotel"])
    analysis_sections = [config["nanotel"]]
    if not config["demuxing"].get("kit_name"):
        raise ValueError("A demultiplexing kit ID is required.")
    for section in ("basecalling", "demuxing"):
        kit = config[section].get("kit_name")
        if kit is not None and (not isinstance(kit, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", kit)):
            raise ValueError("Kit IDs must contain letters, numbers, dots, underscores or hyphens.")
    qscore = config["basecalling"].get("min_qscore")
    if isinstance(qscore, bool) or not isinstance(qscore, int) or not 0 <= qscore <= 50:
        raise ValueError("Minimum quality score must be an integer from 0 to 50.")
    for key in ("telomere_pattern", "tsq1_pattern"):
        value = config["nanotel"].get(key)
        if not isinstance(value, str) or not re.fullmatch(r"[ACGT]+", value):
            raise ValueError(f"{key} must be a nonempty A/C/G/T sequence.")
    pattern_lists = [config["nanotel"].get("tvr_patterns", [])]
    organisms = config["organism_specific"]
    for organism in ("mouse", "human", "zebrafish"):
        if not isinstance(organisms.get(organism), dict):
            raise ValueError(f"Missing organism preset: {organism}")
        analysis = organisms[organism].get("nanotel", {})
        if not isinstance(analysis, dict):
            raise ValueError(f"Analysis defaults for {organism} must be an object.")
        validate_nanotel_settings(analysis)
        analysis_sections.append(analysis)
        pattern_lists.append(organisms[organism].get("tvr_patterns", []))
        reference = config["paths"]["references"].get(organism)
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError(f"A reference path is required for {organism}.")
    # Qt integer editors cannot represent values above a signed 32-bit integer.
    # Reject such imports before loading widgets instead of overflowing or clamping.
    for analysis in analysis_sections:
        for key in ("min_read_length", "short_telomere_threshold_bp", "display_max_edge_distance", "max_telomere_start"):
            value = analysis.get(key)
            if value is not None and value > 2_147_483_647:
                raise ValueError(f"{key} must not exceed 2147483647.")
    for patterns in pattern_lists:
        if isinstance(patterns, list) and any(p in canonical_patterns(config) for p in patterns if isinstance(p, str)):
            raise ValueError("Canonical telomere repeats cannot be included in TVR presets.")
        if not isinstance(patterns, list) or any(
            not isinstance(p, str) or not re.fullmatch(r"[ACGT]+", p) for p in patterns
        ):
            raise ValueError("TVR presets must be lists of A/C/G/T sequences.")
        if len(set(patterns)) != len(patterns):
            raise ValueError("TVR presets must not contain duplicate sequences.")
        if any(len(pattern) < 5 for pattern in patterns):
            raise ValueError("Each TVR sequence must contain at least 5 bases.")
    for key in ("dorado_model", "nanotel_script", "default_input_base", "default_output_base"):
        value = config["paths"].get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"A nonempty path is required for {key}.")
    if config["lab_info"].get("default_organism") not in ("mouse", "human", "zebrafish"):
        raise ValueError("Select a supported default organism.")
    if config["logging"].get("log_level") not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("Invalid logging level.")


def write_json(path, data):
    """Replace only after the complete document has been flushed to disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


class SettingsStore:
    def __init__(self, path):
        self.path = Path(path)
        self.defaults = copy.deepcopy(ConfigManager().config)
        self.defaults["paths"] = local_paths(self.defaults["paths"], self.defaults["paths"])
        remove_legacy_canonical(self.defaults)
        self.profiles = {"Lab default": copy.deepcopy(self.defaults)}
        self.active = "Lab default"
        self.load_error = None
        self.app_paths = copy.deepcopy(self.defaults["paths"])
        self.path_overrides = {}
        if self.path.exists():
            try:
                document = json.loads(self.path.read_text(encoding="utf-8"))
                if document.get("version") not in (1, 2) or not isinstance(document.get("profiles"), dict):
                    raise ValueError("Unsupported settings file format.")
                profiles = {}
                for name, data in document["profiles"].items():
                    self.validate_name(name)
                    config = merge_config(self.defaults, data)
                    remove_legacy_canonical(config)
                    config["paths"] = local_paths(config["paths"], self.defaults["paths"])
                    validate_config(config)
                    profiles[name] = config
                if document.get("active") not in profiles:
                    raise ValueError("The active profile is missing.")
                active = document["active"]
                app_paths = copy.deepcopy(document.get("app_paths", profiles[active]["paths"]))
                app_paths = local_paths(app_paths, self.defaults["paths"])
                probe = copy.deepcopy(self.defaults)
                probe["paths"] = app_paths
                validate_config(probe)
                if document.get("version") == 1:
                    # Preserve old profiles that intentionally used different resources.
                    overrides = {name: copy.deepcopy(c["paths"]) for name, c in profiles.items()
                                 if c["paths"] != app_paths}
                else:
                    overrides = document.get("path_overrides", {})
                    if not isinstance(overrides, dict):
                        raise ValueError("Invalid profile path overrides.")
                    for name, paths in overrides.items():
                        if name not in profiles:
                            raise ValueError("Path overrides reference an unknown profile.")
                        paths = local_paths(paths, self.defaults["paths"])
                        overrides[name] = paths
                        probe["paths"] = paths
                        validate_config(probe)
                self.profiles, self.active = profiles, active
                self.app_paths, self.path_overrides = app_paths, copy.deepcopy(overrides)
                self._refresh_paths()
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                self.load_error = f"Could not load saved profiles: {exc}\nDefaults are shown. The existing file has not been changed."

    @staticmethod
    def validate_name(name):
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise ValueError("Profile names must contain 1–80 characters.")

    def snapshot(self):
        return copy.deepcopy(self.profiles[self.active])

    def _refresh_paths(self):
        """Keep exported/run configurations complete while sharing resource defaults."""
        for name, config in self.profiles.items():
            config["paths"] = copy.deepcopy(self.path_overrides.get(name, self.app_paths))

    def _document(self, profiles, active, app_paths, overrides):
        return {"version": 2, "active": active, "profiles": profiles,
                "app_paths": app_paths, "path_overrides": overrides}

    def save_app_paths(self, paths):
        """Save shared resources without changing analysis profiles or custom paths."""
        probe = copy.deepcopy(self.defaults)
        paths = copy.deepcopy(paths)
        for key in ("default_input_base", "default_output_base"):
            folder = Path(paths.get(key, "")).expanduser()
            if not paths.get(key, "").strip() or not folder.is_dir():
                raise ValueError(f"Choose an existing folder for {key.replace('_', ' ')}.")
            paths[key] = str(folder.resolve())
        probe["paths"] = copy.deepcopy(paths)
        validate_config(probe)
        profiles = copy.deepcopy(self.profiles)
        for name, config in profiles.items():
            config["paths"] = copy.deepcopy(self.path_overrides.get(name, paths))
        self._backup_unreadable()
        write_json(self.path, self._document(profiles, self.active, paths, self.path_overrides))
        self.profiles, self.app_paths = profiles, copy.deepcopy(paths)
        self.load_error = None

    def delete(self, name):
        """Persist deletion before changing the active in-memory configuration."""
        if name == "Lab default":
            raise ValueError("The default profile cannot be deleted.")
        if name not in self.profiles:
            raise ValueError("This profile has not been saved.")
        profiles = copy.deepcopy(self.profiles)
        del profiles[name]
        profiles.setdefault("Lab default", copy.deepcopy(self.defaults))
        active = "Lab default" if self.active == name else self.active
        overrides = copy.deepcopy(self.path_overrides)
        overrides.pop(name, None)
        profiles["Lab default"]["paths"] = copy.deepcopy(overrides.get("Lab default", self.app_paths))
        write_json(self.path, self._document(profiles, active, self.app_paths, overrides))
        self.profiles, self.active = profiles, active
        self.path_overrides = overrides

    def commit(self, name, config):
        self.validate_name(name)
        validate_config(config)
        profiles = copy.deepcopy(self.profiles)
        profiles[name] = copy.deepcopy(config)
        overrides = copy.deepcopy(self.path_overrides)
        if config["paths"] != self.app_paths:
            overrides[name] = copy.deepcopy(config["paths"])
        else:
            overrides.pop(name, None)
        self._backup_unreadable()
        write_json(self.path, self._document(profiles, name, self.app_paths, overrides))
        self.profiles, self.active, self.load_error = profiles, name, None
        self.path_overrides = overrides

    def _backup_unreadable(self):
        """Keep the existing recovery copy before either kind of settings save."""
        # Preserve an unreadable file before an explicit Save replaces it.
        if self.load_error and self.path.exists():
            backup = self.path.with_name(self.path.name + ".bak")
            if backup.exists():
                raise ValueError(f"Saved settings could not be loaded. Recover {self.path} first; a backup already exists at {backup}.")
            backup.write_bytes(self.path.read_bytes())
