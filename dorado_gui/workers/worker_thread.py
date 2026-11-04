import traceback
from copy import deepcopy
from PySide6.QtCore import QObject, Signal
from services.pipeline_runner import run_pipeline
from dorado_workflow.utils.cancellation import WorkflowCancelled


"""Qt worker object that executes the pipeline outside the main UI thread."""
class WorkerThread(QObject):
    """Run the workflow asynchronously and report progress to the GUI.

    Signals:
        log(str): Emits textual log updates for display in the UI.
        done(bool, str): Emits completion status and a final message.
    """

    log = Signal(str)
    done = Signal(bool, str)
    report_ready = Signal(str)

    def __init__(
            self,
            trial_name: str,
            pod5_path: str = "",
            fastq_path: str = "",
            bam_path: str = "",
            project_path: str = "",
            do_post_analysis: bool = False,
            output_dir: str = "",
            organism: str = "Mouse",
            do_basecalling: bool = False,
            do_nanotel: bool = False,
            non_pod5_trim_status: str = "auto",
            bam_is_aligned=None,
            bam_has_modifications=None,
            methylation_type: str = "None",
            chromosome_mapping: bool = False,
            nanotel_mapping: bool = False,
            summary_only: bool = False,
            tvr_mode: str = "None",
            tvr_manual: str = "",
            allow_mismatch: bool = False,
            read_length: str = "",
            max_distance_edge: str = "",
            max_telomere_start: str = "",
            min_density_threshold: str = "",
            short_telomere_threshold: str = "",
            config_data=None,
    ):
        """Store workflow settings that will be passed to run_pipeline.

        Args:
            trial_name: str; run name used for output directories and logs.
            pod5_path: str; pod5 path. Default: ''.
            fastq_path: str; fastq path. Default: ''.
            bam_path: str; bam path. Default: ''.
            project_path: str; project path. Default: ''.
            do_post_analysis: bool; whether to recalculate an existing project. Default: False.
            output_dir: str; directory for generated outputs. Default: ''.
            organism: str; organism label selecting reference and analysis defaults. Default: 'Mouse'.
            do_basecalling: bool; whether the run includes basecalling. Default: False.
            do_nanotel: bool; whether the run includes NanoTel detection. Default: False.
            non_pod5_trim_status: str; trimming state of the original BAM or FASTQ reads. Default: 'auto'.
            bam_is_aligned: Whether the selected BAM already contains alignments. Default: None.
            bam_has_modifications: Whether the BAM contains modified-base tags. Default: None.
            methylation_type: str; selected modified-base analysis mode. Default: 'None'.
            chromosome_mapping: bool; whether reference alignment is selected in the basecalling options. Default: False.
            nanotel_mapping: bool; whether chromosome mapping is selected for NanoTel analysis. Default: False.
            summary_only: bool; whether to omit individual-read pages from the report. Default: False.
            tvr_mode: str; selected TVR configuration mode. Default: 'None'.
            tvr_manual: str; user-entered TVR motifs. Default: ''.
            allow_mismatch: bool; whether one mismatch is allowed in repeat searches. Default: False.
            read_length: str; read-length value in base pairs. Default: ''.
            max_distance_edge: str; required read margin in base pairs. Default: ''.
            max_telomere_start: str; latest allowed telomere start in base pairs. Default: ''.
            min_density_threshold: str; minimum repeat density entered in the GUI. Default: ''.
            short_telomere_threshold: str; short-telomere cutoff entered in base pairs. Default: ''.
            config_data: Configuration snapshot supplied for this run. Default: None.

        Returns:
            None; initializes the instance.
        """
        super().__init__()

        self.trial_name = trial_name
        self.config_data = deepcopy(config_data)
        self.pod5_path = pod5_path
        self.fastq_path = fastq_path
        self.bam_path = bam_path
        self.project_path = project_path
        self.do_post_analysis = do_post_analysis
        self.output_dir = output_dir
        self.organism = organism.lower()

        self.do_basecalling = do_basecalling
        self.do_nanotel = do_nanotel
        self.non_pod5_trim_status = non_pod5_trim_status
        self.bam_is_aligned = bam_is_aligned
        self.bam_has_modifications = bam_has_modifications

        self.methylation_type = methylation_type
        self.chromosome_mapping = chromosome_mapping
        self.nanotel_mapping = nanotel_mapping
        self.summary_only = summary_only
        self.tvr_mode = tvr_mode
        self.tvr_manual = tvr_manual
        self.allow_mismatch = allow_mismatch
        self.read_length = read_length
        self.max_distance_edge = max_distance_edge
        self.max_telomere_start = max_telomere_start
        self.min_density_threshold = min_density_threshold
        self.short_telomere_threshold = short_telomere_threshold
        self._stop_requested = False

    def stop(self):
        """Request cancellation by setting a stop flag checked by the pipeline.

        Inputs:
            None; uses instance state.

        Returns:
            None.
        """
        self._stop_requested = True
        self.log.emit("Stop requested by user")

    def run(self):
        """Execute the pipeline and emit final success/failure signals.

        Inputs:
            None; uses instance state.

        Returns:
            None.
        """
        try:
            self.log.emit("Run started")

            # Workers report through Qt signals; GUI widgets are updated only
            # by their receiving slots on the main thread.
            status_code, message = run_pipeline(
                trial_name=self.trial_name,
                config_data=self.config_data,
                pod5_path=self.pod5_path,
                fastq_path=self.fastq_path,
                bam_path=self.bam_path,
                project_path=self.project_path,
                do_post_analysis=self.do_post_analysis,
                output_dir=self.output_dir,
                organism=self.organism,
                do_basecalling=self.do_basecalling,
                do_nanotel=self.do_nanotel,
                non_pod5_trim_status=self.non_pod5_trim_status,
                bam_is_aligned=self.bam_is_aligned,
                bam_has_modifications=self.bam_has_modifications,
                methylation_type=self.methylation_type,
                chromosome_mapping=self.chromosome_mapping,
                nanotel_mapping=self.nanotel_mapping,
                summary_only=self.summary_only,
                tvr_mode=self.tvr_mode,
                tvr_manual=self.tvr_manual,
                allow_mismatch=self.allow_mismatch,
                read_length=self.read_length,
                max_distance_edge=self.max_distance_edge,
                max_telomere_start=self.max_telomere_start,
                min_density_threshold=self.min_density_threshold,
                short_telomere_threshold=self.short_telomere_threshold,
                log_cb=self.log.emit,
                stop_cb=lambda: self._stop_requested,
                report_cb=self.report_ready.emit,
            )

            if self._stop_requested:
                self.done.emit(False, "Cancelled by user")
                return

            if status_code == 0:
                self.done.emit(True, message)
            else:
                self.done.emit(False, message)

        except WorkflowCancelled:
            self.done.emit(False, "Cancelled by user")

        except Exception:
            err = traceback.format_exc()
            self.log.emit(err)
            self.done.emit(False, err)
