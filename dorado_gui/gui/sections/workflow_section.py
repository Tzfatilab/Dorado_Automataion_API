from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
)

from gui.ui_styles import make_card, make_help_button
from gui.widgets.selection_widgets import SelectCard, SelectionGrid


class WorkflowSection:
    """Mixin that builds the Analysis Steps card and provides workflow state helpers."""

    def _build_workflow(self):
        """
        Build the 'Analysis Steps' card containing selectable workflow step cards.

        Args:
            None

        Returns:
            QWidget: styled card widget with selectable workflow steps.
        """
        box = make_card("Analysis Steps")

        layout = QVBoxLayout()
        layout.setSpacing(14)

        subtitle = QLabel("Select the analysis steps to run")
        subtitle.setStyleSheet("""
            color: #6b7280;
            font-size: 12px;
            background-color: white;
        """)
        layout.addWidget(subtitle)

        row = SelectionGrid(3, spacing=16)

        # Container of SelectCard widgets for each workflow step
        self.workflow_cards = {}

        workflow_items = [
            (
                "basecalling",
                "Basecalling",
                "Convert POD5 to BAM with base modifications."
            ),
            (
                "nanotel",
                "NanoTel Analysis",
                "Analyze telomere content and generate statistics."
            ),
            (
                "post_analysis",
                "Recalculate results",
                "Refilter saved NanoTel data and rebuild reports."
            ),
        ]

        for key, title, desc in workflow_items:
            # Create a selectable card and wire the click handler.
            card = SelectCard(key, title, desc, theme="green", title_size=15)
            card.mousePressEvent = lambda e, k=key: self._toggle_workflow(k)

            self.workflow_cards[key] = card
            row.add_card(card)

        layout.addWidget(row)

        box.setLayout(layout)
        make_help_button(
            box, "Analysis Steps",
            "<h2 style='color:#1d4ed8'>Analysis steps</h2>"
            "<h3>Basecalling</h3>"
            "<p><b>Input:</b> raw POD5 signals.<br>"
            "<b>Process:</b> Dorado calls bases and separates barcodes.<br>"
            "<b>Output:</b> basecalled BAM and FASTQ reads.</p>"
            "<h3>NanoTel Analysis</h3>"
            "<p><b>Input:</b> FASTQ reads, including FASTQ converted from BAM.<br>"
            "<b>Process:</b> measures telomeres, filters reads, and calculates statistics.<br>"
            "<b>Output:</b> per-barcode results and a combined summary.</p>"
            "<p>For raw POD5 through telomere results, select both steps.</p>"
            "<h3>Recalculate results</h3>"
            "<p>Select an <b>Existing project</b> to rerun the shared filtering and optional mapping stages, "
            "then rebuild Excel and a Summary dashboard without rerunning NanoTel. TVR and mismatch settings "
            "are loaded from the original run. Results are saved in a new output folder.</p>"
            "<hr><h2 style='color:#1d4ed8'>Advanced options</h2>"
            "<h3>Basecalling options</h3>"
            "<p><b>Methylation Type:</b> choose whether to detect modified bases.<br>"
            "<b>Chromosome Mapping:</b> align reads to a reference genome.</p>"
            "<h3>NanoTel options</h3>"
            "<p><b>Summary only:</b> automatically save Excel with barcode statistics, "
            "before/after-filter read tables and available KM results, plus a compact dashboard. Skip "
            "detailed NanoTel plots, per-read FASTA and density/motif track exports. "
            "Detection and filters stay unchanged. Separately selected mapping and "
            "methylation still run.<br>"
            "<b>TVR Mode:</b> leave all choices unselected for no TVR patterns; "
            "choose Preset, TSQ1, or Manual to search for TVRs.<br>"
            "<b>Allow 1 mismatch:</b> permit one difference in telomere and TVR "
            "patterns. Preset always uses exact matching.<br>"
            "<b>Run mapping:</b> map NanoTel reads to the genome.</p>"
            "<h3>Numeric thresholds</h3>"
            "<p><b>Minimum total read length (bp):</b> minimum length of the whole read, "
            "not just its telomere. Shorter reads fail the read-length filter.<br>"
            "<b>Latest telomere start (bp):</b> latest permitted start position "
            "of the telomere in the analyzed sequence. Also sets the minimum margin "
            "by which read length must exceed the running median telomere length.<br>"
            "<b>Minimum telomeric repeat density (%):</b> minimum percentage of the "
            "telomeric region matching telomeric repeats; for example, 75 means 75%.<br>"
            "<b>Short telomere cutoff (bp):</b> telomeres shorter than this value "
            "count as short in the report. This threshold does not itself exclude reads.</p>",
            subtitle
        )

        # Initialize selection state: no workflows selected by default
        self.selected_workflows = set()
        for key in self.workflow_cards:
            self.workflow_cards[key].set_selected(False)

        return box

    def _toggle_workflow(self, key):
        """
        Toggle selection state for a workflow step.

        Args:
            key (str): identifier of the workflow step (e.g. "basecalling", "nanotel").

        Returns:
            None
        """
        if key == "post_analysis":
            if key in self.selected_workflows:
                self.selected_workflows.clear()
            else:
                self.selected_workflows = {key}
                self._select_input("project")
                self._load_post_analysis_source()
        else:
            self.selected_workflows.discard("post_analysis")
            if self.selected_input == "project":
                self._select_input("pod5" if key == "basecalling" else "fastq")
            if key in self.selected_workflows:
                self.selected_workflows.remove(key)
            else:
                self.selected_workflows.add(key)
        for name, card in self.workflow_cards.items():
            card.set_selected(name in self.selected_workflows)

        if hasattr(self, "_update_advanced_options_state"):
            self._update_advanced_options_state()

    def _build_workflow_flags(self, inputs):
        """
        Derive boolean flags indicating which workflow steps should run.

        Args:
            inputs (dict): mapping of input types to paths (keys: 'pod5','fastq','bam').

        Returns:
            dict: flags for workflow steps, e.g. {'do_basecalling': bool, 'do_nanotel': bool}
        """
        return {
            "do_post_analysis": "post_analysis" in self.selected_workflows,
            "do_basecalling":
                "basecalling" in self.selected_workflows
                and bool(inputs.get("pod5", "")),

            "do_nanotel":
                "nanotel" in self.selected_workflows,
        }
