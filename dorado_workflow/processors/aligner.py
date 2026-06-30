"""
Alignment Processor Module
==========================

Handles alignment of BAM or FASTQ files to reference genome using minimap2.
"""

from pathlib import Path
from typing import Dict, Optional
from .base import ProcessorBase, ProcessorResult, WorkflowContext
from datetime import datetime
import os
import re
import shutil
import subprocess
import shlex

class AlignmentProcessor(ProcessorBase):
    """
    Processor for running minimap2 alignment.

    Responsibilities:
    - Validate input directory exists and contains BAM/FASTQ files
    - Auto-detect input type (BAM or FASTQ)
    - Build alignment command with appropriate parameters
    - Execute alignment to reference genome
    - Track output and collect statistics

    Configuration used:
    - reference genome path (organism-specific)
    - minimap2 preset
    """

    def __init__(self, context: WorkflowContext):
        """
        Initialize alignment processor.

        Args:
            context: WorkflowContext with all shared resources
        """
        super().__init__(context)

        # Define output directory
        self.output_dir = self.context.path_manager.get_aligned_dir_path()

    def validate_inputs(self, input_dir: str, organism: str = "mouse",
                        use_existing_alignment: bool = False) -> bool:
        """
        Validate that all prerequisites for alignment are met.

        Args:
            input_dir: Path to directory containing BAM or FASTQ files
            organism: Organism type ('mouse' or 'human') for reference selection

        Returns:
            True if validation passes, False otherwise
        """
        self.context.logger.info("Validating alignment inputs...")

        # Check if input directory exists
        input_path = Path(input_dir)
        if not input_path.exists():
            self.context.logger.error(f"Input directory not found: {input_dir}")
            return False

        if not input_path.is_dir():
            self.context.logger.error(f"Input path is not a directory: {input_dir}")
            return False

        # Check if alignment tools are available
        required_tools = ['samtools'] if use_existing_alignment else ['minimap2', 'samtools']
        if not self.context.validate_tools(required_tools):
            return False

        if not use_existing_alignment:
            # Validate reference path exists
            reference_path = self.context.config_manager.get_reference_path(organism)
            if not Path(reference_path).exists():
                self.context.logger.error(f"Reference genome not found: {reference_path}")
                return False

        # Check if input directory contains BAM or FASTQ files
        input_type = self._detect_input_type(input_path)
        if not input_type:
            self.context.logger.error(f"No BAM or FASTQ files found in: {input_dir}")
            return False

        if use_existing_alignment and input_type != "bam":
            self.context.logger.error(
                "Existing alignment mode requires aligned BAM input."
            )
            return False

        self.context.logger.info(f"Detected input type: {input_type}")

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.context.logger.info("✓ All alignment prerequisites validated")
        return True

    def execute(self, input_dir: str, organism: str = "mouse",
                input_type: str = "auto",
                use_existing_alignment: bool = False) -> ProcessorResult:
        """
        Execute the alignment process.

        Args:
            input_dir: Path to directory containing BAM or FASTQ files
            organism: Organism type ('mouse' or 'human') for reference selection
            input_type: 'bam', 'fastq', or 'auto' (auto-detect)

        Returns:
            ProcessorResult with success status, output directory, and statistics
        """
        self.log_start()

        # Validate inputs first
        if not self.validate_inputs(input_dir, organism, use_existing_alignment):
            result = ProcessorResult(
                success=False,
                error="Input validation failed"
            )
            self.log_complete(result)
            return result

        try:
            # Auto-detect input type if needed
            if input_type == "auto":
                input_type = self._detect_input_type(Path(input_dir))
                self.context.logger.info(f"Auto-detected input type: {input_type}")

            if use_existing_alignment:
                self.context.logger.info("Preparing existing aligned BAM files")
                aligned_bams = self._stage_existing_aligned_bams(Path(input_dir))
            else:
                prepared_input = self._prepare_alignment_input(Path(input_dir), input_type)

                self.context.logger.info(
                    f"Running minimap2 alignment ({input_type.upper()} input)"
                )
                aligned_bams = self._run_minimap2_alignment(prepared_input, organism, input_type)
            self._write_alignment_summary(aligned_bams)

            # Collect statistics
            stats = self._collect_statistics(input_type)

            # Create successful result
            result = ProcessorResult(
                success=True,
                output_paths={
                    'output_dir': self.output_dir,
                    'aligned_dir': self.output_dir
                },
                statistics=stats
            )

            self.context.logger.info(f"Alignment output: {self.output_dir}")
            self.log_complete(result)
            return result

        except Exception as e:
            error_msg = f"Alignment failed: {str(e)}"
            self.context.logger.error(error_msg)
            result = ProcessorResult(
                success=False,
                error=error_msg
            )
            self.log_complete(result)
            return result

    def _run_minimap2_alignment(self, input_dir: Path, organism: str, input_type: str) -> list[Path]:
        """
        Align all input files with minimap2 and return sorted BAM paths.
        """
        config = self.context.config_manager
        alignment_params = config.get_alignment_params()
        reference = Path(config.get_reference_path(organism))
        preset = alignment_params.get("minimap_preset", "map-ont")

        input_files = self._find_alignment_inputs(input_dir, input_type)
        if not input_files:
            raise RuntimeError(f"No {input_type.upper()} files found for alignment in: {input_dir}")

        aligned_bams = []
        for index, input_file in enumerate(input_files, 1):
            barcode = self._extract_barcode(input_file) or f"{input_type}{index:02d}"
            output_bam = self.output_dir / f"aligned_{barcode}_{index}.bam"
            self._align_one_file(input_file, output_bam, reference, preset, input_type)
            self._index_bam(output_bam)
            aligned_bams.append(output_bam)

        return aligned_bams

    def _stage_existing_aligned_bams(self, input_dir: Path) -> list[Path]:
        """
        Link or copy already-aligned BAM files into the workflow aligned directory.
        """
        bam_files = self._find_barcode_bams(input_dir)
        if not bam_files:
            raise RuntimeError(f"No barcode BAM files found in: {input_dir}")

        staged_bams = []
        for index, bam_file in enumerate(bam_files, 1):
            barcode = self._extract_barcode(bam_file) or f"bam{index:02d}"
            destination = self.output_dir / f"aligned_{barcode}_{index}.bam"
            self._link_or_copy_bam(bam_file, destination)
            self._index_bam(destination)
            staged_bams.append(destination)

        self.context.logger.info(
            f"Prepared {len(staged_bams)} existing aligned BAM files for mapping"
        )
        return staged_bams

    def _find_alignment_inputs(self, input_dir: Path, input_type: str) -> list[Path]:
        if input_type == "bam":
            return self._find_barcode_bams(input_dir)

        return sorted(
            path for path in input_dir.rglob("*")
            if path.is_file()
            and (
                path.name.lower().endswith(".fastq")
                or path.name.lower().endswith(".fastq.gz")
                or path.name.lower().endswith(".fq")
                or path.name.lower().endswith(".fq.gz")
            )
        )

    def _align_one_file(self, input_file: Path, output_bam: Path,
                        reference: Path, preset: str, input_type: str) -> None:
        if input_type == "bam":
            command_text = (
                f"samtools fastq {self._quote_shell_path(input_file)} | "
                f"minimap2 -ax {preset} {self._quote_shell_path(reference)} - | "
                f"samtools sort -o {self._quote_shell_path(output_bam)} -"
            )
        else:
            command_text = (
                f"minimap2 -ax {preset} {self._quote_shell_path(reference)} "
                f"{self._quote_shell_path(input_file)} | "
                f"samtools sort -o {self._quote_shell_path(output_bam)} -"
            )

        self.context.logger.info(f"Alignment command: {command_text}", gui_visible=False)
        self.context.command_executor.execute(
            command_text,
            stream_output=True,
            gui_output_filter=self._show_minimap_gui_line,
        )

        if not output_bam.exists() or output_bam.stat().st_size == 0:
            raise RuntimeError(f"Alignment produced no BAM output: {output_bam}")

    def _index_bam(self, bam_path: Path) -> None:
        command = self._format_command(["samtools", "index", str(bam_path)])
        self.context.command_executor.execute(command, capture_output=True)

    def _write_alignment_summary(self, bam_paths: list[Path]) -> Path:
        summary_path = self.output_dir / "alignment_summary.txt"
        header = [
            "read_id",
            "alignment_direction",
            "alignment_genome",
            "alignment_genome_start",
            "alignment_genome_end",
            "alignment_mapq",
        ]

        with summary_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("\t".join(header) + "\n")
            for bam_path in bam_paths:
                command = self._format_command(["samtools", "view", str(bam_path)])
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for line in process.stdout or []:
                    line = line.rstrip()
                    fields = line.split("\t")
                    if len(fields) < 6:
                        continue
                    read_id = fields[0]
                    flag = int(fields[1])
                    reference = fields[2]
                    start = fields[3]
                    mapq = fields[4]
                    cigar = fields[5]

                    if flag & 4 or reference == "*":
                        direction = "*"
                        end = ""
                    else:
                        direction = "-" if flag & 16 else "+"
                        end = str(int(start) + self._cigar_reference_length(cigar) - 1)

                    handle.write("\t".join([
                        read_id,
                        direction,
                        reference,
                        start,
                        end,
                        mapq,
                    ]) + "\n")
                stderr = process.stderr.read() if process.stderr else ""
                returncode = process.wait()
                if returncode:
                    raise subprocess.CalledProcessError(
                        returncode,
                        command,
                        stderr=stderr,
                    )

        self.context.logger.info(f"Alignment summary: {summary_path}")
        return summary_path

    @staticmethod
    def _cigar_reference_length(cigar: str) -> int:
        if not cigar or cigar == "*":
            return 0
        length = 0
        for count, op in re.findall(r"(\d+)([MIDNSHP=X])", cigar):
            if op in {"M", "D", "N", "=", "X"}:
                length += int(count)
        return length

    def _prepare_alignment_input(self, input_path: Path, input_type: str) -> Path:
        if input_type != "bam":
            return input_path

        bam_files = self._find_barcode_bams(input_path)
        if not bam_files:
            raise RuntimeError(f"No barcode BAM files found for alignment in: {input_path}")

        staging_root = self.context.path_manager.get_processing_dir_path() / "alignment_input"
        staging_dir = staging_root / datetime.now().strftime("%Y-%m-%d_T%H-%M-%S")

        try:
            for index, bam_file in enumerate(bam_files, 1):
                staging_dir.mkdir(parents=True, exist_ok=True)
                barcode = self._extract_barcode(bam_file) or f"bam{index:02d}"
                link_path = staging_dir / f"{barcode}_{index}_{bam_file.name}"
                self._link_or_copy_bam(bam_file, link_path)
        except Exception:
            if staging_dir.exists() and not any(staging_dir.iterdir()):
                staging_dir.rmdir()
            raise

        self.context.logger.info(
            f"Prepared {len(bam_files)} barcode BAM files for alignment",
            gui_visible=False,
        )
        return staging_dir

    def _find_barcode_bams(self, input_path: Path) -> list[Path]:
        bam_files = [
            path for path in input_path.rglob("*")
            if path.is_file()
            and path.suffix.lower() == ".bam"
            and self._extract_barcode(path)
            and not self._is_skipped_bam(path)
        ]
        return sorted(bam_files)

    @staticmethod
    def _extract_barcode(path: Path) -> Optional[str]:
        match = re.search(r"(?:barcode|bc)(\d+)", str(path), re.IGNORECASE)
        if not match:
            return None
        return f"barcode{int(match.group(1)):02d}"

    @staticmethod
    def _is_skipped_bam(path: Path) -> bool:
        lowered = str(path).lower()
        return "unclassified" in lowered or "/mix/" in lowered or "\\mix\\" in lowered

    @staticmethod
    def _link_or_copy_bam(source: Path, destination: Path) -> None:
        try:
            destination.symlink_to(source)
        except OSError:
            try:
                os.link(source, destination)
            except OSError:
                shutil.copy2(source, destination)

    def _format_command(self, cmd_parts: list) -> str:
        args = [str(part) for part in cmd_parts]
        if os.name == "nt":
            return subprocess.list2cmdline(args)
        return shlex.join(args)

    def _quote_shell_path(self, path: Path) -> str:
        if os.name == "nt":
            return subprocess.list2cmdline([str(path)])
        return shlex.quote(str(path))

    def _detect_input_type(self, input_path: Path) -> Optional[str]:
        """
        Auto-detect if input directory contains BAM or FASTQ files.

        Args:
            input_path: Path to input directory

        Returns:
            'bam', 'fastq', or None if no files found
        """
        # Look for files recursively (in case of barcode subdirectories)
        bam_files = [
            path for path in input_path.rglob("*")
            if path.is_file() and path.suffix.lower() == ".bam"
        ]
        fastq_files = [
            path for path in input_path.rglob("*")
            if path.is_file()
            and (
                path.name.lower().endswith(".fastq")
                or path.name.lower().endswith(".fastq.gz")
                or path.name.lower().endswith(".fq")
                or path.name.lower().endswith(".fq.gz")
            )
        ]

        if bam_files and not fastq_files:
            return "bam"
        elif fastq_files and not bam_files:
            return "fastq"
        elif bam_files and fastq_files:
            # Both exist - prefer BAM (more processed)
            self.context.logger.warning("Both BAM and FASTQ files found, using BAM files")
            return "bam"
        else:
            return None

    def _collect_statistics(self, input_type: str) -> Dict[str, any]:
        """
        Collect statistics about the alignment output.

        Args:
            input_type: Type of input files used

        Returns:
            Dictionary of statistics
        """
        stats = {
            'input_type': input_type,
        }

        # Count output files if directory exists
        if self.output_dir.exists():
            aligned_files = list(self.output_dir.rglob("*"))
            stats['output_file_count'] = len(aligned_files)

            # Count specific file types
            bam_files = [path for path in self.output_dir.rglob("*") if path.suffix.lower() == ".bam"]
            summary_files = list(self.output_dir.rglob("*summary*"))

            stats['aligned_bam_count'] = len(bam_files)
            stats['summary_file_count'] = len(summary_files)

        return stats

    def get_output_paths(self) -> Dict[str, Path]:
        """
        Get the expected output paths for this processor.

        Returns:
            Dictionary with 'output_dir' key
        """
        return {
            'output_dir': self.output_dir
        }

    def get_aligned_files(self) -> list[Path]:
        """
        Get all aligned BAM files.

        Returns:
            List of aligned BAM file paths
        """
        if not self.output_dir.exists():
            return []

        return [path for path in self.output_dir.rglob("*") if path.suffix.lower() == ".bam"]

    @staticmethod
    def _show_minimap_gui_line(line: str) -> bool:
        lower = line.lower()
        return (
            "[error]" in lower
            or "[warning]" in lower
            or "error" in lower
            or "warn" in lower
        )
