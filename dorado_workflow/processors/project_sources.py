"""Resume post-analysis from immutable NanoTel sources in an existing project."""
import csv
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from openpyxl import load_workbook, Workbook
from dorado_workflow.utils.source_links import link_source


@dataclass
class ProjectSources:
    root: Path
    results: Path
    summaries: dict
    workbook: object
    settings: dict
    organism: str

    @classmethod
    def inspect(cls, directory):
        """Discover original populations, preferring native CSVs to workbook copies.

        Detection settings are required to keep recalculation compatible with
        the original measurements. Previously filtered tables are not sources.

        Args:
            directory: Directory containing the selected inputs.

        Returns:
            ProjectSources describing original populations, settings and supporting artifacts.
        """
        root = Path(directory).expanduser().resolve()
        results = root / "results" if (root / "results").is_dir() else root
        if not results.is_dir():
            raise ValueError("Choose an existing project folder or its results folder.")
        root = results.parent if results.name == "results" else root
        summaries = {}
        for path in (results / "nanotel").rglob("barcode*_summary.csv"):
            if re.fullmatch(r"barcode\d+_summary.csv", path.name):
                label = path.name[:-12]
                if label in summaries:
                    raise ValueError("Duplicate NanoTel source summaries: " + label)
                summaries[label] = path
        workbook = results / "nanotel_summary.xlsx"
        if not workbook.is_file():
            workbook = results / "reports" / "post_analysis_sources" / "nanotel_summary.xlsx"
        workbook = workbook if workbook.is_file() else None
        settings, organism = {}, None
        config = results / "reports" / "r_pipeline_config.json"
        snapshot = results / "reports" / "nanotel_source_settings.json"
        if config.is_file():
            settings = json.loads(config.read_text(encoding="utf-8-sig"))
        if snapshot.is_file():
            saved = json.loads(snapshot.read_text(encoding="utf-8-sig"))
            settings = settings or {"nanotel_analysis": saved["nanotel_analysis"]}
            organism = saved.get("organism")
        if workbook:
            book = load_workbook(workbook, read_only=True, data_only=True)
            try:
                metadata = next((book[n] for n in ("_source_Run metadata", "Run metadata") if n in book.sheetnames), None)
                if metadata:
                    parts = {}
                    for key, part, value in list(metadata.values)[1:]:
                        parts.setdefault(key, []).append((part, value))
                    decoded = {key: json.loads("".join(v for _, v in sorted(values))) for key, values in parts.items()}
                    settings = settings or decoded.get("settings") or {}
                    organism = organism or decoded.get("organism")
                for name in book.sheetnames:
                    if re.fullmatch(r"_source_barcode\d+", name):
                        summaries.setdefault(name[8:], name)
                    elif re.fullmatch(r"barcode\d+", name) and "_source_Run metadata" not in book.sheetnames:
                        headers = next(book[name].values, ())
                        if "sequence_ID" in headers:
                            summaries.setdefault(name, name)
            finally:
                book.close()
        if not summaries:
            raise ValueError("No original before-filter NanoTel summaries were found. A dashboard or presentation-only Excel file is insufficient.")
        params = settings.get("nanotel_analysis", settings)
        if not isinstance(params, dict) or not {"max_mismatch", "tvr_patterns", "telomere_pattern"}.issubset(params):
            raise ValueError("Original NanoTel settings are missing. Select the complete project, including its saved configuration or source workbook.")
        return cls(root, results, summaries, workbook, settings, organism or "")

    @property
    def params(self):
        """Params.

        Inputs:
            None; uses instance state.

        Returns:
            Selected stored value, or the supplied fallback when absent.
        """
        return self.settings.get("nanotel_analysis", self.settings)

    def restore(self, context, check_cancelled):
        """Stage immutable inputs as links and extract workbook-only populations.

        Previous filtered results and aggregate figures are deliberately omitted:
        the shared post-analysis workflow must regenerate them using new filters.

        Args:
            context: Shared workflow configuration, paths, logger and command executor.
            check_cancelled: Callback raising when workflow cancellation is requested.

        Returns:
            None.
        """
        target = context.path_manager.get_nanotel_output_dir_path()
        target.mkdir(parents=True, exist_ok=True)
        book = load_workbook(self.workbook, read_only=True, data_only=True) if self.workbook else None
        try:
            for label, source in self.summaries.items():
                check_cancelled()
                output = target / (label + "_summary.csv")
                if isinstance(source, Path):
                    link_source(source, output)
                    # Detailed source tracks remain useful; aggregate plots and
                    # old filtered populations must not be reused after refiltering.
                    details = source.parent / "report_details"
                    if details.is_dir():
                        shutil.copytree(details, target / label / "report_details", dirs_exist_ok=True, copy_function=link_source,
                                        ignore=shutil.ignore_patterns("*telomere*.plotly.json", "*.html"))
                    archive = source.parent / "report_details.zip"
                    if archive.is_file():
                        import zipfile
                        from dorado_workflow.reports.storage.archive import member_path
                        with zipfile.ZipFile(archive) as zipped:
                            for info in zipped.infolist():
                                if info.is_dir() or "telomere" in info.filename or info.filename.endswith(".html"):
                                    continue
                                extracted_path = member_path(target / label / "report_details", info.filename)
                                # Loose exports take precedence over archived
                                # versions. Never overwrite a linked source file.
                                if extracted_path.exists():
                                    continue
                                extracted_path.parent.mkdir(parents=True, exist_ok=True)
                                with zipped.open(info) as archive_stream, extracted_path.open("xb") as output_stream:
                                    shutil.copyfileobj(archive_stream, output_stream)
                    if not context.config_manager.get_nanotel_params().get("summary_only", False):
                        reads = source.parent / "reads"
                        if reads.is_dir():
                            shutil.copytree(reads, target / label / "reads", dirs_exist_ok=True, copy_function=link_source)
                    for path in source.parent.glob(label + "_*.json"):
                        if not path.name.endswith(".plotly.json"):
                            link_source(path, target / path.name)
                else:
                    sheet = book[source]
                    with output.open("w", newline="", encoding="utf-8") as stream:
                        csv.writer(stream).writerows(sheet.values)
            # Completed detector logs retain original input counts for projects
            # that crashed before their first workbook was written.
            logs = context.path_manager.get_results_dir_path() / "logs"
            for path in self.results.rglob("nanotel_barcode*.log"):
                check_cancelled()
                logs.mkdir(parents=True, exist_ok=True)
                dest = logs / path.name
                if dest.exists():
                    raise ValueError("Ambiguous NanoTel source logs: " + path.name)
                link_source(path, dest)
            for name in ("km_barcode_statistics.csv", "km_run_statistics.csv"):
                path = self.results / "nanotel" / name
                if path.is_file(): link_source(path, target / name)
            # Keep motif/coverage provenance and input counts, never old filtered
            # rows, mappings, aggregate figures or summary statistics.
            evidence = Workbook()
            evidence.remove(evidence.active)
            evidence_sheet_names = {"Read motifs", "Barcode source counts", "NanoTel analysis facts", "KM by barcode", "KM run statistics"}
            if book:
                for sheet in book:
                    name = sheet.title.removeprefix("_source_")
                    if name in evidence_sheet_names:
                        dest = evidence.create_sheet("_source_" + name)
                        for row in sheet.values:
                            dest.append(row)
            # Full runs retain analysis fields in their automatic workbook,
            # rather than loose JSON. Carry those fields into the source sheet
            # already used by both report modes, without recreating JSON files.
            from dorado_workflow.reports.storage.analysis_metadata import analysis_rows, HEADERS
            analysis = analysis_rows(self.results, include_native=False)
            if analysis and '_source_NanoTel analysis facts' not in evidence.sheetnames:
                retained = evidence.create_sheet('_source_NanoTel analysis facts')
                retained.append(HEADERS)
                for row, _, _ in analysis:
                    retained.append([row[key] for key in HEADERS])
                    for cell in retained[retained.max_row]:
                        if isinstance(cell.value, str):
                            cell.data_type = 's'
            metadata = evidence.create_sheet("_source_Run metadata")
            metadata.append(["Field", "Part", "Value"])
            updated_settings = dict(self.settings)
            updated_settings["nanotel_analysis"] = context.config_manager.get_nanotel_params()
            for key, value in {"settings": updated_settings, "organism": self.organism or context.config_manager.get_current_organism()}.items():
                encoded = json.dumps(value, ensure_ascii=True)
                # Split JSON to stay below Excel's 32,767-character cell limit.
                metadata_chunk_size = 30000
                for offset in range(0, len(encoded), metadata_chunk_size):
                    metadata.append([key, offset // metadata_chunk_size + 1,
                                     encoded[offset:offset + metadata_chunk_size]])
            # Keep a visible placeholder until the real workbook replaces it.
            evidence.create_sheet("Post-analysis source")
            for sheet in evidence:
                if sheet.title.startswith("_source_"): sheet.sheet_state = "hidden"
            results = context.path_manager.get_r_analysis_dir_path()
            destination = (results / "nanotel_summary.xlsx" if context.config_manager.get_nanotel_params().get("summary_only", False)
                           else results / "reports" / "post_analysis_sources" / "nanotel_summary.xlsx")
            destination.parent.mkdir(parents=True, exist_ok=True)
            evidence.save(destination)
            evidence.close()
        finally:
            if book: book.close()

    def prepare_mapping(self, operator, check_cancelled):
        """Align saved sequences again through the shared alignment processor.

        Prefer FASTQ inputs to potentially partial aligned outputs. Existing BAMs
        are sequence sources only: their old alignment calls are not reused.

        Args:
            operator: WorkflowOperator coordinating the shared processors.
            check_cancelled: Callback raising when workflow cancellation is requested.

        Returns:
            None.
        """
        check_cancelled()
        required_barcodes = self._mapping_barcodes(check_cancelled)
        processing = self.root / "processing"
        candidates = (
            (processing / "fastq", "fastq"),
            (processing / "demultiplexed", "fastq"),
            (processing / "demultiplexed", "bam"),
            (processing / "aligned", "bam"),
        )
        incomplete_sources = []
        for folder, input_type in candidates:
            check_cancelled()
            if not folder.is_dir():
                continue
            inputs = operator.aligner._find_alignment_inputs(folder, input_type)
            if not inputs:
                continue
            available_barcodes = {
                operator.aligner._extract_barcode(path.relative_to(folder))
                for path in inputs
            }
            missing = required_barcodes - available_barcodes
            if missing:
                incomplete_sources.append(f"{folder}: missing {', '.join(sorted(missing))}")
                continue
            operator.context.logger.info(
                f"Recalculating alignment from saved {input_type.upper()} reads: {folder}"
            )
            result = operator.aligner.execute(
                str(folder),
                organism=operator.context.config_manager.get_current_organism(),
                input_type=input_type,
                use_existing_alignment=False,
                link_inputs_only=True,
            )
            if not result.success:
                raise RuntimeError(result.error or "Alignment recalculation failed")
            return
        if incomplete_sources:
            raise ValueError(
                "Saved sequence inputs do not cover all nonempty NanoTel barcodes. "
                "Select the complete original project to recalculate alignment. "
                + "; ".join(incomplete_sources)
            )
        raise ValueError(
            "Alignment recalculation requires saved FASTQ reads or barcode BAMs "
            "under processing/fastq, processing/demultiplexed or processing/aligned. "
            "The Excel workbook alone does not contain the original sequences."
        )

    def _mapping_barcodes(self, check_cancelled):
        """Identify nonempty source populations that require sequence inputs.

        Args:
            check_cancelled: Callback raising when cancellation is requested.

        Returns:
            Set of barcode labels with at least one original NanoTel record.
        """
        required = set()
        workbook = None
        try:
            for barcode, source in self.summaries.items():
                check_cancelled()
                if isinstance(source, Path):
                    with source.open(newline="", encoding="utf-8-sig") as stream:
                        rows = csv.reader(stream)
                        next(rows, None)
                        if any(any(value not in (None, "") for value in row) for row in rows):
                            required.add(barcode)
                else:
                    if workbook is None:
                        workbook = load_workbook(self.workbook, read_only=True, data_only=True)
                    rows = iter(workbook[source].values)
                    next(rows, None)
                    if any(any(value not in (None, "") for value in row) for row in rows):
                        required.add(barcode)
        finally:
            if workbook is not None:
                workbook.close()
        return required
