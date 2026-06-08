from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
)

from gui.ui_styles import make_card
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
                "Convert POD5 to BAM with\nbase modifications."
            ),
            (
                "nanotel",
                "NanoTel Analysis",
                "Analyze telomere content and \n generate statistics."
            ),
        ]

        for key, title, desc in workflow_items:
            # Create a selectable card and wire the click handler.
            card = SelectCard(key, title, desc, theme="green")
            card.mousePressEvent = lambda e, k=key: self._toggle_workflow(k)

            self.workflow_cards[key] = card
            row.addWidget(card)

        layout.addLayout(row)

        box.setLayout(layout)

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