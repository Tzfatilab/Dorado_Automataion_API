"""
BAM to FASTQ Converter Processor Module
========================================

Converts demuxed per-barcode BAM files to FASTQ format using samtools.
Required step between demuxing and NanoTel analysis.
"""

from pathlib import Path
from typing import Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from processors.base import ProcessorBase, ProcessorResult, WorkflowContext

class BamToFastqProcessor(ProcessorBase):
    """
    Processor for converting demuxed BAM files to FASTQ format.

    Responsibilities:
    - Find all per-barcode BAM files in demuxed directory
    - Convert each BAM to FASTQ using samtools
    - Organize output into per-barcode FASTQ directories
    - Run conversions in parallel for speed

    Requires: samtools
    Input:  processing/demultiplexed/barcode01/file.bam
    Output: processing/fastq/barcode01/barcode01.fastq
    """

    def __init__(self, context: WorkflowContext):
        super().__init__(context)
        self.output_dir = self.context.path_manager.get_fastq_dir_path()
        self.converter = None

    def validate_inputs(self, demuxed_dir: str) -> bool:
        self.context.logger.info("Validating BAM to FASTQ conversion inputs...")

        demuxed_path = Path(demuxed_dir)
        if not demuxed_path.exists():
            self.context.logger.error(f"Demuxed directory not found: {demuxed_dir}")
            return False

        # Check for BAM files
        bam_files = list(demuxed_path.rglob("*.bam"))
        if not bam_files:
            self.context.logger.error(f"No BAM files found in: {demuxed_dir}")
            return False

        self.context.logger.info(f"Found {len(bam_files)} BAM files")

        if self.context.command_executor.check_tool_available('samtools'):
            self.converter = 'samtools'
        else:
            try:
                import pysam  # noqa: F401
                self.converter = 'pysam'
                self.context.logger.info(
                    "samtools is unavailable; using the Python BAM reader instead."
                )
            except ImportError:
                self.context.logger.error(
                    "BAM conversion requires samtools or the Python package pysam. "
                    "Install pysam with: pip install pysam"
                )
                return False

        self.context.logger.info("✓ All BAM to FASTQ prerequisites validated")
        return True

    def execute(self, demuxed_dir: str) -> ProcessorResult:
        self.log_start()

        if not self.validate_inputs(demuxed_dir):
            result = ProcessorResult(success=False, error="Input validation failed")
            self.log_complete(result)
            return result

        try:
            demuxed_path = Path(demuxed_dir)
            SKIP_FOLDERS = {'unclassified', 'mix'}

            # Find all barcode directories
            barcode_dirs = [
                d for d in demuxed_path.iterdir()
                if d.is_dir() and d.name not in SKIP_FOLDERS
            ]

            if not barcode_dirs:
                result = ProcessorResult(success=False, error="No barcode directories found")
                self.log_complete(result)
                return result

            self.context.logger.info(f"Converting BAMs for {len(barcode_dirs)} barcodes...")

            # Build conversion tasks
            tasks = []
            for barcode_dir in barcode_dirs:
                barcode_name = barcode_dir.name
                bam_files = list(barcode_dir.glob("*.bam"))

                if not bam_files:
                    self.context.logger.warning(f"No BAM files in {barcode_name}, skipping")
                    continue

                # Output FASTQ directory for this barcode
                fastq_dir = self.output_dir / barcode_name
                fastq_dir.mkdir(parents=True, exist_ok=True)

                for i, bam_file in enumerate(bam_files, 1):
                    output_fastq = fastq_dir / f"{barcode_name}_{i}.fastq"
                    tasks.append({
                        'barcode': barcode_name,
                        'bam_file': bam_file,
                        'output_fastq': output_fastq
                    })

            # Run conversions in parallel
            results_per_barcode = self._convert_parallel(tasks)

            stats = {
                'total_barcodes': len(barcode_dirs),
                'successful_conversions': sum(1 for v in results_per_barcode.values() if v),
                'failed_conversions': sum(1 for v in results_per_barcode.values() if not v),
            }

            result = ProcessorResult(
                success=True,
                output_paths={'fastq_dir': self.output_dir},
                statistics=stats
            )

            self.context.logger.info(
                f"BAM to FASTQ conversion complete: "
                f"{stats['successful_conversions']}/{stats['total_barcodes']} barcodes"
            )
            self.log_complete(result)
            return result

        except Exception as e:
            error_msg = f"BAM to FASTQ conversion failed: {str(e)}"
            self.context.logger.error(error_msg)
            result = ProcessorResult(success=False, error=error_msg)
            self.log_complete(result)
            return result

    def _convert_parallel(self, tasks: list, max_workers: int = 4) -> Dict[str, bool]:
        results = {}

        if not tasks:
            return results

        def convert_single(task):
            try:
                if self.converter == 'samtools':
                    command = f"samtools fastq {task['bam_file']} > {task['output_fastq']}"
                    self.context.command_executor.execute(command)
                else:
                    self._convert_with_pysam(task['bam_file'], task['output_fastq'])
                self.context.logger.info(
                    f"✓ {task['barcode']}: {task['bam_file'].name} → {task['output_fastq'].name}"
                )
                return task['barcode'], True
            except Exception as e:
                self.context.logger.error(
                    f"✗ {task['barcode']}: Failed - {str(e)}"
                )
                return task['barcode'], False

        with ThreadPoolExecutor(max_workers=min(max_workers, len(tasks))) as executor:
            futures = {executor.submit(convert_single, task): task for task in tasks}
            for future in as_completed(futures):
                barcode, success = future.result()
                results[barcode] = success

        return results

    @staticmethod
    def _convert_with_pysam(bam_file: Path, output_fastq: Path) -> None:
        """Write primary BAM reads as FASTQ without requiring a samtools executable."""
        import pysam

        with pysam.AlignmentFile(str(bam_file), "rb", check_sq=False) as bam, \
             output_fastq.open("w", encoding="utf-8", newline="\n") as fastq:
            for read in bam.fetch(until_eof=True):
                if read.is_secondary or read.is_supplementary:
                    continue
                sequence = read.query_sequence
                if not sequence:
                    continue
                qualities = read.qual or "I" * len(sequence)
                fastq.write(f"@{read.query_name}\n{sequence}\n+\n{qualities}\n")

    def get_output_paths(self) -> Dict[str, Path]:
        return {'fastq_dir': self.output_dir}
