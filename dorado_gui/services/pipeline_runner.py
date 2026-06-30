"""GUI pipeline runner.

This module is the thin adapter between the Qt GUI and the workflow package.
It translates GUI state into workflow flags, applies user-configured overrides,
and routes execution to the correct high-level workflow method.
"""

import sys
import time
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
dorado_workflow_path = project_root / "dorado_workflow"
sys.path.insert(0, str(dorado_workflow_path))
sys.path.insert(0, str(project_root))

from dorado_workflow.main import setup_context
from dorado_workflow.operators.workflow_operator import WorkflowOperator

APP_OUTPUT_FOLDER = "Telomere Analyzer"


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
        bam_is_aligned=None,
        bam_has_modifications=None,
        methylation_type: str = "None",
        chromosome_mapping: bool = False,
        nanotel_mapping: bool = False,
        summary_only: bool = False,
        tvr_mode: str = "Use preset",
        tvr_manual: str = "",
        read_length: str = "",
        max_distance_edge: str = "134",
        min_density_threshold: str = "0.75",
        log_cb=None,
        stop_cb=None
) -> tuple[int, str]:
    """Run the selected workflow and return a WorkerThread status tuple."""
    run_started_at = time.monotonic()
    log = _make_log_callback(log_cb)
    check_cancelled = _make_cancel_checker(stop_cb)

    check_cancelled()
    _log_banner(log, "SETTING UP WORKFLOW", "Preparing paths, settings, and tools")

    analysis_flags = _derive_analysis_flags(
        bam_path=bam_path,
        bam_is_aligned=bam_is_aligned,
        bam_has_modifications=bam_has_modifications,
        methylation_type=methylation_type,
        chromosome_mapping=chromosome_mapping,
        nanotel_mapping=nanotel_mapping,
    )
    context = _setup_pipeline_context(
        output_dir=output_dir,
        organism=organism,
        log=log,
        do_basecalling=do_basecalling,
        do_nanotel=do_nanotel,
        bam_path=bam_path,
        nanotel_mapping=analysis_flags["nanotel_mapping"],
        align_during_basecalling=analysis_flags["align_during_basecalling"],
    )

    _apply_gui_config_overrides(
        context,
        organism=organism,
        methylation_type=methylation_type,
        non_pod5_trim_status=non_pod5_trim_status,
        summary_only=summary_only,
        tvr_mode=tvr_mode,
        tvr_manual=tvr_manual,
        read_length=read_length,
        max_distance_edge=max_distance_edge,
        min_density_threshold=min_density_threshold,
    )

    operator = WorkflowOperator(context=context)
    _log_bam_state(log, bam_path, bam_is_aligned, bam_has_modifications)

    result = _dispatch_workflow(
        operator=operator,
        context=context,
        pod5_path=pod5_path,
        fastq_path=fastq_path,
        bam_path=bam_path,
        organism=organism,
        do_basecalling=do_basecalling,
        do_nanotel=do_nanotel,
        log=log,
        check_cancelled=check_cancelled,
        has_methylation=analysis_flags["has_methylation"],
        align_during_basecalling=analysis_flags["align_during_basecalling"],
        nanotel_mapping=analysis_flags["nanotel_mapping"],
        bam_is_aligned=bam_is_aligned,
    )
    if result is None:
        return (1, "No workflow selected")

    check_cancelled()
    return _finish_pipeline_run(result, run_started_at, context, log)


def _make_log_callback(log_cb):
    """Return a logger that is safe when no GUI callback is attached."""
    def log(msg: str):
        if log_cb:
            log_cb(msg)
    return log


def _make_cancel_checker(stop_cb):
    """Return the cancellation hook used before expensive workflow steps."""
    def check_cancelled():
        if stop_cb and stop_cb():
            raise RuntimeError("Cancelled by user")
    return check_cancelled


def _log_banner(log, title: str, subtitle=None) -> None:
    """Write a consistent, easy-to-scan stage banner to the GUI log."""
    log(title.capitalize())
    if subtitle:
        log(subtitle)


def _setup_pipeline_context(
        *,
        output_dir: str,
        organism: str,
        log,
        do_basecalling: bool,
        do_nanotel: bool,
        bam_path: str,
        nanotel_mapping: bool,
        align_during_basecalling: bool,
):
    """Create workflow context in a new timestamped run folder."""
    base_dir = _resolve_base_output_dir(output_dir)
    trial_name = _build_run_folder_name(base_dir)
    context = setup_context(
        trial_name=trial_name,
        base_output_dir=base_dir,
        config_path=None,
        organism=organism,
        log_callback=log,
    )

    log(f"Results will be saved under: {context.path_manager.get_results_dir_path()}")
    context.path_manager.reset_generated_outputs(
        include_results=True,
        include_basecalling_outputs=do_basecalling,
        include_fastq_outputs=do_basecalling or bool(do_nanotel and bam_path),
        include_aligned_outputs=align_during_basecalling or nanotel_mapping,
    )
    log("Prepared fresh output folders for this run")
    return context


def _build_run_folder_name(base_dir: str) -> str:
    """Return a unique GUI run folder name with a timestamp suffix."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trial_name = f"{APP_OUTPUT_FOLDER}_{timestamp}"
    base_path = Path(base_dir)

    if not (base_path / trial_name).exists():
        return trial_name

    index = 1
    while (base_path / f"{trial_name}_{index:02d}").exists():
        index += 1
    return f"{trial_name}_{index:02d}"


def _resolve_base_output_dir(output_dir: str) -> str:
    """Normalize selected output paths to the parent of the trial directory."""
    output_path = Path(output_dir)

    # The GUI can pass the selected root, the stable trial folder, or a generated
    # child such as results/mapping. Normalize all of them to the base directory.
    group_dirs = {'processing', 'results'}
    leaf_subdirs = {
        'basecalled', 'demultiplexed', 'fastq', 'nanotel', 'mapping',
        'methylation', 'aligned', 'logs',
    }

    is_trial_group = output_path.name in group_dirs
    is_nested_subdir = (
        output_path.name in leaf_subdirs
        and output_path.parent.name in group_dirs
    )

    if _is_app_run_folder(output_path.name):
        return str(output_path.parent)

    if is_nested_subdir:
        trial_root = output_path.parent.parent
        return str(trial_root.parent if _is_app_run_folder(trial_root.name) else trial_root)

    if is_trial_group:
        trial_root = output_path.parent
        return str(trial_root.parent if _is_app_run_folder(trial_root.name) else trial_root)

    return str(output_path)


def _is_app_run_folder(folder_name: str) -> bool:
    """Detect stable and timestamped Telomere Analyzer GUI run folders."""
    return (
        folder_name == APP_OUTPUT_FOLDER
        or folder_name.startswith(f"{APP_OUTPUT_FOLDER}_")
    )


def _derive_analysis_flags(
        *,
        bam_path: str,
        bam_is_aligned,
        bam_has_modifications,
        methylation_type: str,
        chromosome_mapping: bool,
        nanotel_mapping: bool,
) -> dict:
    """Translate GUI state and BAM inspection into workflow flags."""
    if bam_path:
        # BAM modifications only count when alignment is already present.
        # Otherwise the BAM still needs mapping before methylation can run.
        has_methylation = bool(bam_is_aligned and bam_has_modifications)
        nanotel_mapping = nanotel_mapping or bool(bam_is_aligned)
    else:
        has_methylation = str(methylation_type or "").strip().lower() != "none"

    return {
        "has_methylation": has_methylation,
        "align_during_basecalling": chromosome_mapping,
        "nanotel_mapping": nanotel_mapping,
    }


def _apply_gui_config_overrides(
        context,
        *,
        organism: str,
        methylation_type: str,
        non_pod5_trim_status: str,
        summary_only: bool,
        tvr_mode: str,
        tvr_manual: str,
        read_length: str,
        max_distance_edge: str,
        min_density_threshold: str,
) -> None:
    """Apply advanced GUI settings to workflow configuration."""
    basecalling_overrides = _build_basecalling_overrides(methylation_type)
    if basecalling_overrides:
        context.config_manager.update_basecalling_params(basecalling_overrides)

    # Trimmed reads usually need a shorter allowed distance from the read edge.
    # Keep a user-entered custom value untouched.
    if non_pod5_trim_status == "trimmed" and str(max_distance_edge).strip() == "134":
        max_distance_edge = "50"

    nanotel_overrides = _build_nanotel_overrides(
        context.config_manager,
        organism=organism,
        summary_only=summary_only,
        tvr_mode=tvr_mode,
        tvr_manual=tvr_manual,
        read_length=read_length,
        max_distance_edge=max_distance_edge,
        min_density_threshold=min_density_threshold,
    )
    if nanotel_overrides:
        context.config_manager.update_nanotel_params(nanotel_overrides)


def _log_bam_state(log, bam_path: str, bam_is_aligned, bam_has_modifications) -> None:
    """Log automatic BAM alignment/modification inspection."""
    if not bam_path:
        return

    alignment_state = (
        "aligned" if bam_is_aligned is True
        else "not aligned" if bam_is_aligned is False
        else "unknown alignment"
    )
    modification_state = (
        "with modifications" if bam_has_modifications is True
        else "without modifications" if bam_has_modifications is False
        else "unknown modifications"
    )
    log(f"BAM input marked as {alignment_state}, {modification_state}")


def _dispatch_workflow(
        *,
        operator,
        context,
        pod5_path: str,
        fastq_path: str,
        bam_path: str,
        organism: str,
        do_basecalling: bool,
        do_nanotel: bool,
        log,
        check_cancelled,
        has_methylation: bool,
        align_during_basecalling: bool,
        nanotel_mapping: bool,
        bam_is_aligned,
):
    """Choose the workflow branch requested by the GUI checkboxes."""
    if do_basecalling and do_nanotel:
        return _run_full_pipeline(
            operator,
            context,
            pod5_path,
            organism,
            log,
            check_cancelled,
            has_methylation,
            align_during_basecalling,
        )

    if do_basecalling:
        return _run_basecalling_only(
            operator,
            pod5_path,
            organism,
            log,
            check_cancelled,
            align_during_basecalling,
        )

    if do_nanotel:
        return _run_nanotel_only(
            operator,
            fastq_path,
            bam_path,
            organism,
            log,
            check_cancelled,
            has_methylation,
            nanotel_mapping,
            bam_is_aligned,
        )

    return None


def _finish_pipeline_run(result, run_started_at: float, context, log) -> tuple[int, str]:
    """Convert workflow success/failure into the WorkerThread return format."""
    if result:
        elapsed_seconds = time.monotonic() - run_started_at
        log("Pipeline finished successfully")
        log(f"Total run time: {elapsed_seconds:.1f}s")
        log(f"Results: {context.path_manager.get_results_dir_path()}")
        return (0, "Workflow completed successfully")

    log("PIPELINE FAILED")
    return (1, "Pipeline execution failed")


def _run_basecalling_only(
        operator,
        pod5_path,
        organism,
        log,
        check_cancelled,
        align_during_basecalling: bool = False,
):
    """Execute only the basecalling workflow."""
    check_cancelled()

    if not pod5_path:
        log("POD5 Workflow selected but no POD5 path provided.")
        return 1

    return operator.run_basecalling(
        pod5_path,
        organism=organism,
        align_during_basecalling=align_during_basecalling,
    )


def _run_nanotel_only(
        operator,
        fastq_path,
        bam_path,
        organism,
        log,
        check_cancelled,
        has_methylation: bool = False,
        run_mapping: bool = False,
        bam_is_aligned: bool = False,
):
    """Run NanoTel from FASTQ or BAM input."""
    check_cancelled()
    input_file = fastq_path if fastq_path else bam_path
    if not input_file:
        log("FASTQ/BAM input required for NanoTel.")
        return 1

    return operator.run_nanotel_workflow(
        input_file,
        organism=organism,
        run_mapping=run_mapping,
        has_methylation=has_methylation,
        bam_is_aligned=bool(bam_path and bam_is_aligned),
    )


def _run_full_pipeline(
        operator,
        context,
        pod5_path,
        organism,
        log,
        check_cancelled,
        methylation_enabled: bool = False,
        align_during_basecalling: bool = False,
):
    """Execute the full POD5 to NanoTel workflow."""
    check_cancelled()

    return operator.run_pod5_workflow(
        pod5_path,
        organism=organism,
        methylation_enabled=methylation_enabled,
        align_during_basecalling=align_during_basecalling,
    )


def _build_basecalling_overrides(methylation_type: str) -> dict:
    """Convert GUI methylation selection into Dorado basecalling overrides."""
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
        summary_only: bool,
        tvr_mode: str,
        tvr_manual: str,
        read_length: str,
        max_distance_edge: str,
        min_density_threshold: str,
) -> dict:
    """Convert GUI NanoTel advanced options into NanoTel overrides."""
    overrides = {"summary_only": bool(summary_only)}

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
    """Safely parse an integer from a GUI string field."""
    value = str(value or "").strip()
    if not value:
        return None
    return int(value)


def _parse_float(value: str):
    """Safely parse a floating-point value from a GUI string field."""
    value = str(value or "").strip()
    if not value:
        return None
    return float(value)


def _parse_patterns(value: str) -> list:
    """Normalize a comma- or semicolon-separated pattern string into a list."""
    value = str(value or "").strip()
    if not value:
        return []
    return [
        pattern.strip().upper()
        for pattern in value.replace(";", ",").replace(" ", ",").split(",")
        if pattern.strip()
    ]
