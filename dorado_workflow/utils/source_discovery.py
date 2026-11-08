"""Discover one project's inputs without descending into recalculated runs."""
import fnmatch
import os
from pathlib import Path

RECALCULATED_FOLDER = "Recalculated results"


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
