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
from dorado_workflow.utils.cancellation import WorkflowCancelled
from dorado_workflow.operators.workflow_operator import WorkflowOperator

APP_OUTPUT_FOLDER = "Telomere Analyzer"


def run_pipeline(
        *,
        trial_name: str = None,
        pod5_path: str = "",
        fastq_path: str = "",
        bam_path: str = "",
        project_path: str = "",
        do_post_analysis: bool = False,
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
        tvr_mode: str = "None",
        tvr_manual: str = "",
        allow_mismatch: bool = False,
        read_length: str = "",
        max_distance_edge: str = "",
        max_telomere_start: str = "",
        min_density_threshold: str = "",
        short_telomere_threshold: str = "",
        config_data=None,
        log_cb=None,
        stop_cb=None,
        report_cb=None,
) -> tuple[int, str]:
    """Run the selected workflow and return a WorkerThread status tuple.

    Args:
        trial_name: str; run name used for output directories and logs. Default: None.
        pod5_path: str; pod5 path. Default: ''.
        fastq_path: str; fastq path. Default: ''.
        bam_path: str; bam path. Default: ''.
        project_path: str; project path. Default: ''.
        do_post_analysis: bool; whether to recalculate an existing project. Default: False.
        output_dir: str; directory for generated outputs.
        organism: str; organism label selecting reference and analysis defaults.
        do_basecalling: bool; whether the run includes basecalling.
        do_nanotel: bool; whether the run includes NanoTel detection.
        non_pod5_trim_status: str; trimming state of the original BAM or FASTQ reads. Default: 'auto'.
        bam_is_aligned: Whether the selected BAM already contains alignments. Default: None.
        bam_has_modifications: Whether the BAM contains modified-base tags. Default: None.
        methylation_type: str; selected modified-base analysis mode. Default: 'None'.
        chromosome_mapping: bool; whether reference alignment is selected in the basecalling options. Default: False.
        nanotel_mapping: bool; whether chromosome mapping is selected for NanoTel analysis. Default: False.
        summary_only: bool; whether to omit individual-read pages from the report. Default: False.
        tvr_mode: str; selected TVR configuration mode. Default: 'None'.
        tvr_manual: str; user-entered TVR motifs. Default: ''.
        allow_mismatch: bool; whether one mismatch is allowed in repeat searches. Default: False.
        read_length: str; read-length value in base pairs. Default: ''.
        max_distance_edge: str; required read margin in base pairs. Default: ''.
        max_telomere_start: str; latest allowed telomere start in base pairs. Default: ''.
        min_density_threshold: str; minimum repeat density entered in the GUI. Default: ''.
        short_telomere_threshold: str; short-telomere cutoff entered in base pairs. Default: ''.
        config_data: Configuration snapshot supplied for this run. Default: None.
        log_cb: Callback receiving workflow log messages. Default: None.
        stop_cb: Callback reporting whether cancellation was requested. Default: None.
        report_cb: Callback receiving the completed dashboard path. Default: None.

    Returns:
        Status/message tuple: zero for success and nonzero for failure.
    """
    run_started_at = time.monotonic()
    log = _make_log_callback(log_cb)
    check_cancelled = _make_cancel_checker(stop_cb)

    if do_post_analysis:
        return _run_post_analysis(
            project_path=project_path, output_dir=output_dir, organism=organism,
            mapping=nanotel_mapping, summary_only=summary_only, read_length=read_length,
            max_telomere_start=max_telomere_start, density=min_density_threshold,
            short_cutoff=short_telomere_threshold, config_data=config_data,
            trim_status=non_pod5_trim_status,
            log=log, check_cancelled=check_cancelled, stop_cb=stop_cb, report_cb=report_cb,
        )

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
        config_data=config_data,
    )

    context.command_executor.stop_callback = stop_cb
    check_cancelled()

    _apply_gui_config_overrides(
        context,
        organism=organism,
        methylation_type=methylation_type,
        non_pod5_trim_status=non_pod5_trim_status,
        summary_only=summary_only,
        tvr_mode=tvr_mode,
        tvr_manual=tvr_manual,
        allow_mismatch=allow_mismatch,
        read_length=read_length,
        max_distance_edge=max_distance_edge,
        max_telomere_start=max_telomere_start,
        min_density_threshold=min_density_threshold,
        short_telomere_threshold=short_telomere_threshold,
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
    # Generate once, after filtering/mapping finish, in the existing worker thread.
    # A display/export failure must not discard successful scientific results.
    report_warning = ""
    if result and do_nanotel and summary_only:
        summary_path = context.path_manager.get_r_analysis_dir_path() / "dashboard_summary.html"
        log(f"Summary only: Excel and compact dashboard saved; detailed NanoTel outputs skipped.")
        if summary_path.is_file():
            log(f"Summary dashboard: {summary_path}")
            if report_cb:
                report_cb(str(summary_path))
    if result and do_nanotel and not summary_only:
        try:
            report_path = _write_full_report(context, log, check_cancelled)
            if report_cb:
                report_cb(str(report_path))
        except WorkflowCancelled:
            raise
        except Exception as exc:
            report_warning = f"\nDashboard/Excel export could not be completed: {exc}"
            log(report_warning.strip())
            # Preserve the location and exception type, not only its message.
            # This makes intermittent report failures diagnosable after the GUI closes.
            import traceback
            log(traceback.format_exc())
    status, message = _finish_pipeline_run(result, run_started_at, context, log)
    return status, message + report_warning


def _make_log_callback(log_cb):
    """Return a logger that is safe when no GUI callback is attached.

    Args:
        log_cb: Callback receiving workflow log messages.

    Returns:
        Callable that forwards progress text to the configured log destination.
    """
    def log(msg: str):
        """Log.

        Args:
            msg: str; progress message text.

        Returns:
            None.
        """
        if log_cb:
            log_cb(msg)
    return log


def _make_cancel_checker(stop_cb):
    """Return the cancellation hook used before expensive workflow steps.

    Args:
        stop_cb: Callback reporting whether cancellation was requested.

    Returns:
        Callable that raises WorkflowCancelled when cancellation is requested.
    """
    def check_cancelled():
        """Check cancelled.

        Inputs:
            None.

        Returns:
            None.
        """
        if stop_cb and stop_cb():
            raise WorkflowCancelled()
    return check_cancelled


def _log_banner(log, title: str, subtitle=None) -> None:
    """Write a consistent, easy-to-scan stage banner to the GUI log.

    Args:
        log: Callback receiving user-visible progress messages.
        title: str; displayed title.
        subtitle: Secondary displayed text. Default: None.

    Returns:
        None.
    """
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
        config_data=None,
):
    """Create workflow context in a new timestamped run folder.

    Args:
        output_dir: str; directory for generated outputs.
        organism: str; organism label selecting reference and analysis defaults.
        log: Callback receiving user-visible progress messages.
        do_basecalling: bool; whether the run includes basecalling.
        do_nanotel: bool; whether the run includes NanoTel detection.
        bam_path: str; bam path.
        nanotel_mapping: bool; whether chromosome mapping is selected for NanoTel analysis.
        align_during_basecalling: bool; whether Dorado should align reads while basecalling.
        config_data: Configuration snapshot supplied for this run. Default: None.

    Returns:
        WorkflowContext containing the new run configuration and resources.
    """
    base_dir = _resolve_base_output_dir(output_dir)
    trial_name = _build_run_folder_name(base_dir)
    context = setup_context(
        trial_name=trial_name,
        base_output_dir=base_dir,
        config_path=None,
        organism=organism,
        log_callback=log,
        config_data=config_data,
    )

    log(f"Results will be saved under: {context.path_manager.get_results_dir_path()}")
    context.path_manager.reset_generated_outputs(
        include_results=True,
        include_basecalling_outputs=do_basecalling,
        include_fastq_outputs=do_basecalling or bool(do_nanotel and bam_path),
        include_aligned_outputs=align_during_basecalling or nanotel_mapping,
        include_mapping_outputs=nanotel_mapping,
    )
    log("Output directories initialized")
    return context


def _build_run_folder_name(base_dir: str) -> str:
    """Return a unique GUI run folder name with a timestamp suffix.

    Args:
        base_dir: str; base dir.

    Returns:
        Timestamped run name with a suffix when necessary to avoid collisions.
    """
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
    """Use the selected directory as the parent of the new timestamped run.

    Folder names do not imply navigation: even an existing run or a directory
    named results/processing is an explicit user-selected destination.

    Args:
        output_dir: str; directory for generated outputs.

    Returns:
        Expanded output-directory path as a string.
    """
    return str(Path(output_dir).expanduser())



def _derive_analysis_flags(
        *,
        bam_path: str,
        bam_is_aligned,
        bam_has_modifications,
        methylation_type: str,
        chromosome_mapping: bool,
        nanotel_mapping: bool,
) -> dict:
    """Translate GUI state and BAM inspection into workflow flags.

    Args:
        bam_path: str; bam path.
        bam_is_aligned: Whether the selected BAM already contains alignments.
        bam_has_modifications: Whether the BAM contains modified-base tags.
        methylation_type: str; selected modified-base analysis mode.
        chromosome_mapping: bool; whether reference alignment is selected in the basecalling options.
        nanotel_mapping: bool; whether chromosome mapping is selected for NanoTel analysis.

    Returns:
        Resolved flags for methylation and alignment/mapping steps.
    """
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
        allow_mismatch: bool,
        read_length: str,
        max_distance_edge: str,
        max_telomere_start: str,
        min_density_threshold: str,
        short_telomere_threshold: str,
) -> None:
    """Apply advanced GUI settings to workflow configuration.

    Args:
        context: Shared workflow configuration, paths, logger and command executor.
        organism: str; organism label selecting reference and analysis defaults.
        methylation_type: str; selected modified-base analysis mode.
        non_pod5_trim_status: str; trimming state of the original BAM or FASTQ reads.
        summary_only: bool; whether to omit individual-read pages from the report.
        tvr_mode: str; selected TVR configuration mode.
        tvr_manual: str; user-entered TVR motifs.
        allow_mismatch: bool; whether one mismatch is allowed in repeat searches.
        read_length: str; read-length value in base pairs.
        max_distance_edge: str; required read margin in base pairs.
        max_telomere_start: str; latest allowed telomere start in base pairs.
        min_density_threshold: str; minimum repeat density entered in the GUI.
        short_telomere_threshold: str; short-telomere cutoff entered in base pairs.

    Returns:
        None.
    """
    basecalling_overrides = _build_basecalling_overrides(methylation_type)
    if basecalling_overrides:
        context.config_manager.update_basecalling_params(basecalling_overrides)

    nanotel_defaults = context.config_manager.get_nanotel_params()

    max_telomere_start = _resolve_telomere_start(
        nanotel_defaults, max_telomere_start, non_pod5_trim_status
    )
    max_distance_edge = max_telomere_start

    nanotel_overrides = _build_nanotel_overrides(
        context.config_manager,
        organism=organism,
        summary_only=summary_only,
        tvr_mode=tvr_mode,
        tvr_manual=tvr_manual,
        allow_mismatch=allow_mismatch,
        read_length=read_length,
        max_distance_edge=max_distance_edge,
        max_telomere_start=max_telomere_start,
        min_density_threshold=min_density_threshold,
        short_telomere_threshold=short_telomere_threshold,
    )
    if nanotel_overrides:
        context.config_manager.update_nanotel_params(nanotel_overrides)


def _log_bam_state(log, bam_path: str, bam_is_aligned, bam_has_modifications) -> None:
    """Log automatic BAM alignment/modification inspection.

    Args:
        log: Callback receiving user-visible progress messages.
        bam_path: str; bam path.
        bam_is_aligned: Whether the selected BAM already contains alignments.
        bam_has_modifications: Whether the BAM contains modified-base tags.

    Returns:
        None.
    """
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
    """Choose the workflow branch requested by the GUI checkboxes.

    Args:
        operator: WorkflowOperator coordinating the shared processors.
        context: Shared workflow configuration, paths, logger and command executor.
        pod5_path: str; pod5 path.
        fastq_path: str; fastq path.
        bam_path: str; bam path.
        organism: str; organism label selecting reference and analysis defaults.
        do_basecalling: bool; whether the run includes basecalling.
        do_nanotel: bool; whether the run includes NanoTel detection.
        log: Callback receiving user-visible progress messages.
        check_cancelled: Callback raising when workflow cancellation is requested.
        has_methylation: bool; whether downstream processing requires modification tags.
        align_during_basecalling: bool; whether Dorado should align reads while basecalling.
        nanotel_mapping: bool; whether chromosome mapping is selected for NanoTel analysis.
        bam_is_aligned: Whether the selected BAM already contains alignments.

    Returns:
        Workflow success flag, or None when no execution path is selected.
    """
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
            nanotel_mapping=nanotel_mapping,
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
    """Convert workflow success/failure into the WorkerThread return format.

    Args:
        result: Result produced by the preceding operation.
        run_started_at: float; monotonic timestamp captured when the run started.
        context: Shared workflow configuration, paths, logger and command executor.
        log: Callback receiving user-visible progress messages.

    Returns:
        Status/message tuple: zero for success and nonzero for failure.
    """
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
    """Execute only the basecalling workflow.

    Args:
        operator: WorkflowOperator coordinating the shared processors.
        pod5_path: Pod5 path.
        organism: Organism label selecting reference and analysis defaults.
        log: Callback receiving user-visible progress messages.
        check_cancelled: Callback raising when workflow cancellation is requested.
        align_during_basecalling: bool; whether Dorado should align reads while basecalling. Default: False.

    Returns:
        True when basecalling succeeds; False on failure or missing prerequisites.
    """
    check_cancelled()

    if not pod5_path:
        log("POD5 Workflow selected but no POD5 path provided.")
        return False

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
    """Run NanoTel from FASTQ or BAM input.

    Args:
        operator: WorkflowOperator coordinating the shared processors.
        fastq_path: Fastq path.
        bam_path: Bam path.
        organism: Organism label selecting reference and analysis defaults.
        log: Callback receiving user-visible progress messages.
        check_cancelled: Callback raising when workflow cancellation is requested.
        has_methylation: bool; whether downstream processing requires modification tags. Default: False.
        run_mapping: bool; whether to run chromosome mapping. Default: False.
        bam_is_aligned: bool; whether the selected BAM already contains alignments. Default: False.

    Returns:
        True when the NanoTel workflow succeeds; False on failure.
    """
    check_cancelled()
    input_file = fastq_path if fastq_path else bam_path
    if not input_file:
        log("FASTQ/BAM input required for NanoTel.")
        return False

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
        nanotel_mapping: bool = False,
):
    """Execute the full POD5 to NanoTel workflow.

    Args:
        operator: WorkflowOperator coordinating the shared processors.
        context: Shared workflow configuration, paths, logger and command executor.
        pod5_path: Pod5 path.
        organism: Organism label selecting reference and analysis defaults.
        log: Callback receiving user-visible progress messages.
        check_cancelled: Callback raising when workflow cancellation is requested.
        methylation_enabled: bool; whether modified-base analysis is enabled. Default: False.
        align_during_basecalling: bool; whether Dorado should align reads while basecalling. Default: False.
        nanotel_mapping: bool; whether chromosome mapping is selected for NanoTel analysis. Default: False.

    Returns:
        True when the complete POD5 workflow succeeds; False on failure.
    """
    check_cancelled()

    return operator.run_pod5_workflow(
        pod5_path,
        organism=organism,
        methylation_enabled=methylation_enabled,
        align_during_basecalling=align_during_basecalling,
        run_mapping=nanotel_mapping,
    )


def _build_basecalling_overrides(methylation_type: str) -> dict:
    """Convert GUI methylation selection into Dorado basecalling overrides.

    Args:
        methylation_type: str; selected modified-base analysis mode.

    Returns:
        Basecalling parameter overrides for the selected modification mode.
    """
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
        allow_mismatch: bool,
        read_length: str,
        max_distance_edge: str,
        max_telomere_start: str,
        min_density_threshold: str,
        short_telomere_threshold: str,
) -> dict:
    """Convert GUI NanoTel advanced options into NanoTel overrides.

    Args:
        config_manager: Manager providing effective workflow settings.
        organism: str; organism label selecting reference and analysis defaults.
        summary_only: bool; whether to omit individual-read pages from the report.
        tvr_mode: str; selected TVR configuration mode.
        tvr_manual: str; user-entered TVR motifs.
        allow_mismatch: bool; whether one mismatch is allowed in repeat searches.
        read_length: str; read-length value in base pairs.
        max_distance_edge: str; required read margin in base pairs.
        max_telomere_start: str; latest allowed telomere start in base pairs.
        min_density_threshold: str; minimum repeat density entered in the GUI.
        short_telomere_threshold: str; short-telomere cutoff entered in base pairs.

    Returns:
        Validated NanoTel parameter overrides supplied by the GUI.
    """
    overrides = {"summary_only": bool(summary_only)}

    short_threshold = _parse_int(short_telomere_threshold)
    if short_threshold is not None:
        if short_threshold <= 0:
            raise ValueError("Short telomere threshold must be greater than zero")
        overrides["short_telomere_threshold_bp"] = short_threshold

    density = _parse_float(min_density_threshold)
    if density is not None:
        overrides["min_density"] = density
        overrides["density_threshold"] = density

    max_start = _parse_int(max_telomere_start)
    if max_start is not None:
        overrides["max_telomere_start"] = max_start

    if max_start is not None:
        overrides["max_edge_distance"] = max_start

    read_length_value = _parse_int(read_length)
    if read_length_value is not None:
        overrides["read_length"] = read_length_value

    if isinstance(tvr_mode, (set, list, tuple)):
        modes = {str(mode).strip().lower() for mode in tvr_mode}
    else:
        mode_text = str(tvr_mode or "").strip().lower()
        modes = {
            mode.strip()
            for mode in mode_text.replace(",", "+").split("+")
            if mode.strip() and mode.strip() != "none"
        }

    tvr_patterns = []
    if "use preset" in modes:
        tvr_patterns.extend(config_manager.get_tvr_patterns(organism))
    if "tsq1" in modes:
        tvr_patterns.append(config_manager.get_tsq1_pattern())
    if "enter manual" in modes or "manual" in modes:
        tvr_patterns.extend(_parse_patterns(tvr_manual))

    canonical = config_manager.config["nanotel"]["telomere_pattern"].upper()
    reverse = canonical.translate(str.maketrans("ACGT", "TGCA"))[::-1]
    if any(pattern.upper() in {canonical, reverse} for pattern in tvr_patterns):
        raise ValueError("Canonical telomere repeats cannot be used as TVR patterns.")

    # Preserve selection order while removing patterns duplicated across modes.
    overrides["tvr_patterns"] = list(dict.fromkeys(tvr_patterns))
    # The checkbox allows one mismatch for both the regular telomere pattern
    # and any selected TVR patterns. Preset ignores it and uses exact matches.
    max_mismatch = (
        0 if "use preset" in modes else int(bool(allow_mismatch))
    )
    overrides["max_mismatch"] = max_mismatch

    return overrides


def _parse_int(value: str):
    """Safely parse an integer from a GUI string field.

    Args:
        value: str; value to inspect, convert or format.

    Returns:
        Parsed integer, or None when no value was supplied.
    """
    value = str(value or "").strip()
    if not value:
        return None
    return int(value)


def _parse_float(value: str):
    """Safely parse a floating-point value from a GUI string field.

    Args:
        value: str; value to inspect, convert or format.

    Returns:
        Parsed floating-point value, or None when no value was supplied.
    """
    value = str(value or "").strip()
    if not value:
        return None
    return float(value)


def _parse_patterns(value: str) -> list:
    """Normalize a comma- or semicolon-separated pattern string into a list.

    Args:
        value: str; value to inspect, convert or format.

    Returns:
        Nonempty motif strings normalized to uppercase.
    """
    value = str(value or "").strip()
    if not value:
        return []
    return [
        pattern.strip().upper()
        for pattern in value.replace(";", ",").replace(" ", ",").split(",")
        if pattern.strip()
    ]


def _resolve_telomere_start(nanotel_params, requested_start, trim_status):
    """Apply the same trimming adjustment in fresh and recalculation runs.

    Args:
        nanotel_params: Effective NanoTel settings, including filtering defaults.
        requested_start: Requested latest telomere start in base pairs.
        trim_status: Original read trimming state: trimmed, untrimmed or auto.

    Returns:
        Effective telomere-start threshold as text, adjusted for trimming state.
    """
    trimmed_start_default = nanotel_params.get("display_max_edge_distance", 50)
    untrimmed_start_default = nanotel_params.get("untrimmed_max_telomere_start", 134)
    if trim_status == "untrimmed":
        return str(untrimmed_start_default)
    # Undo the automatic untrimmed adjustment when switching back to trimmed.
    if trim_status == "trimmed" and str(requested_start).strip() == str(untrimmed_start_default):
        return str(trimmed_start_default)
    return str(requested_start).strip() or str(nanotel_params.get("max_telomere_start", trimmed_start_default))


def _run_post_analysis(*, project_path, output_dir, organism, mapping, summary_only, read_length,
                       max_telomere_start, density, short_cutoff, config_data,
                       log, check_cancelled, stop_cb, report_cb, trim_status="auto"):
    """Use the same R filtering/mapping and report writers as a normal run.

    Args:
        project_path: Project path.
        output_dir: Directory for generated outputs.
        organism: Organism label selecting reference and analysis defaults.
        mapping: Whether recalculation includes chromosome mapping.
        summary_only: Whether to omit individual-read pages from the report.
        read_length: Read-length value in base pairs.
        max_telomere_start: Latest allowed telomere start in base pairs.
        density: Minimum repeat density as a fraction.
        short_cutoff: Short-telomere cutoff in base pairs.
        config_data: Configuration snapshot supplied for this run.
        log: Callback receiving user-visible progress messages.
        check_cancelled: Callback raising when workflow cancellation is requested.
        stop_cb: Callback reporting whether cancellation was requested.
        report_cb: Callback receiving the completed dashboard path.
        trim_status: Original read trimming state: trimmed, untrimmed or auto. Default: 'auto'.

    Returns:
        Status/message tuple describing recalculation success or failure.
    """
    from dorado_workflow.processors.project_sources import ProjectSources
    import json
    check_cancelled()
    source = ProjectSources.inspect(project_path)
    organism = source.organism or organism
    base = Path(_resolve_base_output_dir(output_dir)).resolve()
    if base == source.root or source.root in base.parents:
        raise ValueError("Choose an Output Path outside the source project; Post-analysis never overwrites the original project.")
    context = _setup_pipeline_context(output_dir=str(base), organism=organism, log=log,
        do_basecalling=False, do_nanotel=True, bam_path="", nanotel_mapping=mapping,
        align_during_basecalling=False, config_data=config_data)
    context.command_executor.stop_callback = stop_cb
    params = dict(context.config_manager.get_nanotel_params())
    params.update(source.params)
    params["source_detection_settings"] = source.params.get("source_detection_settings", dict(source.params))
    # Only post-detection thresholds may change. Detection options come from
    # the source snapshot, never the current GUI TVR/mismatch controls.
    for key in ("input_dir", "output_dir"):
        params.pop(key, None)
    params["summary_only"] = bool(summary_only)
    max_telomere_start = _resolve_telomere_start(params, max_telomere_start, trim_status)
    params["input_trim_status"] = trim_status
    log(f"Post-analysis trimming: {trim_status}; latest telomere start and edge distance: {max_telomere_start} bp")
    for key, value, parse_value in (("min_read_length", read_length, int),
                                 ("max_telomere_start", max_telomere_start, int),
                                 ("density_threshold", density, float),
                                 ("short_telomere_threshold_bp", short_cutoff, int)):
        if str(value).strip():
            params[key] = parse_value(value)
    params["read_length"] = params.get("min_read_length")
    params["max_edge_distance"] = params["max_telomere_start"]
    params["min_density"] = params["density_threshold"]
    context.config_manager.config.setdefault("r_analysis", {})["run_nanotel_analysis"] = True
    context.config_manager.update_nanotel_params(params)
    reports = context.path_manager.get_reports_dir_path()
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "post_analysis_source.json").write_text(json.dumps({"source_project": str(source.root),
        "source_workbook": str(source.workbook) if source.workbook else None,
        "original_detection_settings": params["source_detection_settings"], "post_analysis_settings": params}, indent=2), encoding="utf-8")
    log("Post-analysis: restoring original before-filter NanoTel populations; TVR and mismatch settings are locked.")
    operator = WorkflowOperator(context=context)
    result = operator.run_post_analysis(source=source, check_cancelled=check_cancelled,
                                       run_mapping=mapping)
    if result is None:
        return (1, "Post-analysis failed; original project was not modified. Inspect the run log.")
    dashboard = (context.path_manager.get_r_analysis_dir_path() / "dashboard_summary.html"
                 if summary_only else _write_full_report(context, log, check_cancelled))
    if not dashboard.is_file():
        return (1, "Post-analysis finished without a dashboard; inspect the run log.")
    if report_cb:
        report_cb(str(dashboard))
    log("Post-analysis complete: " + str(dashboard))
    return (0, "Your updated dashboard and Excel workbook are ready.")


def _write_full_report(context, log, check_cancelled):
    """Shared full dashboard/export publication for normal and resumed runs.

    Args:
        context: Shared workflow configuration, paths, logger and command executor.
        log: Callback receiving user-visible progress messages.
        check_cancelled: Callback raising when workflow cancellation is requested.

    Returns:
        Path to the completed full dashboard.
    """
    from dorado_workflow.reports.all_barcodes import generate_run_report
    log("Generating All Barcodes dashboard and Excel workbook...")
    report_path = Path(generate_run_report(context.path_manager.get_results_dir_path(),
                                         context.path_manager.get_nanotel_output_dir_path()))
    check_cancelled()
    log(f"All Barcodes report: {report_path}")
    log(f"Excel workbook: {report_path.with_name('nanotel_results.xlsx')}")
    return report_path
