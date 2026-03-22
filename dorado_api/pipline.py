
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
dorado_workflow_path = project_root / "dorado_workflow"
sys.path.insert(0, str(dorado_workflow_path))
sys.path.insert(0, str(project_root))

from dorado_workflow.main import setup_context
from dorado_workflow.operators.workflow_operator import WorkflowOperator


def RunPipeline(
        *,
        trial_name: str = None,
        pod5_path: str = "",
        fastq_path: str = "",
        bam_path: str = "",
        nanotel_path: str = "",
        output_dir: str,
        organism: str,
        do_pod5: bool,
        do_fastq: bool,
        do_nanotel: bool,
        do_align: bool,
        do_r: bool,
        log_cb=None,
        run_filtration: bool,
        run_mapping: bool,
        run_methylation: bool,
        stop_cb = None
)-> tuple[int, str]:  # Returns (status_code, message)
    """
    Execute telomere analysis pipeline from any starting point.

    INPUT PATHS (optional - provide as needed):
        pod5_path: POD5 files for basecalling
        fastq_path: FASTQ sequences for analysis
        bam_path: Aligned BAM files
        nanotel_path: Pre-computed NanoTel summaries

    WORKFLOW STEPS (executed based on flags):
        do_pod5: Basecall POD5 → FASTQ
        do_fastq: Filter and preprocess FASTQ
        do_nanotel: Identify and analyze telomeres
        do_align: Align sequences to reference
        do_r: Statistical analysis (with optional filtration, mapping, methylation)

    PARAMETERS:
        output_dir (str): Output base directory (required)
        organism (str): 'mouse', 'human', or 'fish' (required)
        log_cb (callable): Logging function
        stop_cb (callable): Cancellation signal

    RETURNS:
        (0, message) = Success
        (1, message) = Error (missing inputs or execution failure)
    """

    def log(msg: str):
        if log_cb:
            log_cb(msg)

    log("\n" + "=" * 60)
    log("Setting up workflow context...")
    log("=" * 60)

    output_path = Path(output_dir)

    actual_trial = output_path.name

    # Check if this is a trial folder (has subdirs) or base folder
    trial_subdirs = ['nanotel_output', 'aligned', 'logs', 'fastqs', 'demuxed']
    is_trial_folder = any((output_path / subdir).exists() for subdir in trial_subdirs)

    # Smart detection: Check if output_dir ends with trial_name
    if is_trial_folder:
        base_dir = str(output_path.parent)
        log(f"✅ Detected trial-specific folder. Using parent as base: {base_dir}")
    else:
        base_dir = str(output_path)
        log(f"✅ Using selected folder as base: {base_dir}")

    context = setup_context(
        trial_name=actual_trial,
        base_output_dir=base_dir,
        config_path=None
    )

    operator = WorkflowOperator(context=context)

    log("✅ Context ready.\n")

    # Route inputs to correct workflow steps
    # Use first available input for each step
    res = 0

    if do_pod5:
        if pod5_path:
            log("=" * 60)
            log("STEP 1: POD5 WORKFLOW")
            log("=" * 60)
            res = operator.run_pod5_workflow(pod5_path, organism=organism)
        else:
            msg = "POD5 Workflow selected but no POD5 path provided."
            log(f"❌ {msg}")
            return (1, msg)

    if do_fastq:
        if fastq_path:
            log("\n" + "=" * 60)
            log("STEP 2: FASTQ WORKFLOW")
            log("=" * 60)
            res = operator.run_fastq_workflow(fastq_path, organism=organism)
        else:
            msg = "FASTQ Workflow selected but no FASTQ path provided."
            log(f"❌ {msg}")
            return (1, msg)

    if do_nanotel:
        input_for_nanotel = fastq_path or pod5_path
        if input_for_nanotel:
            log("\n" + "=" * 60)
            log(" STEP 3: NANOTEL ANALYSIS")
            log("=" * 60)
            res = operator.run_nanotel_only(input_for_nanotel)
        else:
            msg = "NanoTel Analysis selected but no FASTQ/POD5 path provided."
            log(f"❌ {msg}")
            return (1, msg)

    if do_align:
        input_for_align = bam_path or fastq_path or pod5_path
        if input_for_align:
            log("\n" + "=" * 60)
            log("STEP 4: ALIGNMENT")
            log("=" * 60)
            res = operator.run_alignment_only(input_for_align, organism=organism)
        else:
            msg = "Alignment selected but no BAM/FASTQ/POD5 path provided."
            log(f"❌ {msg}")
            return (1, msg)

    if do_r:
        input_for_r = nanotel_path or bam_path
        if input_for_r:
            log("\n" + "=" * 60)
            log("STEP 5: R-ANALYSIS")
            log("=" * 60)
            res = operator.run_r_analysis_only(run_filtration, run_mapping, run_methylation)
        else:
            msg = "R-Analysis selected but no NanoTel/BAM path provided."
            log(f"❌ {msg}")
            return (1, msg)

    log("\n" + "=" * 60)
    if res == 0:
        log("✅ PIPELINE COMPLETED SUCCESSFULLY")
        return (0, "Workflow completed successfully")
    else:
        log("❌ PIPELINE FAILED")
        return (1, "Pipeline execution failed")