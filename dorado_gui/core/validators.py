from pathlib import Path
import shutil
import subprocess

"""Validation helpers for workflow selection and input directories."""
def validate_advanced_selection(
        *,
        do_basecalling,
        do_nanotel,
        pod5_path,
        fastq_path,
        bam_path
):
    """Validate workflow flag combinations against the provided input paths.
    Returns:
        List of user-facing validation error strings.
    """
    errors = []

    has_pod5 = bool(pod5_path)
    has_fastq = bool(fastq_path)
    has_bam = bool(bam_path)

    if do_basecalling and not has_pod5:
        errors.append("Basecalling workflow selected, but no POD5 directory was provided.")
    elif do_basecalling:
        has_fastq = True

    if do_nanotel and not has_fastq and not has_bam:
        errors.append("Nanotel workflow selected, but no FASTQ or BAM directory was provided.")
    elif do_nanotel:
        has_fastq = True

    return errors


def validate_input_directories(pod5, fastq, bam):
    """Validate that selected directories contain files needed by each step.
    Args:
        pod5: Path to POD5 input directory.
        fastq: Path to FASTQ input directory.
        bam: Path to BAM input directory.

    Returns:
        List of user-facing validation error strings.
    """
    errors = []

    def has_files(path, patterns):
        """Check whether a directory recursively contains files matching patterns."""
        if not path:
            return False
        p = Path(path)
        if not p.exists():
            return False
        return any(list(p.rglob(pat)) for pat in patterns)

    if pod5 and not has_files(pod5, ["*.pod5"]):
        errors.append("POD5 directory has no .pod5 files")

    if fastq and not has_files(fastq, ["*.fastq", "*.fastq.gz"]):
        errors.append("FASTQ directory has no FASTQ files")

    if bam and not has_files(bam, ["*.bam"]):
        errors.append("BAM directory has no .bam files")

    return errors


def inspect_bam_directory(bam_path, max_files=3, methylation_read_limit=1000):
    """
    Inspect BAM files for alignment and modified-base tags.

    Returns:
        dict with:
        - bam_files: number of BAM files found
        - is_aligned: True/False/None
        - has_modifications: True/False/None
        - errors: non-fatal inspection errors
    """
    result = {
        "bam_files": 0,
        "is_aligned": None,
        "has_modifications": None,
        "errors": [],
    }

    if not bam_path:
        return result

    root = Path(bam_path)
    if not root.exists():
        result["errors"].append(f"BAM path does not exist: {bam_path}")
        return result

    bam_files = sorted(path for path in root.rglob("*.bam") if path.is_file())
    result["bam_files"] = len(bam_files)
    if not bam_files:
        result["errors"].append(f"No BAM files found in: {bam_path}")
        return result

    if not shutil.which("samtools"):
        result["errors"].append("samtools is not available; BAM metadata could not be inspected.")
        return result

    sampled_bams = bam_files[:max_files]
    result["is_aligned"] = any(_bam_has_mapped_reads(path) for path in sampled_bams)
    result["has_modifications"] = any(
        _bam_has_modified_base_tags(path, methylation_read_limit)
        for path in sampled_bams
    )
    return result


def _bam_has_mapped_reads(bam_file):
    completed = subprocess.run(
        ["samtools", "view", "-c", "-F", "4", str(bam_file)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        return False

    try:
        return int((completed.stdout or "0").strip() or "0") > 0
    except ValueError:
        return False


def _bam_has_modified_base_tags(bam_file, read_limit):
    process = subprocess.Popen(
        ["samtools", "view", str(bam_file)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        for index, line in enumerate(process.stdout or []):
            if index >= read_limit:
                break
            if "\tMM:Z:" in line or "\tMm:Z:" in line or "\tML:B:" in line:
                return True
        return False
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def validate_mode_inputs(inputs, selected_workflows):
    """
    Validate selected workflows and input compatibility.

    Checks that required input types were selected and that
    input directories contain the expected file formats.

    Args:
        inputs (dict): Selected input paths.
        selected_workflows (set[str]): Selected workflows.

    Returns:
        list[str]: Validation error messages, or an empty list if valid.
    """
        
    errors = []

    if not any(inputs.values()):
        errors.append("Please select an input directory.")
        return errors

    # Basecalling requires POD5
    if (
        "basecalling" in selected_workflows
        and not inputs["pod5"]
    ):
        errors.append(
            "Basecalling requires POD5 input."
        )

    # NanoTel requires FASTQ/BAM
    # OR POD5 + basecalling
    if (
        "nanotel" in selected_workflows
        and not (
            inputs["fastq"]
            or inputs["bam"]
            or (
                inputs["pod5"]
                and "basecalling" in selected_workflows
            )
        )
    ):
        errors.append(
            "NanoTel requires FASTQ, BAM, or POD5 with basecalling."
        )

    if errors:
        return errors

    # POD5 validation
    if inputs["pod5"]:
        return validate_input_directories(
            pod5=inputs["pod5"],
            fastq=None,
            bam=None
        )

    # FASTQ validation
    if inputs["fastq"]:
        return validate_input_directories(
            pod5=None,
            fastq=inputs["fastq"],
            bam=None
        )

    # BAM validation
    if inputs["bam"]:
        return validate_input_directories(
            pod5=None,
            fastq=None,
            bam=inputs["bam"]
        )

    return errors
