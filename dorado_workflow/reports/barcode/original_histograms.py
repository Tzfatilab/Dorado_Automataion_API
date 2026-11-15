"""Batch access to the original NanoTel histogram builder, shared with analysis."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

def original_histograms(requests):
    """Render recorded length populations in one shared NanoTel R process.

    Requests contain stable IDs, source lengths and the recorded matching mode.
    Missing populations are omitted by the caller; empty populations are explicit.
    """
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
