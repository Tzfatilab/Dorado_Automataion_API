"""Cooperative cancellation, distinct from a failed analysis."""


class WorkflowCancelled(RuntimeError):
    def __init__(self):
        super().__init__("Cancelled by user")
