"""Cooperative cancellation, distinct from a failed analysis."""


class WorkflowCancelled(RuntimeError):
    def __init__(self):
        """Initialize the instance and its dependencies.

        Inputs:
            None; uses instance state.

        Returns:
            None; initializes the instance.
        """
        super().__init__("Cancelled by user")
