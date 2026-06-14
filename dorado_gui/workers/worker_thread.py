import traceback
from PySide6.QtCore import QObject, Signal
from services.pipeline_runner import run_pipeline


"""Qt worker object that executes the pipeline outside the main UI thread."""
class WorkerThread(QObject):
    """Run the workflow asynchronously and report progress to the GUI.

    Signals:
        log(str): Emits textual log updates for display in the UI.
        done(bool, str): Emits completion status and a final message.
    """

    log = Signal(str)
    done = Signal(bool, str)

    def __init__(
            self,
            trial_name: str,
            pod5_path: str = "",
            fastq_path: str = "",
            bam_path: str = "",
            output_dir: str = "",
            organism: str = "Mouse",
            do_basecalling: bool = False,
            do_nanotel: bool = False,
            non_pod5_trim_status: str = "auto",
            methylation_type: str = "None",
            chromosome_mapping: bool = False,
            tvr_mode: str = "Use preset",
            tvr_manual: str = "",
            read_length: str = "",
            max_distance_edge: str = "134",
            min_density_threshold: str = "0.75",
    ):
        """Store workflow settings that will be passed to run_pipeline."""
        super().__init__()

        self.trial_name = trial_name
        self.pod5_path = pod5_path
        self.fastq_path = fastq_path
        self.bam_path = bam_path
        self.output_dir = output_dir
        self.organism = organism.lower()

        self.do_basecalling = do_basecalling
        self.do_nanotel = do_nanotel
        self.non_pod5_trim_status = non_pod5_trim_status

        self.methylation_type = methylation_type
        self.chromosome_mapping = chromosome_mapping
        self.tvr_mode = tvr_mode
        self.tvr_manual = tvr_manual
        self.read_length = read_length
        self.max_distance_edge = max_distance_edge
        self.min_density_threshold = min_density_threshold
        self._stop_requested = False

    def stop(self):
        """Request cancellation by setting a stop flag checked by the pipeline."""
        self._stop_requested = True
        self.log.emit("Stop requested by user")

    def run(self):
        """Execute the pipeline and emit final success/failure signals."""
        try:
            self.log.emit("=" * 60)
            self.log.emit("WORKFLOW STARTING")
            self.log.emit("=" * 60)

            # Pass all current settings and callbacks into the pipeline entrypoint.
            status_code, message = run_pipeline(
                trial_name=self.trial_name,
                pod5_path=self.pod5_path,
                fastq_path=self.fastq_path,
                bam_path=self.bam_path,
                output_dir=self.output_dir,
                organism=self.organism,
                do_basecalling=self.do_basecalling,
                do_nanotel=self.do_nanotel,
                non_pod5_trim_status=self.non_pod5_trim_status,
                methylation_type=self.methylation_type,
                chromosome_mapping=self.chromosome_mapping,
                tvr_mode=self.tvr_mode,
                tvr_manual=self.tvr_manual,
                read_length=self.read_length,
                max_distance_edge=self.max_distance_edge,
                min_density_threshold=self.min_density_threshold,
                log_cb=self.log.emit,
                stop_cb=lambda: self._stop_requested,
            )

            if self._stop_requested:
                self.done.emit(False, "Cancelled by user")
                return

            if status_code == 0:
                self.log.emit("WORKFLOW FINISHED SUCCESSFULLY")
                self.done.emit(True, message)
            else:
                self.done.emit(False, message)

        except Exception as e:
            if "Cancelled by user" in str(e):
                self.done.emit(False, "Cancelled by user")
                return

            err = traceback.format_exc()
            self.log.emit(err)
            self.done.emit(False, err)