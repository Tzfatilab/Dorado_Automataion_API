"""
Dorado Workflow Package
=======================

A modular workflow system for processing Oxford Nanopore sequencing data
with Dorado basecaller, demultiplexing, NanoTel telomere analysis,
alignment, and downstream R analysis.

Package Structure:
-----------------
- processors/: Core processing modules (basecalling, demuxing, alignment, etc.)
- operators/: Workflow orchestration (WorkflowOperator)
- managers/: Configuration, path, and barcode management
- utils/: Logging and command execution utilities

Main Entry Point:
----------------
Use main.py or import WorkflowOperator for programmatic access.

Example Usage:
-------------
    from dorado_workflow import WorkflowOperator, WorkflowContext
    from dorado_workflow.managers import ConfigManager, PathManager
    from dorado_workflow.utils import WorkflowLogger, CommandExecutor

    # Initialize dependencies
    config = ConfigManager()
    path_mgr = PathManager("Trial_75", config_manager=config)
    logger = WorkflowLogger(path_mgr.get_log_file_path())
    executor = CommandExecutor(logger)
    barcode_mgr = BarcodeManager()

    # Create context and operator
    context = WorkflowContext(logger, config, path_mgr, barcode_mgr, executor)
    operator = WorkflowOperator(context)

    # Run workflow
    operator.run_pod5_workflow("/path/to/pod5", organism="mouse")
"""

__version__ = "2.0.0"
__author__ = "Dorado Workflow Team"

# Core workflow components
from .operators.workflow_operator import WorkflowOperator

# Base classes for processors
from .processors.base import ProcessorBase, ProcessorResult, WorkflowContext

# Manager classes
from .managers.config_manager import ConfigManager
from .managers.path_manager import PathManager
from .managers.barcode_manager import BarcodeManager

# Utility classes
from .utils.logger import WorkflowLogger
from .utils.command_executor import CommandExecutor

# Expose main classes at package level
__all__ = [
    # Operators
    'WorkflowOperator',

    # Base classes
    'ProcessorBase',
    'ProcessorResult',
    'WorkflowContext',

    # Managers
    'ConfigManager',
    'PathManager',
    'BarcodeManager',

    # Utils
    'WorkflowLogger',
    'CommandExecutor',
]