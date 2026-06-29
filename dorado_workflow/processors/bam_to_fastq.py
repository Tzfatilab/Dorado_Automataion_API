"""
BAM to FASTQ Converter Processor Module
========================================

Converts demuxed per-barcode BAM files to FASTQ format using samtools.
Required step between demuxing and NanoTel analysis.
"""

from pathlib import Path
from typing import Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import shlex
import subprocess

from processors.base import ProcessorBase, ProcessorResult, WorkflowContext


class BamToFastqProcessor(ProcessorBase):
    """
    Processor for converting demuxed BAM files to FASTQ format.

    Requires: samtools
    Input:  processing/demultiplexed/barcode01/file.bam
    Output: processing/fastq/barcode01/barcode01.fastq
    """

    def __init__(self, context: WorkflowContext):
        super().__init__(context)
        self.output_dir = self.context.path_manager.get_fastq_dir_path()

    def validate_inputs(self, demuxed_dir: str) -> bool:
        self.context.logger.info("Validating BAM to FASTQ conversion inputs...")

        demuxed_path = Path(demuxed_dir)
        if not demuxed_path.exists():
            self.context.logger.error(f"Demuxed directory not found: {demuxed_dir}")
            return False

        bam_files = list(demuxed_path.rglob("*.bam"))
        if not bam_files:
            self.context.logger.error(f"No BAM files found in: {demuxed_dir}")
            return False

        self.context.logger.info(f"Found {len(bam_files)} BAM files")

        if not self.context.command_executor.check_tool_available("samtools"):
            self.context.logger.error(
                "BAM conversion requires samtools. Install samtools in Windows, "
                "or use FASTQ input to skip BAM conversion."
            )
            return False

        self.context.logger.info("All BAM to FASTQ prerequisites validated")
        return True

    def execute(self, demuxed_dir: str) -> ProcessorResult:
        self.log_start()

        if not self.validate_inputs(demuxed_dir):
            result = ProcessorResult(success=False, error="Input validation failed")
            self.log_complete(result)
            return result

        try:
            demuxed_path = Path(demuxed_dir)
            skip_folders = {"unclassified", "mix"}

            barcode_dirs = [
                d for d in demuxed_path.iterdir()
                if d.is_dir() and d.name not in skip_folders
            ]

            if not barcode_dirs:
                result = ProcessorResult(success=False, error="No barcode directories found")
                self.log_complete(result)
                return result

            self.context.logger.info(f"Converting BAMs for {len(barcode_dirs)} barcodes...")

            tasks = []
            for barcode_dir in barcode_dirs:
                barcode_name = barcode_dir.name
                bam_files = list(barcode_dir.glob("*.bam"))

                if not bam_files:
                    self.context.logger.warning(f"No BAM files in {barcode_name}, skipping")
                    continue

                fastq_dir = self.output_dir / barcode_name
                fastq_dir.mkdir(parents=True, exist_ok=True)

                for i, bam_file in enumerate(bam_files, 1):
                    output_fastq = fastq_dir / f"{barcode_name}_{i}.fastq"
                    tasks.append({
                        "barcode": barcode_name,
                        "bam_file": bam_file,
                        "output_fastq": output_fastq,
                    })

            results_per_barcode = self._convert_parallel(tasks)
            attempted_barcodes = {task["barcode"] for task in tasks}
            skipped_barcodes = len(barcode_dirs) - len(attempted_barcodes)

            stats = {
                "total_barcodes": len(barcode_dirs),
                "attempted_barcodes": len(attempted_barcodes),
                "skipped_barcodes": skipped_barcodes,
                "successful_conversions": sum(1 for v in results_per_barcode.values() if v),
                "failed_conversions": sum(1 for v in results_per_barcode.values() if not v),
            }

            success = stats["failed_conversions"] == 0 and stats["successful_conversions"] > 0
            result = ProcessorResult(
                success=success,
                output_paths={"fastq_dir": self.output_dir},
                statistics=stats,
                error=None if success else (
                    "BAM to FASTQ conversion failed for "
                    f"{stats['failed_conversions']}/{stats['attempted_barcodes']} attempted barcodes"
                ),
            )

            self.context.logger.info(
                "BAM to FASTQ conversion complete: "
                f"{stats['successful_conversions']}/{stats['attempted_barcodes']} barcodes"
            )
            if stats["skipped_barcodes"]:
                self.context.logger.warning(
                    f"Skipped {stats['skipped_barcodes']} barcode folders with no BAM files"
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
                self._run_samtools_fastq(
                    task["bam_file"],
                    task["output_fastq"],
                )

                if not self._has_fastq_output(task["output_fastq"]):
                    raise RuntimeError(
                        f"No FASTQ output was created: {task['output_fastq']}"
                    )

                self.context.logger.info(
                    f"{task['barcode']}: {task['bam_file'].name} -> {task['output_fastq'].name}"
                )
                return task["barcode"], True
            except Exception as e:
                if task["output_fastq"].exists() and task["output_fastq"].stat().st_size == 0:
                    task["output_fastq"].unlink()
                self.context.logger.error(f"{task['barcode']}: Failed - {str(e)}")
                return task["barcode"], False

        with ThreadPoolExecutor(max_workers=min(max_workers, len(tasks))) as executor:
            futures = {executor.submit(convert_single, task): task for task in tasks}
            for future in as_completed(futures):
                barcode, success = future.result()
                results[barcode] = results.get(barcode, True) and success

        return results

    def _run_samtools_fastq(self, bam_file: Path, output_fastq: Path) -> subprocess.CompletedProcess:
        command = self._build_samtools_command(bam_file)
        temp_fastq = output_fastq.with_name(f"{output_fastq.name}.tmp")
        command_text = f"{self._format_command(command)} > {self._quote_path(output_fastq)}"

        self.context.logger.info(f"Running samtools command: {command_text}")
        cmd_index = self.context.logger.register_command(command_text)

        try:
            with temp_fastq.open("w", encoding="utf-8", newline="") as stdout_file:
                result = subprocess.run(
                    command,
                    stdout=stdout_file,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                )

            if not self._has_fastq_output(temp_fastq):
                raise RuntimeError(f"samtools created an empty FASTQ file: {temp_fastq}")

            temp_fastq.replace(output_fastq)
            self.context.logger.mark_command_success(
                cmd_index,
                returncode=result.returncode,
                stderr=result.stderr,
            )
            return result
        except subprocess.CalledProcessError as e:
            self.context.logger.mark_command_failed(
                cmd_index,
                str(e),
                returncode=e.returncode,
                stderr=e.stderr,
            )
            raise
        except Exception as e:
            self.context.logger.mark_command_failed(cmd_index, str(e))
            raise
        finally:
            if temp_fastq.exists():
                temp_fastq.unlink()

    def _build_samtools_command(self, bam_file: Path) -> list:
        return ["samtools", "fastq", str(bam_file)]

    def _format_command(self, cmd_parts: list) -> str:
        args = [str(part) for part in cmd_parts]
        if os.name == "nt":
            return subprocess.list2cmdline(args)
        return shlex.join(args)

    def _quote_path(self, path: Path) -> str:
        if os.name == "nt":
            return subprocess.list2cmdline([str(path)])
        return shlex.quote(str(path))

    @staticmethod
    def _has_fastq_output(output_fastq: Path) -> bool:
        return output_fastq.exists() and output_fastq.stat().st_size > 0

    @staticmethod
    def _format_command_output(result: subprocess.CompletedProcess) -> str:
        details = []
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        if stdout:
            details.append(f"stdout: {stdout}")
        if stderr:
            details.append(f"stderr: {stderr}")
        return f" ({'; '.join(details)})" if details else ""

    def get_output_paths(self) -> Dict[str, Path]:
        return {"fastq_dir": self.output_dir}
