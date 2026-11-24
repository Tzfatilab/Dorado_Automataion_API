"""
Alignment Processor Module
==========================

Handles alignment of BAM or FASTQ files to reference genome using minimap2.
"""

from pathlib import Path
from typing import Dict, Optional
from .base import ProcessorBase, ProcessorResult, WorkflowContext
from ..utils.cancellation import WorkflowCancelled
from ..utils.source_links import link_source
from ..utils.shell_commands import format_command
from datetime import datetime
import os
import re
import shutil
import subprocess
import tempfile

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
        """Initialize alignment processor.

        Args:
            context: WorkflowContext with all shared resources

        Returns:
            None; initializes the instance.
        """
        super().__init__(context)

        # Define output directory
        self.output_dir = self.context.path_manager.get_aligned_dir_path()

    def validate_inputs(self, input_dir: str, organism: str = "mouse",
                        use_existing_alignment: bool = False) -> bool:
        """Validate that all prerequisites for alignment are met.

        Args:
            input_dir: Path to directory containing BAM or FASTQ files
            organism: Organism type ('mouse' or 'human') for reference selection
            use_existing_alignment: bool; whether to reuse aligned BAMs instead of running minimap2. Default: False.

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
                use_existing_alignment: bool = False, link_inputs_only: bool = False,
                nanotel_sources=None) -> ProcessorResult:
        """Execute the alignment process.

        Args:
            input_dir: Path to directory containing BAM or FASTQ files
            organism: Organism type ('mouse' or 'human') for reference selection
            input_type: 'bam', 'fastq', or 'auto' (auto-detect)
            link_inputs_only: Reject copying existing BAMs if linking fails;
                used by recalculation to avoid duplicating saved inputs.
            use_existing_alignment: bool; whether to reuse aligned BAMs instead of running minimap2. Default: False.

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

            if nanotel_sources is not None:
                # Fresh non-methylation workflows supply the exact successful
                # NanoTel tasks. Saved-project reanalysis supplies no tasks and
                # continues through the existing BAM-linking path below.
                if use_existing_alignment or link_inputs_only:
                    raise ValueError("Fresh subtelomeric mapping cannot reuse whole-read alignments.")
                aligned_bams = self._run_subtelomeric_alignment(nanotel_sources, organism)
            elif use_existing_alignment:
                self.context.logger.info("Preparing existing aligned BAM files")
                aligned_bams = self._stage_existing_aligned_bams(Path(input_dir), link_inputs_only=link_inputs_only)
            else:
                prepared_input = self._prepare_alignment_input(
                    Path(input_dir), input_type, link_inputs_only=link_inputs_only
                )

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

        except WorkflowCancelled:
            raise
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
        """Align all input files with minimap2 and return sorted BAM paths.

        Args:
            input_dir: Path; directory containing input files.
            organism: str; organism label selecting reference and analysis defaults.
            input_type: str; selected input kind, such as BAM, FASTQ or auto.

        Returns:
            Ordered paths to the sorted and indexed aligned BAM files.
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

    def _stage_existing_aligned_bams(self, input_dir: Path, *, link_inputs_only=False) -> list[Path]:
        """Stage existing BAMs and create indexes only in the new run directory.

        Recalculation sets link_inputs_only so large BAMs never silently fall
        back to a full copy when filesystem links are unavailable.

        Args:
            input_dir: Path; directory containing input files.
            link_inputs_only: Whether to reject copying if source-file linking fails. Default: False.

        Returns:
            Paths to existing BAMs staged in the new aligned directory.
        """
        bam_files = self._find_barcode_bams(input_dir)
        if not bam_files:
            raise RuntimeError(f"No barcode BAM files found in: {input_dir}")

        staged_bams = []
        for index, bam_file in enumerate(bam_files, 1):
            barcode = self._extract_barcode(bam_file) or f"bam{index:02d}"
            destination = self.output_dir / f"aligned_{barcode}_{index}.bam"
            if link_inputs_only:
                link_source(bam_file, destination)
            else:
                self._link_or_copy_bam(bam_file, destination)
            self._index_bam(destination)
            staged_bams.append(destination)

        self.context.logger.info(
            f"Prepared {len(staged_bams)} existing aligned BAM files for mapping"
        )
        return staged_bams

    def _find_alignment_inputs(self, input_dir: Path, input_type: str) -> list[Path]:
        """Find alignment inputs.

        Args:
            input_dir: Path; directory containing input files.
            input_type: str; selected input kind, such as BAM, FASTQ or auto.

        Returns:
            list[Path]: Sorted list of matching values.
        """
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
        """Align one file.

        Args:
            input_file: Path; one source file to process.
            output_bam: Path; destination for the generated BAM.
            reference: Path; reference path or exported reference label.
            preset: str; minimap2 alignment preset.
            input_type: str; selected input kind, such as BAM, FASTQ or auto.

        Returns:
            None.
        """
        temporary_bam = output_bam.with_name(f"{output_bam.name}.tmp.bam")
        if input_type == "bam":
            # Carry modification tags through FASTQ comments; soft clipping
            # keeps supplementary alignments consistent with the MM/MN tags.
            commands = [
                ["samtools", "fastq", "-T", "MM,ML,Mm,Ml,MN", input_file],
                ["minimap2", "-y", "-Y", "-ax", preset, reference, "-"],
            ]
        else:
            commands = [["minimap2", "-ax", preset, reference, input_file]]
        commands.append(["samtools", "sort", "-o", temporary_bam, "-"])

        try:
            self.context.command_executor.execute_pipeline(
                commands, gui_output_filter=self._show_minimap_gui_line
            )
            if not temporary_bam.exists() or temporary_bam.stat().st_size == 0:
                raise RuntimeError(f"Alignment produced no BAM output: {output_bam}")
            # Never publish a partial BAM if an upstream tool failed.
            temporary_bam.replace(output_bam)
        finally:
            if temporary_bam.exists():
                temporary_bam.unlink()

    def _index_bam(self, bam_path: Path) -> None:
        """Index bam.

        Args:
            bam_path: Path; bam path.

        Returns:
            None.
        """
        command = format_command(["samtools", "index", str(bam_path)])
        self.context.command_executor.execute(command, capture_output=True)

    def _run_subtelomeric_alignment(self, sources, organism):
        """Map NanoTel's before-filter subtelomeric exports, one barcode at a time.

        NanoTel supplies exact source paths, so barcode identity and input files
        are not rediscovered from report folders. NanoTel owns sequence cutting;
        Python only validates the export and restores alignment coordinates.
        """
        from ..utils.subtelomeric_inputs import prepare_subtelomeric_inputs

        if not sources or len({source['barcode'] for source in sources}) != len(sources):
            raise ValueError("Unique successful NanoTel barcode sources are required.")
        params = self.context.config_manager.get_nanotel_params()
        # Use the boundary method actually requested for this fresh detection:
        # combined canonical + variants (including TSQ), otherwise canonical
        # with mismatch, otherwise exact canonical. This selects saved columns;
        # it neither recalculates boundaries nor changes filtering thresholds.
        method = ('variant_inclusive' if params.get('tvr_patterns') else
                  'mismatch' if int(params.get('max_mismatch', 0)) else 'exact')
        bams = []
        for source in sources:
            self.context.command_executor.check_cancelled()
            prepared = prepare_subtelomeric_inputs(source['summary_csv'], source['subtelomeric_fasta'],
                boundary_method=method, check_cancelled=self.context.command_executor.check_cancelled)
            if prepared.barcode != source['barcode']:
                raise ValueError("NanoTel source barcode disagrees with the mapping task.")
            self.context.logger.info(f"{prepared.barcode}: {prepared.queries} subtelomeric queries; "
                f"{prepared.no_subtelomere} without a flank; {prepared.missing_boundary} without a boundary")
            directory = self.align_prepared_subtelomeric(prepared, organism)
            bams.extend(sorted(directory.glob('*.bam')))
        return bams

    def align_prepared_subtelomeric(self, prepared, organism: str) -> Path:
        """Map a prepared barcode and save alignments on the original-read axis.

        Original full-read and methylation BAMs are never edited or reused as output.
        Publish a new barcode directory only after mapping, projection, sorting,
        indexing and summary generation succeed.
        """
        from ..utils.subtelomeric_alignments import validate_query_coordinates, project_subtelomeric_sam
        from ..utils.subtelomeric_inputs import PreparedSubtelomericInputs

        executor = self.context.command_executor
        executor.check_cancelled()
        if not isinstance(prepared, PreparedSubtelomericInputs):
            raise TypeError("Pass the in-memory result of prepare_subtelomeric_inputs.")
        barcode = prepared.barcode
        if not re.fullmatch(r"barcode\d+", barcode):
            raise ValueError("Invalid subtelomeric preparation barcode.")
        queries = prepared.coordinates
        validate_query_coordinates(queries)
        if not self.context.validate_tools(["minimap2", "samtools"]):
            raise RuntimeError("Minimap2 and samtools are required for subtelomeric alignment.")
        config = self.context.config_manager
        reference = Path(config.get_reference_path(organism))
        if not reference.is_file():
            raise ValueError(f"Reference genome not found: {reference}")
        preset = config.get_alignment_params().get("minimap_preset", "map-ont")
        destination = self.output_dir / "subtelomeric" / barcode
        if destination.exists():
            raise FileExistsError(f"Subtelomeric alignment output already exists: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.context.logger.info(f"Subtelomeric alignment: {barcode}, {len(queries)} prepared queries")
        with tempfile.TemporaryDirectory(prefix=".subtelomeric-alignment-", dir=destination.parent) as temporary:
            staged = Path(temporary) / barcode
            staged.mkdir()
            bams = []
            counts = dict(mapped=0, unmapped=0)
            if queries:
                # Minimap2 sees only the extracted flank. Project its SAM back
                # to full-read coordinates before sorting/indexing, so R and
                # the dashboard can keep using their existing coordinate code.
                raw_sam = staged / "query.sam"
                projected_sam = staged / "original_read.sam"
                executor.execute_pipeline([["minimap2", "-ax", preset, "-o", raw_sam,
                    reference, prepared.fasta]],
                    gui_output_filter=self._show_minimap_gui_line)
                counts = project_subtelomeric_sam(raw_sam, projected_sam, queries, executor.check_cancelled)
                bam = staged / f"aligned_{barcode}.bam"
                executor.execute_pipeline([["samtools", "sort", "-o", bam, projected_sam]])
                executor.execute(format_command(["samtools", "quickcheck", bam]), capture_output=True)
                self._index_bam(bam)
                bams.append(bam)
                # SAM intermediates are not retained; the indexed BAM and
                # alignment summary are sufficient for later re-filtering.
                raw_sam.unlink()
                projected_sam.unlink()
            else:
                self.context.logger.warning(f"{barcode}: no available subtelomeric queries to align.")
                # A real empty BAM preserves this barcode in saved mapping inputs
                # and lets reanalysis distinguish zero reads from missing files.
                empty_sam = staged / 'empty.sam'
                empty_sam.write_text('@HD\tVN:1.6\tSO:coordinate\n'
                    '@CO\tmapping_mode=subtelomeric; no available queries\n', encoding='utf-8')
                bam = staged / f'aligned_{barcode}.bam'
                executor.execute_pipeline([['samtools', 'view', '-b', '-o', bam, empty_sam]])
                executor.execute(format_command(['samtools', 'quickcheck', '-u', bam]), capture_output=True)
                self._index_bam(bam)
                bams.append(bam)
                empty_sam.unlink()
            self._write_alignment_summary(bams, output_dir=staged)
            executor.check_cancelled()
            if destination.exists():
                raise FileExistsError(f"Subtelomeric alignment output already exists: {destination}")
            os.rename(staged, destination)
        self.context.logger.info(f"Subtelomeric alignment saved: {destination} "
            f"({counts['mapped']} mapped and {counts['unmapped']} unmapped alignment records)")
        return destination

    def _write_alignment_summary(self, bam_paths: list[Path], output_dir: Optional[Path] = None) -> Path:
        """Path to the tab-separated alignment summary.

        Args:
            bam_paths: list[Path]; aligned BAM paths included in the exported summary.

        Returns:
            Path to the tab-separated alignment summary.
        """
        summary_path = Path(output_dir if output_dir is not None else self.output_dir) / "alignment_summary.txt"
        header = [
            "read_id",
            "alignment_direction",
            "alignment_genome",
            "alignment_genome_start",
            "alignment_genome_end",
            "alignment_mapq",
            "alignment_cigar",
            "alignment_coordinate_convention",
            "alignment_query_start",
            "alignment_query_end",
            "alignment_query_length",
            "alignment_query_convention",
            "alignment_query_space",
        ]

        with summary_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("\t".join(header) + "\n")
            for bam_path in bam_paths:
                command = format_command(["samtools", "view", str(bam_path)])
                process = self.context.command_executor.popen(
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
                    query = None

                    if flag & 4 or reference == "*":
                        direction = "*"
                        end = ""
                    else:
                        direction = "-" if flag & 16 else "+"
                        end = str(int(start) + self._cigar_reference_length(cigar) - 1)
                        query = self._cigar_query_interval(cigar, reverse=bool(flag & 16))

                    handle.write("\t".join([
                        read_id,
                        direction,
                        reference,
                        start,
                        end,
                        mapq,
                        cigar,
                        "one_based_inclusive",
                        *([str(value) for value in query] if query else ["", "", ""]),
                        "zero_based_half_open" if query else "",
                        "original_read" if query else "",
                    ]) + "\n")
                stderr = process.stderr.read() if process.stderr else ""
                returncode = process.wait()
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()
                self.context.command_executor.check_cancelled()
                if returncode:
                    raise subprocess.CalledProcessError(
                        returncode,
                        command,
                        stderr=stderr,
                    )

        self.context.logger.info(f"Alignment summary: {summary_path}")
        return summary_path

    @staticmethod
    def _cigar_query_interval(cigar: str, reverse: bool = False):
        """Aligned bounding span on the original read, including hard-clip offsets.

        SAM stores reverse-strand CIGAR in reference-facing orientation. Return
        original-read coordinates so NanoTel's own orientation can be applied
        explicitly later. Insertions consume query bases; deletions do not.

        Args:
            cigar: str; sAM CIGAR string describing aligned and clipped spans.
            reverse: bool; whether the alignment is on the reverse strand. Default: False.

        Returns:
            Tuple containing `start`, `end`, `length`. May be None when no usable result is available.
        """
        if not cigar or not re.fullmatch(r'(?:[1-9]\d*[MIDNSHP=X])+', cigar):
            return None
        ops = [(int(n), op) for n, op in re.findall(r'(\d+)([MIDNSHP=X])', cigar)]
        core = [i for i, (_, op) in enumerate(ops) if op not in {'S', 'H'}]
        if not core or any(op in {'S', 'H'} for _, op in ops[core[0]:core[-1]+1]):
            return None
        leading = sum(n for n, _ in ops[:core[0]])
        aligned = sum(n for n, op in ops[core[0]:core[-1]+1] if op in {'M', 'I', '=', 'X'})
        length = sum(n for n, op in ops if op in {'M', 'I', 'S', 'H', '=', 'X'})
        if not aligned:
            return None
        start, end = leading, leading + aligned
        if reverse:
            start, end = length-end, length-start
        return start, end, length

    @staticmethod
    def _cigar_reference_length(cigar: str) -> int:
        """Cigar reference length.

        Args:
            cigar: str; sAM CIGAR string describing aligned and clipped spans.

        Returns:
            int: Integer value.
        """
        if not cigar or cigar == "*":
            return 0
        length = 0
        for count, op in re.findall(r"(\d+)([MIDNSHP=X])", cigar):
            if op in {"M", "D", "N", "=", "X"}:
                length += int(count)
        return length

    def _prepare_alignment_input(self, input_path: Path, input_type: str,
                                 *, link_inputs_only: bool = False) -> Path:
        """Flatten barcode BAM paths for alignment without changing their contents.

        Args:
            input_path: Path; input path.
            input_type: str; selected input kind, such as BAM, FASTQ or auto.
            link_inputs_only: Reject copying saved BAM inputs when linking fails.

        Returns:
            Directory containing FASTQ inputs or staged barcode BAM files.
        """
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
                if link_inputs_only:
                    link_source(bam_file, link_path)
                else:
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
        """Find barcode bams.

        Args:
            input_path: Path; input path.

        Returns:
            list[Path]: Sorted list of matching values.
        """
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
        """Extract barcode.

        Args:
            path: Path; file or directory path.

        Returns:
            Optional[str]: Formatted text for the requested output.
        """
        # Prefer explicit barcode labels over abbreviated labels anywhere in
        # the path. A run ID such as bc29e4db is not barcode29.
        parts = re.split(r"[\\/]", str(path))
        for pattern in (r"(?<![A-Za-z0-9])barcode(\d+)(?![A-Za-z0-9])",
                        r"(?<![A-Za-z0-9])bc(\d+)(?![A-Za-z0-9])"):
            for part in reversed(parts):
                match = re.search(pattern, part, re.IGNORECASE)
                if match:
                    return f"barcode{int(match.group(1)):02d}"
        return None

    @staticmethod
    def _is_skipped_bam(path: Path) -> bool:
        """True for BAMs belonging to unclassified or mixed barcode folders.

        Args:
            path: Path; file or directory path.

        Returns:
            True for BAMs belonging to unclassified or mixed barcode folders.
        """
        lowered = str(path).lower()
        return "unclassified" in lowered or "/mix/" in lowered or "\\mix\\" in lowered

    @staticmethod
    def _link_or_copy_bam(source: Path, destination: Path) -> None:
        """Link or copy bam.

        Args:
            source: Path; existing source artifact or source data.
            destination: Path; path where the new output is written.

        Returns:
            None.
        """
        try:
            destination.symlink_to(source)
        except OSError:
            try:
                os.link(source, destination)
            except OSError:
                shutil.copy2(source, destination)


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
        """Get the expected output paths for this processor.

        Returns:
            Dictionary with 'output_dir' key

        Inputs:
            None; uses instance state.
        """
        return {
            'output_dir': self.output_dir
        }

    def get_aligned_files(self) -> list[Path]:
        """Get all aligned BAM files.

        Returns:
            List of aligned BAM file paths

        Inputs:
            None; uses instance state.
        """
        if not self.output_dir.exists():
            return []

        return [path for path in self.output_dir.rglob("*") if path.suffix.lower() == ".bam"]

    @staticmethod
    def _show_minimap_gui_line(line: str) -> bool:
        """True when the minimap2 diagnostic is suitable for GUI display.

        Args:
            line: str; one line of source or process output.

        Returns:
            True when the minimap2 diagnostic is suitable for GUI display.
        """
        lower = line.lower()
        return (
            "[error]" in lower
            or "[warning]" in lower
            or "error" in lower
            or "warn" in lower
        )
