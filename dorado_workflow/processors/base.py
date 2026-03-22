"""
Processor Base Module
====================

Abstract base class and supporting classes for all workflow processors.
Defines the common interface and shared functionality.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ProcessorResult:
    """
    Standard result object returned by all processors.

    Provides consistent interface for success/failure tracking,
    output paths, and statistics collection.

    Attributes:
        success: Whether the process completed successfully
        output_paths: Dictionary of output file/directory paths
        statistics: Dictionary of process statistics (counts, metrics, etc.)
        error: Error message if failed (None if successful)
    """
    success: bool
    output_paths: Dict[str, Path] = field(default_factory=dict)
    statistics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def __post_init__(self):
        """Validate that failed results have an error message."""
        if not self.success and not self.error:
            self.error = "Process failed with unknown error"

    def get_output(self, key: str, default: Optional[Path] = None) -> Optional[Path]:
        """
        Safely get an output path.

        Args:
            key: Key name for the output path
            default: Default value if key not found

        Returns:
            Path object or default
        """
        return self.output_paths.get(key, default)

    def get_statistic(self, key: str, default: Any = None) -> Any:
        """
        Safely get a statistic value.

        Args:
            key: Key name for the statistic
            default: Default value if key not found

        Returns:
            Statistic value or default
        """
        return self.statistics.get(key, default)

    def __repr__(self) -> str:
        """String representation of result."""
        status = "SUCCESS" if self.success else "FAILED"
        outputs = len(self.output_paths)
        stats = len(self.statistics)
        return f"ProcessorResult({status}, outputs={outputs}, stats={stats})"


class WorkflowContext:
    """
    Container for all shared workflow resources and dependencies.

    Passed to all processors to provide access to managers and utilities.
    This avoids passing multiple parameters to each processor.

    Attributes:
        logger: WorkflowLogger instance
        config_manager: ConfigManager instance
        path_manager: PathManager instance
        barcode_manager: BarcodeManager instance
        command_executor: CommandExecutor instance
    """

    def __init__(self, logger, config_manager, path_manager,
                 barcode_manager, command_executor):
        """
        Initialize workflow context with all dependencies.

        Args:
            logger: WorkflowLogger instance
            config_manager: ConfigManager instance
            path_manager: PathManager instance
            barcode_manager: BarcodeManager instance
            command_executor: CommandExecutor instance
        """
        self.logger = logger
        self.config_manager = config_manager
        self.path_manager = path_manager
        self.barcode_manager = barcode_manager
        self.command_executor = command_executor

    def validate_tools(self, required_tools: list) -> bool:
        """
        Validate that all required tools are available.
        Convenience method that delegates to command_executor.

        Args:
            required_tools: List of tool names to check

        Returns:
            True if all tools available, False otherwise
        """
        all_available, missing = self.command_executor.validate_tools(required_tools)
        return all_available

    def __repr__(self) -> str:
        """String representation of context."""
        return (
            f"WorkflowContext("
            f"trial={self.path_manager.trial_name}, "
            f"organism={self.config_manager.get_current_organism()})"
        )


class ProcessorBase(ABC):
    """
    Abstract base class for all workflow processors.

    Defines the standard interface that all processors must implement:
    - validate_inputs(): Check prerequisites before execution
    - execute(): Run the main process
    - get_output_paths(): Return expected output locations

    All processors receive a WorkflowContext with access to:
    - Logger for logging
    - ConfigManager for configuration
    - PathManager for paths
    - BarcodeManager for barcode tracking
    - CommandExecutor for running commands
    """

    def __init__(self, context: WorkflowContext):
        """
        Initialize processor with workflow context.

        Args:
            context: WorkflowContext with all shared resources
        """
        self.context = context

    @abstractmethod
    def validate_inputs(self, *args, **kwargs) -> bool:
        """
        Validate that all required inputs and prerequisites are met.

        This should check:
        - Input files/directories exist
        - Required tools are available
        - Configuration is valid

        Returns:
            True if validation passes, False otherwise
        """
        pass

    @abstractmethod
    def execute(self, *args, **kwargs) -> ProcessorResult:
        """
        Execute the main processing task.

        This is where the actual work happens:
        - Build commands
        - Execute processes
        - Track results
        - Handle errors

        Returns:
            ProcessorResult with success status, outputs, and statistics
        """
        pass

    @abstractmethod
    def get_output_paths(self) -> Dict[str, Path]:
        """
        Get the expected output paths for this processor.

        Used for:
        - Checking if outputs already exist (skip re-running)
        - Linking processors in pipeline
        - Validation

        Returns:
            Dictionary mapping output names to Path objects
        """
        pass

    def get_name(self) -> str:
        """
        Get the processor name (class name).

        Returns:
            Processor class name
        """
        return self.__class__.__name__

    def log_start(self, message: str = None) -> None:
        """
        Log the start of processing with a section header.

        Args:
            message: Optional custom message. If None, uses processor name.
        """
        if message is None:
            message = f"STARTING {self.get_name().upper()}"
        self.context.logger.section_header(message)

    def log_complete(self, result: ProcessorResult) -> None:
        """
        Log completion of processing.

        Args:
            result: ProcessorResult to log
        """
        if result.success:
            self.context.logger.info(f"✓ {self.get_name()} completed successfully")
        else:
            self.context.logger.error(f"✗ {self.get_name()} failed: {result.error}")

    def __repr__(self) -> str:
        """String representation of processor."""
        return f"{self.get_name()}(trial={self.context.path_manager.trial_name})"