"""
Workflow Operator Module
========================
Orchestrates the complete workflow by coordinating all processor classes.
Handles three main execution scenarios and manages the pipeline flow.
"""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from processors.base import WorkflowContext, ProcessorResult
from processors.basecaller import BasecallerProcessor
from processors.demuxer import DemuxProcessor
from processors.nanotel import NanoTelProcessor
from processors.aligner import AlignmentProcessor
from processors.r_analyzer import RAnalyzer
from processors.bam_to_fastq import BamToFastqProcessor


class WorkflowOperator:
    """
    Main workflow orchestrator that coordinates all processing steps.
    Responsibilities:
    - Execute complete workflows (POD5 ג†’ analysis, FASTQ ג†’ analysis)
    - Execute single process steps
    - Manage processor dependencies and data flow
    - Handle errors and logging
    - Track workflow state

    Three main workflow scenarios:
    1. POD5 workflow: basecall ג†’ demux ג†’ nanotel ג†’ align ג†’ R analysis (all three)
    2. FASTQ workflow: nanotel ג†’ align ג†’ R analysis (filtration only, no methylation yet)
    3. Single process: Run individual step (nanotel, align, R analysis)
    """

    def __init__(self, context: WorkflowContext):
        """
        Initialize workflow operator with context.
        Args:
            context: WorkflowContext with all shared resources
        """
        self.context = context

        # Initialize all processors
        self.basecaller = BasecallerProcessor(context)
        self.demuxer = DemuxProcessor(context)
        self.nanotel = NanoTelProcessor(context)
        self.aligner = AlignmentProcessor(context)
        self.r_analyzer = RAnalyzer(context)
        self.bam_to_fastq = BamToFastqProcessor(context)

        # Track workflow state
        self.results: Dict[str, ProcessorResult] = {}

    STEP_DETAILS = {
        'Basecalling': (
            'Converts POD5 signal',
            'a basecalled BAM file',
        ),
        'Demultiplexing': (
            'Separates reads by barcode',
            'barcode-specific BAM folders',
        ),
        'BAM to FASTQ conversion': (
            'Converts BAM reads',
            'FASTQ files for each barcode',
        ),
        'NanoTel analysis': (
            'Measures telomere features',
            'barcode-specific NanoTel summaries',
        ),
        'Alignment': (
            'Aligns reads to the reference genome',
            'aligned reads and mapping results',
        ),
        'Post-analysis': (
            'Builds the requested analysis results',
            'tables and summary reports',
        ),
    }

    # ------------------------------ Internal helpers ------------------------------
    def _run_step(self, key: str, label: str, processor: Any,
                  *args: Any, step: Optional[str] = None,
                  **kwargs: Any) -> Optional[ProcessorResult]:
        """
        Execute a processor, store its result, and check for success.
        Args:
            key: Name under which to store the result.
            label: Human-readable step name used in the error message.
            processor: Processor instance whose ``execute`` will be called.
            *args, **kwargs: Arguments forwarded to ``processor.execute``.
        Returns:
            The ProcessorResult on success, or None on failure (after logging).
        """
        title = f"{step}: {label}" if step else label
        self.context.logger.section_header(title)
        description, output = self.STEP_DETAILS.get(label, (None, None))
        if description:
            self.context.logger.info(f"{description}; creates {output}.")

        result = processor.execute(*args, **kwargs)
        self.results[key] = result
        if not result.success:
            self.context.logger.error(f"Workflow stopped: {label} failed")
            return None
        return result

    def _log_inputs(self, input_path: str, organism: Optional[str]) -> None:
        """Log the standard input/organism header lines."""
        self.context.logger.section_header("Run details")
        self.context.logger.info(f"Input: {input_path}")
        self.context.logger.info(f"Organism: {organism}")

    def _finish_success(self) -> bool:
        """Log the success banner and print the run summary."""
        self.context.logger.section_header("WORKFLOW COMPLETED SUCCESSFULLY")
        self._print_workflow_summary()
        return True

    def _run_basecall_to_fastq(self, pod5_input: str, organism: Optional[str],
                               align_during_basecalling: bool
                               ) -> Optional[Tuple[Any, Any]]:
        """
        Shared POD5 prefix: basecall ג†’ demux ג†’ BAM-to-FASTQ.
        Returns:
            (demuxed_dir, fastq_dir) on success, or None on failure.
        """
        result = self._run_step('basecaller', 'Basecalling', self.basecaller,
                                 pod5_input, organism, align_during_basecalling)
        if result is None:
            return None
        basecalled_bam = result.get_output('bam')

        result = self._run_step('demuxer', 'Demultiplexing', self.demuxer,
                                 str(basecalled_bam))
        if result is None:
            return None
        demuxed_dir = result.get_output('output_dir')

        result = self._run_step('bam_to_fastq', 'BAM to FASTQ conversion',
                                 self.bam_to_fastq, str(demuxed_dir))
        if result is None:
            return None
        fastq_dir = result.get_output('fastq_dir')

        return demuxed_dir, fastq_dir

    def _prepare_fastq_input(self, input_path: str) -> Optional[Any]:
        """Convert BAM to FASTQ if needed. Returns the FASTQ input path or None on failure."""
        path = Path(input_path)
        bam_files = list(path.rglob("*.bam"))
        fastq_files = list(path.rglob("*.fastq*"))

        if bam_files and not fastq_files:
            self.context.logger.info("BAM input detected - converting to FASTQ...")
            result = self._run_step('bam_to_fastq', 'BAM to FASTQ conversion',
                                    self.bam_to_fastq, input_path)
            if result is None:
                return None
            return result.get_output('fastq_dir')

        return input_path

    def _log_methylation_outputs(self, result: ProcessorResult) -> None:
        """Log methylation outputs without defining the R output structure here."""
        methylation_dir = result.get_output('methylation_output')
        if not methylation_dir:
            return

        methylation_dir = Path(methylation_dir)

        if not methylation_dir.exists():
            self.context.logger.info(
                "Methylation analysis was skipped because no mapped methylation input was produced."
            )
            return

        output_files = sorted(path for path in methylation_dir.rglob("*") if path.is_file())
        if not output_files:
            self.context.logger.info(
                "Methylation analysis completed with no output files."
            )
            self.context.logger.info(
                "Review the mapping results and confirm that mapped BAM files contain modified-base tags."
            )
            return

        self.context.logger.section_header("Modification Results")
        self.context.logger.info(f"Methylation output: {methylation_dir}")

        for path in output_files[:10]:
            self.context.logger.info(f"  {path.relative_to(methylation_dir)}")
        if len(output_files) > 10:
            remaining = len(output_files) - 10
            self.context.logger.info(f"  ... and {remaining} more file(s)")

    # ------------------------------ Full workflows ------------------------------

    def run_pod5_workflow(self, pod5_input: str, organism: str = "mouse",
                          methylation_enabled: bool = False,
                          align_during_basecalling: bool = False) -> bool:
        """
        Execute complete workflow starting from POD5 files.
        Workflow: POD5 ג†’ basecall ג†’ demux ג†’ nanotel ג†’ align ג†’ R analysis (all)
        Args:
            pod5_input: Path to POD5 input (file or directory)
            organism: Organism type ('mouse' or 'human')
        Returns:
            True if entire workflow succeeds, False otherwise
        """
        self.context.logger.section_header("POD5 COMPLETE WORKFLOW")
        self._log_inputs(pod5_input, organism)

        prep = self._run_basecall_to_fastq(pod5_input, organism, align_during_basecalling)
        if prep is None:
            return False
        demuxed_dir, fastq_dir = prep

        # NanoTel analysis
        if self._run_step('nanotel', 'NanoTel analysis',
                          self.nanotel, str(fastq_dir)) is None:
            return False

        # R mapping expects the aligned/ directory and Dorado sequencing summary.
        # Even if basecalling used a reference, run the alignment step to produce
        # the normalized inputs consumed by the post-analysis scripts.
        if align_during_basecalling or methylation_enabled:
            if self._run_step('aligner', 'Alignment',
                              self.aligner, str(demuxed_dir), organism) is None:
                return False

        run_mapping = align_during_basecalling or methylation_enabled

        # Post-analysis (filtration, plus mapping when requested and methylation when enabled)
        result = self._run_step('r_analyzer', 'Post-analysis', self.r_analyzer,
                                run_filtration=True,
                                run_mapping=run_mapping,
                                run_methylation=methylation_enabled)
        if result is None:
            return False
        if methylation_enabled:
            self._log_methylation_outputs(result)

        return self._finish_success()

    def run_basecalling(self, pod5_input: str, organism: str = None,
                        align_during_basecalling: bool = False) -> bool:
        """
        Execute the basecalling portion of the workflow.
        Workflow: POD5 ג†’ basecall ג†’ demux ג†’ BAM to FASTQ
        Args:
            pod5_input: Path to POD5 input (file or directory)
        Returns:
            True if entire workflow succeeds, False otherwise
        """
        self.context.logger.section_header("POD5 BASECALLING WORKFLOW")
        self._log_inputs(pod5_input, organism)

        return self._run_basecall_to_fastq(
            pod5_input, organism, align_during_basecalling) is not None

    def run_nanotel_workflow(self, path_input: str, organism: str = "mouse",
                             run_mapping: bool = False,
                             has_methylation: bool = False,
                             bam_is_aligned: bool = False) -> bool:
        """
        Execute workflow starting from FASTQ files (from MinKNOW) or BAM files.
        Workflow: FASTQ (or BAM ג†’ FASTQ) ג†’ nanotel ג†’ align ג†’ R analysis (filtration only)
        Note: FASTQ from MinKNOW won't have methylation data, so we only run
        NanoTel filtration. Mapping/methylation require POD5 workflow.
        Args:
            path_input: Path to FASTQ or BAM directory
            organism: Organism type ('mouse' or 'human')
        Returns:
            True if workflow succeeds, False otherwise
        """
        self.context.logger.section_header("FASTQ analysis workflow")
        self._log_inputs(path_input, organism)

        prepared = self._prepare_fastq_input(path_input)
        if prepared is None:
            return False
        fastq_input = prepared
        do_mapping = run_mapping
        original_input = Path(path_input)
        use_existing_bam_alignment = (
            bam_is_aligned
            and any(original_input.rglob("*.bam"))
        )

        # NanoTel analysis
        total_steps = 3 if do_mapping else 2
        if self._run_step('nanotel', 'NanoTel analysis',
                          self.nanotel, fastq_input,
                          step=f"Step 1/{total_steps}") is None:
            return False

        # Alignment
        if do_mapping:
            self.context.logger.info("NanoTel mapping selected")
            alignment_input = path_input if use_existing_bam_alignment else fastq_input
            alignment_kwargs = {}
            if use_existing_bam_alignment:
                self.context.logger.info("Using existing BAM alignment for mapping")
                alignment_kwargs = {
                    "input_type": "bam",
                    "use_existing_alignment": True,
                }
            if self._run_step('aligner', 'Alignment',
                                self.aligner, alignment_input, organism,
                                step=f"Step 2/{total_steps}",
                                **alignment_kwargs) is None:
                return False

        final_step = total_steps
        run_methylation = has_methylation and do_mapping
        result = self._run_step('r_analyzer', 'Post-analysis', self.r_analyzer,
                                run_filtration=True,
                                run_mapping=do_mapping,
                                run_methylation=run_methylation,
                                step=f"Step {final_step}/{total_steps}")
        if result is None:
            return False
        if run_methylation:
            self._log_methylation_outputs(result)

        return self._finish_success()

    # ------------------------------ Single-step workflows ------------------------------

    def run_nanotel_only(self, fastq_input: str) -> bool:
        """
        Execute only NanoTel analysis.
        Args:
            fastq_input: Path to FASTQ directory
        Returns:
            True if succeeds, False otherwise
        """
        self.context.logger.section_header("NANOTEL ANALYSIS ONLY")
        result = self._run_step('nanotel', 'NanoTel analysis', self.nanotel, fastq_input)
        if result is not None:
            self.context.logger.info("OK NanoTel analysis completed")
            self.context.logger.info(f"Output: {result.get_output('nanotel_output')}")
        return result is not None

    def run_alignment_only(self, fastq_input: str, organism: str = "mouse") -> bool:
        """
        Execute only alignment.
        Args:
            fastq_input: Path to FASTQ directory
            organism: Organism type ('mouse' or 'human')
        Returns:
            True if succeeds, False otherwise
        """
        self.context.logger.section_header("ALIGNMENT ONLY")
        result = self._run_step('aligner', 'Alignment', self.aligner, fastq_input, organism)
        if result is not None:
            self.context.logger.info("OK Alignment completed")
            self.context.logger.info(f"Output: {result.get_output('aligned_dir')}")
        return result is not None

    def run_r_analysis_only(self, run_filtration: bool = True,
                            run_mapping: bool = True,
                            run_methylation: bool = True) -> bool:
        """
        Execute only R analysis pipeline.
        This requires that previous steps have been completed:
        - For filtration: NanoTel summary.csv files must exist
        - For mapping/methylation: Aligned BAMs with methylation data must exist
        Args:
            run_filtration: If True, run NanoTel filtration
            run_mapping: If True, run mapping analysis
            run_methylation: If True, run methylation analysis
        Returns:
            True if succeeds, False otherwise
        """
        self.context.logger.section_header("POST-ANALYSIS ONLY")
        result = self._run_step('r_analyzer', 'Post-analysis', self.r_analyzer,
                                run_filtration=run_filtration,
                                run_mapping=run_mapping,
                                run_methylation=run_methylation)
        if result is not None:
            self.context.logger.info("OK R analysis completed")
            self.context.logger.info("Post-analysis completed")
            if run_filtration:
                self.context.logger.info(f"Filtered summaries: {result.get_output('nanotel_filtered')}")
            if run_mapping:
                self.context.logger.info(f"Mapping output: {result.get_output('mapping_output')}")
            if run_methylation:
                self._log_methylation_outputs(result)
        return result is not None

    # ------------------------------ Result accessors / utilities ------------------------------

    def _print_workflow_summary(self) -> None:
        """Print summary of workflow execution."""
        self.context.logger.info("\n=== WORKFLOW SUMMARY ===")
        for processor_name, result in self.results.items():
            status = "SUCCESS" if result.success else "FAILED"
            self.context.logger.info(f"{processor_name}: {status}")
            if result.success and result.statistics:
                for key, value in result.statistics.items():
                    self.context.logger.info(f"  {key}: {value}")

    def get_result(self, processor_name: str) -> Optional[ProcessorResult]:
        """
        Get result from a specific processor.
        Args:
            processor_name: Name of the processor
        Returns:
            ProcessorResult if found, None otherwise
        """
        return self.results.get(processor_name)

    def get_all_results(self) -> Dict[str, ProcessorResult]:
        """
        Get all processor results.
        Returns:
            Dictionary of all results
        """
        return self.results.copy()

    def clear_results(self) -> None:
        """Clear all stored results."""
        self.results.clear()

    def __repr__(self) -> str:
        """String representation of operator."""
        completed_steps = len(self.results)
        return f"WorkflowOperator(trial={self.context.path_manager.trial_name}, completed_steps={completed_steps})"
