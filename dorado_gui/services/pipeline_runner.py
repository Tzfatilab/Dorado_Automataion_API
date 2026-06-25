import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
dorado_workflow_path = project_root / "dorado_workflow"
sys.path.insert(0, str(dorado_workflow_path))
sys.path.insert(0, str(project_root))

from dorado_workflow.main import setup_context
from dorado_workflow.operators.workflow_operator import WorkflowOperator

APP_OUTPUT_FOLDER = "Telomere Analyzer"


def _log_banner(log, title: str, subtitle=None) -> None:
    """Write a consistent, easy-to-scan stage banner to the GUI log."""
    log(title.capitalize())
    if subtitle:
        log(subtitle)


"""Pipeline entrypoint used by the GUI and worker thread.

This function can start from different input stages (POD5, FASTQ, BAM) and only executes steps enabled by the boolean flags.

Args:
    trial_name: Optional trial label. The current implementation infers the
        effective trial name from output_dir.
    pod5_path: Directory containing POD5 files.
    fastq_path: Directory containing FASTQ files.
    bam_path: Directory containing BAM files.
    output_dir: Base output directory, or an existing trial directory.
    organism: Target organism name (mouse, human, or fish).
    do_basecalling: Run basecalling step.
    do_nanotel: Run NanoTel analysis step.
    log_cb: Optional callback used for log messages.
    run_filtration: Enable filtration in R analysis.
    run_mapping: Enable mapping in R analysis.
    run_methylation: Enable methylation analysis in R analysis.
    stop_cb: Optional cancellation callback for future use.

Returns:
    Tuple of (status_code, message):
    - (0, message): Workflow finished successfully.
    - (1, message): Validation or execution failed.
"""


def run_pipeline(
        *,
        trial_name: str = None,
        pod5_path: str = "",
        fastq_path: str = "",
        bam_path: str = "",
        output_dir: str,
        organism: str,
        do_basecalling: bool,
        do_nanotel: bool,
        non_pod5_trim_status: str = "auto",
        methylation_type: str = "None",
        chromosome_mapping: bool = False,
        tvr_mode: str = "Use preset",
        tvr_manual: str = "",
        read_length: str = "",
        max_distance_edge: str = "134",
        min_density_threshold: str = "0.75",
        log_cb=None,
        stop_cb=None
) -> tuple[int, str]:
    # Orchestrate the pipeline run based on user-selected workflow steps.
    # Validates input paths, sets up the workflow context, applies overrides,
    # and routes execution to the appropriate sub-workflow.
    run_started_at = time.monotonic()
    def log(msg: str):
        # Relay log messages to the optional callback.
        if log_cb:
            log_cb(msg)

    def check_cancelled():
        # Stop execution early if the GUI requested cancellation.
        if stop_cb and stop_cb():
            raise RuntimeError("Cancelled by user")

    check_cancelled()
    _log_banner(log, "SETTING UP WORKFLOW", "Preparing paths, settings, and tools")

    output_path = Path(output_dir)

    # Detect whether output_dir points to the selected output root, an existing
    # Telomere Analyzer folder, or one of its processing/results subfolders.
    group_dirs = {'processing', 'results'}
    legacy_group_dirs = {'raw_data'}
    leaf_subdirs = {
        'basecalled', 'demultiplexed', 'fastq', 'nanotel', 'mapping',
        'methylation', 'aligned', 'logs',
    }
    legacy_subdirs = {
        'nanotel_output', 'aligned', 'logs', 'fastqs', 'demuxed',
        'rebasecalled', 'r_analysis',
    }
    trial_markers = group_dirs | legacy_group_dirs | legacy_subdirs
    is_trial_folder = any((output_path / subdir).exists() for subdir in trial_markers)
    is_trial_group = output_path.name in group_dirs or output_path.name in legacy_group_dirs
    is_nested_subdir = (
        output_path.name in leaf_subdirs
        and output_path.parent.name in (group_dirs | legacy_group_dirs)
    )
    is_legacy_subdir = output_path.name in legacy_subdirs

    actual_trial = APP_OUTPUT_FOLDER
    if output_path.name == APP_OUTPUT_FOLDER:
        base_dir = str(output_path.parent)
    elif is_nested_subdir:
        trial_root = output_path.parent.parent
        if trial_root.name == APP_OUTPUT_FOLDER:
            base_dir = str(trial_root.parent)
        else:
            base_dir = str(trial_root)
    elif is_trial_group or is_legacy_subdir:
        trial_root = output_path.parent
        if trial_root.name == APP_OUTPUT_FOLDER:
            base_dir = str(trial_root.parent)
        else:
            base_dir = str(trial_root)
    else:
        base_dir = str(output_path)

    context = setup_context(
        trial_name=actual_trial,
        base_output_dir=base_dir,
        config_path=None,
        organism=organism,
        log_callback=log,
    )
    log(f"Results will be saved under: {context.path_manager.get_results_dir_path()}")
    has_methylation = str(methylation_type or "").strip().lower() != "none"
    align_during_basecalling = chromosome_mapping
    basecalling_overrides = _build_basecalling_overrides(methylation_type)
    if basecalling_overrides:
        context.config_manager.update_basecalling_params(basecalling_overrides)

    # Adjust NanoTel settings based on the GUI advanced options.
    if trim_hint := (non_pod5_trim_status if non_pod5_trim_status in {"trimmed", "untrimmed"} else None):
        if trim_hint == "trimmed" and str(max_distance_edge).strip() == "134":
            max_distance_edge = "50"

    nanotel_overrides = _build_nanotel_overrides(
        context.config_manager,
        organism=organism,
        tvr_mode=tvr_mode,
        tvr_manual=tvr_manual,
        read_length=read_length,
        max_distance_edge=max_distance_edge,
        min_density_threshold=min_density_threshold,
    )
    if nanotel_overrides:
        context.config_manager.update_nanotel_params(nanotel_overrides)

    operator = WorkflowOperator(context=context)
    res = 0
    if do_basecalling and do_nanotel:
        res = _run_full_pipeline(operator, context, pod5_path, organism, log, check_cancelled, has_methylation, align_during_basecalling)
    elif do_basecalling:
        res = _run_basecalling_only(
            operator,
            pod5_path,
            organism,
            log,
            check_cancelled,
            align_during_basecalling
        )
    elif do_nanotel:
        res = _run_nanotel_only(operator, fastq_path, bam_path, organism, log, check_cancelled, has_methylation)
    else:
        return (1, "No workflow selected")

    check_cancelled()
    if res:
        elapsed_seconds = time.monotonic() - run_started_at
        log("PIPELINE COMPLETED SUCCESSFULLY")
        log(f"Total run time: {elapsed_seconds:.1f}s")
        log(f"Results: {context.path_manager.get_results_dir_path()}")
        return (0, "Workflow completed successfully")
        log("✅ PIPELINE COMPLETED SUCCESSFULLY")
        return (0, "Workflow completed successfully")
    else:
        log("❌ PIPELINE FAILED")
        return (1, "Pipeline execution failed")


def _run_basecalling_only(operator, pod5_path, organism, log, check_cancelled, align_during_basecalling: bool = False):
    # Execute only the basecalling workflow.
    check_cancelled()

    if not pod5_path:
        msg = "POD5 Workflow selected but no POD5 path provided."
        log(f"❌ {msg}")
        return 1

    return operator.run_basecalling(
        pod5_path,
        organism=organism,
        align_during_basecalling=align_during_basecalling
    )


def _run_nanotel_only(operator, fastq_path, bam_path, organism, log, check_cancelled, has_methylation: bool = False):
    # Run only the NanoTel analysis, choosing FASTQ or BAM mode as needed.
    check_cancelled()

    if fastq_path:
        return operator.run_nanotel_workflow(fastq_path, organism=organism, align=True, has_methylation=has_methylation)

    if bam_path:
        return operator.run_nanotel_workflow(bam_path, organism=organism, align=True, has_methylation=has_methylation)

    msg = "FASTQ/BAM input required for NanoTel."
    log(f"❌ {msg}")
    return 1


def _build_basecalling_overrides(methylation_type: str) -> dict:
    # Convert GUI methylation selection into Dorado basecalling config overrides.
    mode = (methylation_type or "").strip().lower()

    if mode == "none":
        return {"modified_bases": ""}

    if mode == "5mcpg":
        return {"modified_bases": "5mCG"}

    if mode == "5mcpg + 5hmcpg":
        return {"modified_bases": "5mCG_5hmCG"}

    return {}


def _build_nanotel_overrides(
        config_manager,
        *,
        organism: str,
        tvr_mode: str,
        tvr_manual: str,
        read_length: str,
        max_distance_edge: str,
        min_density_threshold: str,
) -> dict:
    # Convert GUI NanoTel advanced options into NanoTel parameter overrides.
    overrides = {}

    density = _parse_float(min_density_threshold)
    if density is not None:
        overrides["min_density"] = density
        overrides["density_threshold"] = density

    max_start = _parse_int(max_distance_edge)
    if max_start is not None:
        overrides["max_telomere_start"] = max_start

    read_length_value = _parse_int(read_length)
    if read_length_value is not None:
        overrides["read_length"] = read_length_value

    mode = (tvr_mode or "").strip().lower()
    if mode == "none":
        overrides["tvr_patterns"] = []
    elif mode == "use preset":
        overrides["tvr_patterns"] = config_manager.get_tvr_patterns(organism)
    elif mode == "tsq1":
        overrides["tvr_patterns"] = ["AACCGC"]
    elif mode == "enter manual":
        overrides["tvr_patterns"] = _parse_patterns(tvr_manual)

    return overrides


def _parse_int(value: str):
    # Safely parse an integer from a GUI string field.
    value = str(value or "").strip()
    if not value:
        return None
    return int(value)


def _parse_float(value: str):
    # Safely parse a floating-point value from a GUI string field.
    value = str(value or "").strip()
    if not value:
        return None
    return float(value)


def _parse_patterns(value: str) -> list:
    # Normalize a comma- or semicolon-separated pattern string into a list.
    value = str(value or "").strip()
    if not value:
        return []
    return [
        pattern.strip().upper()
        for pattern in value.replace(";", ",").replace(" ", ",").split(",")
        if pattern.strip()
    ]


def _run_full_pipeline(operator, context, pod5_path, organism, log, check_cancelled, methylation_enabled: bool = False, align_during_basecalling: bool = False):
    # Execute the full POD5 + NanoTel pipeline.
    check_cancelled()

    res = operator.run_pod5_workflow(
        pod5_path,
        organism=organism,
        methylation_enabled=methylation_enabled,
        align_during_basecalling=align_during_basecalling,
    )
    return res
