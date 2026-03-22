import traceback
from PySide6.QtCore import QObject, Signal
from dorado_api.pipline import RunPipeline


class WorkerThread(QObject):
    log = Signal(str)
    done = Signal(bool, str)

    def __init__(
        self,
        trial_name: str,
        pod5_path: str = "",
        fastq_path: str = "",
        bam_path: str = "",
        nanotel_path: str = "",
        output_dir: str = "",
        organism: str = "mouse",
        do_pod5: bool = False,
        do_fastq: bool = False,
        do_nanotel: bool = False,
        do_align: bool = False,
        do_r: bool = False,
        run_filtration: bool = True,
        run_mapping: bool = True,
        run_methylation: bool = True,
    ):
        super().__init__()

        self.trial_name = trial_name
        self.pod5_path = pod5_path
        self.fastq_path = fastq_path
        self.bam_path = bam_path
        self.nanotel_path = nanotel_path
        self.output_dir = output_dir
        self.organism = organism

        self.do_pod5 = do_pod5
        self.do_fastq = do_fastq
        self.do_nanotel = do_nanotel
        self.do_align = do_align
        self.do_r = do_r

        self.run_filtration = run_filtration
        self.run_mapping = run_mapping
        self.run_methylation = run_methylation

        self._stop_requested = False

    def stop(self):
        self._stop_requested = True
        self.log.emit("⚠️ Stop requested by user")

    def run(self):
        try:
            self.log.emit("=" * 60)
            self.log.emit("🚀 WORKFLOW STARTING")
            self.log.emit("=" * 60)

            RunPipeline(
                trial_name=self.trial_name,
                pod5_path=self.pod5_path,
                fastq_path=self.fastq_path,
                bam_path=self.bam_path,
                nanotel_path=self.nanotel_path,
                output_dir=self.output_dir,
                organism=self.organism,
                do_pod5=self.do_pod5,
                do_fastq=self.do_fastq,
                do_nanotel=self.do_nanotel,
                do_align=self.do_align,
                do_r=self.do_r,
                run_filtration=self.run_filtration,
                run_mapping=self.run_mapping,
                run_methylation=self.run_methylation,
                log_cb=self.log.emit,
                stop_cb=lambda: self._stop_requested,
            )

            if self._stop_requested:
                self.done.emit(False, "Cancelled by user")
                return

            self.log.emit("✅ WORKFLOW FINISHED SUCCESSFULLY")
            self.done.emit(True, "Done.")

        except Exception as e:
            if "Cancelled by user" in str(e):
                self.done.emit(False, "Cancelled by user")
                return

            err = traceback.format_exc()
            self.log.emit(err)
            self.done.emit(False, err)