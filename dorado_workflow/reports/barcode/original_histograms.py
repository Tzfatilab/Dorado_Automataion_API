"""Batch access to the original NanoTel histogram builder, shared with analysis."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from ..reads.browser import read_rows
from ..reads.density import mismatch_enabled


def original_histograms(barcodes, settings):
    """Build original figures over the current exported post-filtered reads.

    Args:
        barcodes: Barcode records needing a regenerated histogram.
        settings: Recorded settings used to label the exact/mismatch calling mode.

    Returns:
        Figure dictionary indexed by barcode ID. Missing populations are omitted.
        Raises RuntimeError if the original R renderer cannot run; no alternate
        histogram implementation is substituted.
    """
    mode = mismatch_enabled(settings)
    if mode is None:
        return {}
    requests = []
    for barcode in barcodes:
        rows = read_rows(barcode)
        if rows is None or any(row['telomere'] is None for row in rows):
            continue
        requests.append(dict(id=barcode.id, barcode=barcode.label, mismatch_allowance=int(mode),
            lengths_bp=[row['telomere'] for row in rows], read_ids=[row['header'] for row in rows]))
    if not requests:
        return {}
    executable = shutil.which('Rscript')
    if executable is None:
        raise RuntimeError('Rscript is required to rebuild the original NanoTel histogram')
    renderer = Path(__file__).parents[2] / 'data' / 'render_nanotel_histograms.R'
    # One R process serves all barcodes. Temporary requests and figures are
    # removed after import, keeping the dashboard as the final artifact.
    with tempfile.TemporaryDirectory(prefix='nanotel-histograms-') as directory:
        request_path = Path(directory) / 'requests.json'
        output_path = Path(directory) / 'figures.json'
        request_path.write_text(json.dumps(requests, allow_nan=False), encoding='utf-8')
        result = subprocess.run([executable, '--vanilla', str(renderer), str(request_path), str(output_path)],
            capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode != 0:
            raise RuntimeError('Original NanoTel histogram generation failed: ' + result.stderr.strip())
        return json.loads(output_path.read_text(encoding='utf-8-sig'))
