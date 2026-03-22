"""
Workflow Operator Module
========================

Orchestrates the complete workflow by coordinating all processor classes.
Handles three main execution scenarios and manages the pipeline flow.
"""

from pathlib import Path
from typing import Optional, Dict
from processors.base import WorkflowContext, ProcessorResult
from processors.basecaller import BasecallerProcessor
from processors.demuxer import DemuxProcessor
from processors.nanotel import NanoTelProcessor
from processors.aligner import AlignmentProcessor
from processors.r_analyzer import RAnalyzer


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

        # Track workflow state
        self.results: Dict[str, ProcessorResult] = {}

    def run_pod5_workflow(self, pod5_input: str, organism: str = "mouse") -> bool:
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
        self.context.logger.info(f"Input: {pod5_input}")
        self.context.logger.info(f"Organism: {organism}")

        # Step 1: Basecalling
        result = self.basecaller.execute(pod5_input, organism)
        self.results['basecaller'] = result
        if not result.success:
            self.context.logger.error("Workflow stopped: Basecalling failed")
            return False

        basecalled_bam = result.get_output('bam')

        # Step 2: Demultiplexing
        result = self.demuxer.execute(str(basecalled_bam))
        self.results['demuxer'] = result
        if not result.success:
            self.context.logger.error("Workflow stopped: Demultiplexing failed")
            return False

        demuxed_dir = result.get_output('demuxed_dir')

        # Step 3: NanoTel Analysis
        result = self.nanotel.execute(str(demuxed_dir))
        self.results['nanotel'] = result
        if not result.success:
            self.context.logger.error("Workflow stopped: NanoTel analysis failed")
            return False

        # Step 4: Alignment
        result = self.aligner.execute(str(demuxed_dir), organism)
        self.results['aligner'] = result
        if not result.success:
            self.context.logger.error("Workflow stopped: Alignment failed")
            return False

        # Step 5: R Analysis (all three: filtration, mapping, methylation)
        result = self.r_analyzer.execute(
            run_filtration=True,
            run_mapping=True,
            run_methylation=True
        )
        self.results['r_analyzer'] = result
        if not result.success:
            self.context.logger.error("Workflow stopped: R analysis failed")
            return False

        self.context.logger.section_header("WORKFLOW COMPLETED SUCCESSFULLY")
        self._print_workflow_summary()
        return True

    def run_fastq_workflow(self, fastq_input: str, organism: str = "mouse") -> bool:
        """
        Execute workflow starting from FASTQ files (from MinKNOW).

        Workflow: FASTQ → nanotel → align → R analysis (filtration only)

        Note: FASTQ from MinKNOW won't have methylation data, so we only run
        NanoTel filtration. Mapping/methylation require POD5 workflow.

        Args:
            fastq_input: Path to FASTQ directory (typically demuxed output)
            organism: Organism type ('mouse' or 'human')

        Returns:
            True if workflow succeeds, False otherwise
        """
        self.context.logger.section_header("FASTQ WORKFLOW")
        self.context.logger.info(f"Input: {fastq_input}")
        self.context.logger.info(f"Organism: {organism}")

        fastq_path = Path(fastq_input)
        if not fastq_path.exists():
            self.context.logger.error(f"FASTQ input not found: {fastq_input}")
            return False

        # Step 1: NanoTel Analysis
        result = self.nanotel.execute(fastq_input)
        self.results['nanotel'] = result
        if not result.success:
            self.context.logger.error("Workflow stopped: NanoTel analysis failed")
            return False

        # Step 2: Alignment
        result = self.aligner.execute(fastq_input, organism)
        self.results['aligner'] = result
        if not result.success:
            self.context.logger.error("Workflow stopped: Alignment failed")
            return False

        # Step 3: R Analysis (filtration only - no methylation in FASTQ from MinKNOW)
        self.context.logger.info(
            "Note: FASTQ workflow runs NanoTel filtration only.\n"
            "For mapping/methylation analysis, use POD5 workflow with basecalling."
        )

        result = self.r_analyzer.execute(
            run_filtration=True,
            run_mapping=False,
            run_methylation=False
        )
        self.results['r_analyzer'] = result
        if not result.success:
            self.context.logger.error("Workflow stopped: R analysis failed")
            return False

        self.context.logger.section_header("WORKFLOW COMPLETED SUCCESSFULLY")
        self._print_workflow_summary()
        return True

    def run_nanotel_only(self, fastq_input: str) -> bool:
        """
        Execute only NanoTel analysis.

        Args:
            fastq_input: Path to FASTQ directory

        Returns:
            True if succeeds, False otherwise
        """
        self.context.logger.section_header("NANOTEL ANALYSIS ONLY")

        result = self.nanotel.execute(fastq_input)
        self.results['nanotel'] = result

        if result.success:
            self.context.logger.info("✓ NanoTel analysis completed")
            self.context.logger.info(f"Output: {result.get_output('nanotel_output')}")

        return result.success

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

        result = self.aligner.execute(fastq_input, organism)
        self.results['aligner'] = result

        if result.success:
            self.context.logger.info("✓ Alignment completed")
            self.context.logger.info(f"Output: {result.get_output('aligned_dir')}")

        return result.success

    def run_r_analysis_only(self,
                           run_filtration: bool = True,
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

        result = self.r_analyzer.execute(
            run_filtration=run_filtration,
            run_mapping=run_mapping,
            run_methylation=run_methylation
        )
        self.results['r_analyzer'] = result

        if result.success:
            self.context.logger.info("✓ R analysis completed")
            if run_filtration:
                self.context.logger.info(f"Filtered summaries: {result.get_output('nanotel_filtered')}")
            if run_mapping:
                self.context.logger.info(f"Mapping output: {result.get_output('mapping_output')}")
            if run_methylation:
                self.context.logger.info(f"Methylation output: {result.get_output('methylation_output')}")

        return result.success

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