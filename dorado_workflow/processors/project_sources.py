"""Resume post-analysis from immutable NanoTel sources in an existing project."""
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from openpyxl import load_workbook, Workbook
from dorado_workflow.utils.source_links import link_source
from dorado_workflow.utils.source_discovery import source_files
from dorado_workflow.reports.storage.saved_sources import source_folders, MANIFEST


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
        for path in source_files(results / "nanotel", "barcode*_summary.csv"):
            if re.fullmatch(r"barcode\d+_summary.csv", path.name):
                label = path.name[:-12]
                if label in summaries:
                    raise ValueError("Duplicate NanoTel source summaries: " + label)
                summaries[label] = path
        workbook = results / "nanotel_summary.xlsx"
        if not workbook.is_file():
            workbook = results / "reports" / "post_analysis_sources" / "nanotel_summary.xlsx"
        if not workbook.is_file():
            workbook = results / "nanotel" / "nanotel_results.xlsx"
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

    @property
    def includes_km(self):
        """Retain the source run's KM choice, including legacy artifact evidence."""
        if "include_km" in self.params:
            return self.params["include_km"] is True
        # Older runs predate the opt-in setting. Their saved KM exports record
        # whether KM was included; the currently active profile is irrelevant.
        if any(source_files(self.results / "nanotel", "*km*statistics.csv")):
            return True
        if self.workbook:
            book = load_workbook(self.workbook, read_only=True, data_only=True)
            try:
                return any(name.removeprefix("_source_") in
                           {"KM by barcode", "KM run statistics", "Kaplan-Meier"}
                           for name in book.sheetnames)
            finally:
                book.close()
        return False

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
        reuse_km = self.includes_km
        if not reuse_km:
            context.logger.info("KM disabled for recalculation; saved KM tables are not copied.")
        book = load_workbook(self.workbook, read_only=True, data_only=True) if self.workbook else None
        referenced_folders = {}
        try:
            for label, source in self.summaries.items():
                check_cancelled()
                output = target / (label + "_summary.csv")
                if isinstance(source, Path):
                    link_source(source, output)
                    # Keep only a directory reference: no per-read links, copies,
                    # or ZIP extraction in the recalculated project.
                    inherited = source_folders(source.parent)
                    detail_folder = inherited.get(label, source.parent if source.parent.name == label else source.parent / label)
                    if detail_folder.name == label and detail_folder.is_dir():
                        referenced_folders[label] = str(detail_folder.resolve())
                    analysis = source.parent / (label + "_analysis.json")
                    if analysis.is_file():
                        link_source(analysis, target / analysis.name)
                else:
                    sheet = book[source]
                    with output.open("w", newline="", encoding="utf-8") as stream:
                        csv.writer(stream).writerows(sheet.values)
                    original_nanotel = self.results / "nanotel"
                    detail_folder = source_folders(original_nanotel).get(label, original_nanotel / label)
                    if detail_folder.is_dir():
                        referenced_folders[label] = str(detail_folder.resolve())
            (target / MANIFEST).write_text(json.dumps(referenced_folders, indent=2), encoding="utf-8")
            # Completed detector logs retain original input counts for projects
            # that crashed before their first workbook was written.
            logs = context.path_manager.get_results_dir_path() / "logs"
            for path in source_files(self.results, "nanotel_barcode*.log"):
                check_cancelled()
                logs.mkdir(parents=True, exist_ok=True)
                dest = logs / path.name
                if dest.exists():
                    raise ValueError("Ambiguous NanoTel source logs: " + path.name)
                link_source(path, dest)
            for name in ("km_barcode_statistics.csv", "km_run_statistics.csv"):
                path = self.results / "nanotel" / name
                if reuse_km and path.is_file(): link_source(path, target / name)
            # Keep motif/coverage provenance and input counts, never old filtered
            # rows, mappings, aggregate figures or summary statistics.
            evidence = Workbook()
            evidence.remove(evidence.active)
            evidence_sheet_names = {"Read motifs", "Read repeat summaries", "Barcode source counts", "NanoTel analysis facts"}
            if reuse_km:
                evidence_sheet_names.update({"KM by barcode", "KM run statistics"})
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
        """Reuse complete saved alignments and refilter them without realignment.

        Only processing/aligned inputs are eligible. Filtered BAMs and mapped
        result tables cannot recover reads excluded by the previous thresholds.

        Args:
            operator: WorkflowOperator coordinating the shared processors.
            check_cancelled: Callback raising when workflow cancellation is requested.

        Returns:
            None.
        """
        check_cancelled()
        required_barcodes = self._mapping_barcodes(check_cancelled)
        mapping = self.settings.get('mapping_analysis', {})
        candidates = [self.root / 'processing/aligned']
        recorded = mapping.get('bam_dir')
        if recorded and Path(recorded).name == 'aligned':
            candidates.append(Path(recorded))
        problems = []
        selected = None
        for folder in dict.fromkeys(path.resolve() for path in candidates):
            check_cancelled()
            if not folder.is_dir():
                continue
            inputs = [path for path in sorted(folder.rglob('*.bam'))
                      if not path.name.lower().startswith('filtered_')]
            from dorado_workflow.reports.exports.workbook import barcode_from_summary_filename
            available_barcodes = {barcode_from_summary_filename(path.name) or
                                 barcode_from_summary_filename(path.parent.name) for path in inputs}
            missing = required_barcodes - available_barcodes
            if missing:
                problems.append(f"{folder}: missing {', '.join(sorted(missing))}")
                continue
            summary = next((path for path in (folder / 'alignment_summary.txt',
                                              folder / 'sequencing_summary.txt') if path.is_file()), None)
            if not inputs or summary is None:
                problems.append(f'{folder}: original alignment BAMs/summary are missing')
                continue
            with summary.open(encoding='utf-8-sig', newline='') as stream:
                headers = next(csv.reader(stream, delimiter='\t'), [])
            required = {'read_id', 'alignment_direction', 'alignment_genome',
                        'alignment_genome_start', 'alignment_genome_end'}
            mapq = {'alignment_mapq', 'mapq', 'mapping_quality', 'alignment_mapping_quality'}
            if not required.issubset(headers) or not mapq.intersection(headers):
                problems.append(f'{summary}: required alignment/MAPQ columns are missing')
                continue
            selected = folder, inputs, summary
            break
        if selected is None:
            raise ValueError(
                'Mapping recalculation requires the original unfiltered BAMs and alignment summary '
                'under processing/aligned. Filtered mapping outputs and Excel alone are insufficient. '
                'No alignment was rerun. ' + '; '.join(problems)
            )
        folder, inputs, summary = selected
        target = operator.context.path_manager.get_aligned_dir_path()
        target.mkdir(parents=True, exist_ok=True)
        # Preflight every destination before staging immutable links. The R
        # mapper reads them and writes new filtered outputs in results/mapping.
        sources = [(summary, target / summary.name)]
        for path in inputs:
            sources.append((path, target / path.relative_to(folder)))
            index = Path(str(path) + '.bai')
            if index.is_file():
                sources.append((index, target / index.relative_to(folder)))
        for _, destination in sources:
            if destination.exists() or destination.is_symlink():
                raise FileExistsError(f'Mapping input destination already exists: {destination}')
        for path, destination in sources:
            check_cancelled()
            link_source(path, destination)
        operator.context.logger.info(
            f'Reusing {len(inputs)} saved alignment BAMs and {summary.name}; '
            'applying current NanoTel and mapping filters without rerunning Dorado/minimap2.'
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
