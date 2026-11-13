"""Discover one project's inputs without descending into recalculated runs."""
import fnmatch
import os
import re
from pathlib import Path

RECALCULATED_FOLDER = "Recalculated results"


def barcode_directories(nanotel):
    """Find barcode folders in both current and legacy report layouts."""
    root = Path(nanotel)
    return sorted(folder for base in (root, root / 'supporting_data')
                  for folder in base.glob('barcode*')
                  if folder.is_dir() and re.fullmatch(r'barcode\d+', folder.name, re.I))


def source_files(root, pattern="*"):
    root = Path(root)
    for directory, folders, files in os.walk(root):
        parent = Path(directory)
        folders[:] = [name for name in folders
                      if name != RECALCULATED_FOLDER
                      and not (parent / name / "results/reports/post_analysis_source.json").is_file()
                      and not (parent / name / "reports/post_analysis_source.json").is_file()]
        for name in files:
            if fnmatch.fnmatch(name, pattern):
                yield parent / name
