"""Readable run identity for standalone report headers and filenames."""
from pathlib import Path
import re


def result_run_label(results):
    root = Path(results)
    return root.parent.name if root.name.lower() == 'results' else root.name


def dashboard_filename(label, *, summary=False):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(label)).strip(' .')[:120].rstrip(' .') or 'Run'
    return ('Dashboard_Summary_' if summary else 'Dashboard_') + name + '.html'


def summary_dashboard_path(results):
    return Path(results) / dashboard_filename(result_run_label(results), summary=True)
