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
    - Execute complete workflows (POD5 → analysis, FASTQ → analysis)
    - Execute single process steps
    - Manage processor dependencies and data flow
    - Handle errors and logging
    - Track workflow state

    Three main workflow scenarios:
    1. POD5 workflow: basecall → demux → nanotel → align → R analysis (all three)
    2. FASTQ workflow: nanotel → align → R analysis (filtration only, no methylation yet)
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

    # ------------------------------ Internal helpers ------------------------------
    def _run_step(self, key: str, label: str, processor: Any,
                  *args: Any, **kwargs: Any) -> Optional[ProcessorResult]:
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
        result = processor.execute(*args, **kwargs)
        self.results[key] = result
        if not result.success:
            self.context.logger.error(f"Workflow stopped: {label} failed")
            return None
        return result

    def _log_inputs(self, input_path: str, organism: Optional[str]) -> None:
        """Log the standard input/organism header lines."""
        self.context.logger.section_header("WORKFLOW INPUTS")
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
        Shared POD5 prefix: basecall → demux → BAM-to-FASTQ.
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

    def _prepare_fastq_input(self, input_path: str) -> Optional[Tuple[Any, bool]]:
        """Convert BAM to FASTQ if needed. Returns (fastq_dir, do_mapping) or None on failure."""
        path = Path(input_path)
        bam_files = list(path.rglob("*.bam"))
        fastq_files = list(path.rglob("*.fastq*"))

        if bam_files and not fastq_files:
            self.context.logger.info("BAM input detected — converting to FASTQ...")
            result = self._run_step('bam_to_fastq', 'BAM to FASTQ conversion',
                                    self.bam_to_fastq, input_path)
            if result is None:
                return None
            # BAM input means we have mapping data, so enable alignment downstream.
            return result.get_output('fastq_dir'), True

        return input_path, False

    # ------------------------------ Full workflows ------------------------------

    def run_pod5_workflow(self, pod5_input: str, organism: str = "mouse",
                          methylation_enabled: bool = False,
                          align_during_basecalling: bool = False) -> bool:
        """
        Execute complete workflow starting from POD5 files.
        Workflow: POD5 → basecall → demux → nanotel → align → R analysis (all)
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

        # Alignment (skip only if already aligned during basecalling and no methylation needed)
        if not align_during_basecalling or methylation_enabled:
            if self._run_step('aligner', 'Alignment',
                              self.aligner, str(demuxed_dir), organism) is None:
                return False

        # R analysis (filtration, plus mapping/methylation when enabled)
        if self._run_step('r_analyzer', 'R analysis', self.r_analyzer,
                          run_filtration=True,
                          run_mapping=methylation_enabled,
                          run_methylation=methylation_enabled) is None:
            return False

        return self._finish_success()

    def run_basecalling(self, pod5_input: str, organism: str = None,
                        align_during_basecalling: bool = False) -> bool:
        """
        Execute the basecalling portion of the workflow.
        Workflow: POD5 → basecall → demux → BAM to FASTQ
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
                             align: bool = False, has_methylation: bool = False) -> bool:
        """
        Execute workflow starting from FASTQ files (from MinKNOW) or BAM files.
        Workflow: FASTQ (or BAM → FASTQ) → nanotel → align → R analysis (filtration only)
        Note: FASTQ from MinKNOW won't have methylation data, so we only run
        NanoTel filtration. Mapping/methylation require POD5 workflow.
        Args:
            path_input: Path to FASTQ or BAM directory
            organism: Organism type ('mouse' or 'human')
        Returns:
            True if workflow succeeds, False otherwise
        """
        self.context.logger.section_header("FASTQ WORKFLOW")
        self._log_inputs(path_input, organism)

        prepared = self._prepare_fastq_input(path_input)
        if prepared is None:
            return False
        fastq_input, do_mapping = prepared

        # NanoTel analysis
        if self._run_step('nanotel', 'NanoTel analysis',
                          self.nanotel, fastq_input) is None:
            return False

        # Alignment
        if align:
            if self._run_step('aligner', 'Alignment',
                              self.aligner, fastq_input, organism) is None:
                return False

        # R analysis (filtration only - no methylation in FASTQ from MinKNOW)
        self.context.logger.info(
            "Note: FASTQ workflow runs NanoTel filtration only.\n"
            "For mapping/methylation analysis, use POD5 workflow with basecalling."
        )
        if self._run_step('r_analyzer', 'R analysis', self.r_analyzer,
                          run_filtration=True,
                          run_mapping=do_mapping,
                          run_methylation=has_methylation and do_mapping) is None:
            return False

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
            self.context.logger.info("✓ NanoTel analysis completed")
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
            self.context.logger.info("✓ Alignment completed")
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
        self.context.logger.section_header("R ANALYSIS ONLY")
        result = self._run_step('r_analyzer', 'R analysis', self.r_analyzer,
                                run_filtration=run_filtration,
                                run_mapping=run_mapping,
                                run_methylation=run_methylation)
        if result is not None:
            self.context.logger.info("✓ R analysis completed")
            if run_filtration:
                self.context.logger.info(f"Filtered summaries: {result.get_output('nanotel_filtered')}")
            if run_mapping:
                self.context.logger.info(f"Mapping output: {result.get_output('mapping_output')}")
            if run_methylation:
                self.context.logger.info(f"Methylation output: {result.get_output('methylation_output')}")
        return result is not None

    # ------------------------------ Result accessors / utilities ------------------------------

    def _print_workflow_summary(self) -> None:
        """Print summary of workflow execution."""
        self.context.logger.info("\n=== WORKFLOW SUMMARY ===")
        for processor_name, result in self.results.items():
            status = "✓ SUCCESS" if result.success else "✗ FAILED"
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