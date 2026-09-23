from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
)

from gui.ui_styles import make_card, make_help_button
from gui.widgets.selection_widgets import SelectCard


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

        row = QHBoxLayout()
        row.setSpacing(16)

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
        ]

        for key, title, desc in workflow_items:
            # Create a selectable card and wire the click handler.
            card = SelectCard(key, title, desc, theme="green", title_size=15)
            card.mousePressEvent = lambda e, k=key: self._toggle_workflow(k)

            self.workflow_cards[key] = card
            row.addWidget(card)

        layout.addLayout(row)

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
            "<hr><h2 style='color:#1d4ed8'>Advanced options</h2>"
            "<h3>Basecalling options</h3>"
            "<p><b>Methylation Type:</b> choose whether to detect modified bases.<br>"
            "<b>Chromosome Mapping:</b> align reads to a reference genome.</p>"
            "<h3>NanoTel options</h3>"
            "<p><b>Summary only:</b> skip individual read plots and FASTA files; "
            "keep summary outputs in one Excel workbook.<br>"
            "<b>TVR Mode:</b> leave all choices unselected for no TVR patterns; "
            "choose Preset, TSQ1, or Manual to search for TVRs.<br>"
            "<b>Allow 1 mismatch:</b> permit one difference in telomere and TVR "
            "patterns. Preset always uses exact matching.<br>"
            "<b>Run mapping:</b> map NanoTel reads to the genome.</p>"
            "<h3>Numeric thresholds</h3>"
            "<p><b>Min Read Length:</b> shortest read accepted for analysis.<br>"
            "<b>Max Edge Distance:</b> how far a telomere may start from a read end.<br>"
            "<b>Max Telomere Start:</b> limit for locating the telomere start.<br>"
            "<b>Min Density:</b> minimum telomere-repeat density required.<br>"
            "<b>Short Telomere Cutoff:</b> enter a length cutoff (X) in bp. "
            "The output reports the percentage of telomeres shorter than X.</p>",
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
        if key in self.selected_workflows:
            self.selected_workflows.remove(key)
            self.workflow_cards[key].set_selected(False)
        else:
            self.selected_workflows.add(key)
            self.workflow_cards[key].set_selected(True)

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
            "do_basecalling":
                "basecalling" in self.selected_workflows
                and bool(inputs.get("pod5", "")),

            "do_nanotel":
                "nanotel" in self.selected_workflows,
        }
