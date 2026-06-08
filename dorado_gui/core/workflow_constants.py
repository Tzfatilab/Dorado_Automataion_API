"""Shared workflow mode constants for dorado_api UI modules."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

WORKFLOW_MODE_COMPLETE = "complete_basecalling"
WORKFLOW_MODE_NANOTEL = "nanotel_filtration_statistic"

WORKFLOW_MODES = [
    (WORKFLOW_MODE_COMPLETE, "Complete Basecalling Workflow"),
    (WORKFLOW_MODE_NANOTEL, "Nanotel (+Filtration and Statistic) Workflow"),
]

WORKFLOW_MODE_LABELS = {
    WORKFLOW_MODE_COMPLETE: "Complete Basecalling Workflow",
    WORKFLOW_MODE_NANOTEL: "Nanotel (+Filtration and Statistic) Workflow",
}

ICON_SIZE = 40