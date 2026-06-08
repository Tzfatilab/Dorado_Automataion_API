from pathlib import Path

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
