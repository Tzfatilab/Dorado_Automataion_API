"""
Managers Package
===============

Manager classes for the Dorado workflow.

This package provides:
- ConfigManager: Configuration loading and management
- PathManager: Directory and file path management (to be implemented)
- BarcodeManager: Barcode tracking and management (to be implemented)
"""

from .config_manager import ConfigManager
from .path_manager import PathManager
from .barcode_manager import BarcodeManager

__all__ = ['ConfigManager', 'PathManager', 'BarcodeManager']
