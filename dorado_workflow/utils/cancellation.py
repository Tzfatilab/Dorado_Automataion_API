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


class CancellableWriter:
    """Check cooperative cancellation during writes to a temporary output file."""
    def __init__(self, stream, check_cancelled):
        self.stream = stream
        self.check_cancelled = check_cancelled

    def write(self, data):
        self.check_cancelled()
        return self.stream.write(data)

    def __getattr__(self, name):
        return getattr(self.stream, name)
