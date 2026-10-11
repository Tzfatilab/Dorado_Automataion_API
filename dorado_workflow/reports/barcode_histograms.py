"""Embed existing NanoTel histogram HTML without regenerating its statistics."""
from html import escape
from pathlib import Path
from html.parser import HTMLParser
import json
import hashlib
import re


class _FigureParser(HTMLParser):
    """Read only NanoTel's saved JSON figure; never execute source HTML."""
    def __init__(self):
        super().__init__()
        self.inside = False
        self.parts = []
        self.count = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('id') == 'figure':
            self.inside = True
            self.count += 1

    def handle_data(self, data):
        if self.inside:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'script':
            self.inside = False


def histogram_sections(run, results_root=None):
    """Section 2 uses the original histogram and its unit controls."""
    return _saved_plot_sections(run, results_root, 'histogram', 2,
        'Telomere Length Distribution',
        'Saved NanoTel histogram; original count/percentage controls and population are preserved. '
        'NanoTel final-filtered reads may differ from the R post-analysis population in the cards above.')


def telomere_plot_sections(run, results_root=None):
    """Section 3 preserves the original per-read plot, including its axes."""
    return _saved_plot_sections(run, results_root, 'plot', 3,
        'Telomere and Read Length per Read',
        'Saved NanoTel per-read plot. Original traces, running median, axes and pre-final-filter population are preserved.')


def _saved_plot_sections(run, results_root, kind, number, title, note):
    """Reuse the figure saved in NanoTel's histogram HTML, with no recalculation.

    Extract JSON, not executable HTML. The parent report supplies offline Plotly.
    Duplicate files and unsupported legacy HTML remain explicitly unavailable.
    """
    found = {}
    specifications = {}
    if results_root is not None:
        root = Path(results_root).resolve()
        for path in root.rglob(f'*_telomere_{kind}.html'):
            if path.is_file() and path.resolve().is_relative_to(root):
                found.setdefault(path.name.lower(), []).append(path)
        for path in root.rglob(f'*_telomere_{kind}.plotly.json'):
            if path.is_file() and path.resolve().is_relative_to(root):
                specifications.setdefault(path.name.lower(), []).append(path)
    sections = {}
    for barcode in run.barcodes:
        paths = specifications.get(f'{barcode.label}_telomere_{kind}.plotly.json'.lower(), []) or found.get(f'{barcode.label}_telomere_{kind}.html'.lower(), [])
        # Use the numbered dashboard heading as the single visible plot title.
        heading = (f'<section><div class="histogram-heading"><h2><span class="number">{number}</span>'
                   f'{title}</h2><div class="histogram-controls" '
                   'role="group" aria-label="Histogram units"></div></div>')
        reason = ''
        if len(paths) != 1:
            reason = (f'Multiple matching {kind} files; select an unambiguous results directory.' if paths else
                      f'Saved NanoTel {kind} not available. Summary-only runs do not generate this plot.')
        else:
            path = paths[0]
            raw = path.read_bytes()
            try:
                if path.name.endswith('.plotly.json'):
                    figure = json.loads(raw.decode('utf-8-sig'))
                else:
                    parser = _FigureParser()
                    parser.feed(raw.decode('utf-8-sig'))
                    if parser.count != 1:
                        raise ValueError('Ambiguous figure')
                    figure = json.loads(''.join(parser.parts))
                if not isinstance(figure, dict) or not isinstance(figure.get('data'), list) or not isinstance(figure.get('layout'), dict):
                    raise ValueError('Unsupported figure schema')
                # R's older Plotly serializes titles as strings. Plotly 6 needs
                # title objects for saved updates such as yaxis.title.text.
                # Normalize presentation metadata only; source files, bins and
                # the saved count/percentage arrays remain unchanged.
                layout = figure['layout']
                if isinstance(layout.get('title'), str):
                    layout['title'] = {'text': layout['title']}
                # Hide the duplicate title only in this embedded copy. Keep
                # annotations/subtitles, scientific data and source HTML intact.
                layout['title'] = {'text': ''}
                # The dashboard supplies the title and unit buttons, so the
                # saved plot's large title/menu margin is no longer needed.
                if not isinstance(layout.get('margin', {}), dict):
                    raise ValueError('Invalid plot margins')
                layout.setdefault('margin', {})['t'] = 24
                for key, axis in layout.items():
                    if re.fullmatch(r'[xy]axis\d*', key) and isinstance(axis, dict) and isinstance(axis.get('title'), str):
                        axis['title'] = {'text': axis['title']}
                # Escaping script delimiters prevents source labels closing the
                # JSON element. Values and histogram bins are retained verbatim.
                payload = json.dumps(figure, ensure_ascii=True, allow_nan=False).replace('<', '\\u003c')
            except (ValueError, UnicodeError, TypeError):
                reason = f'Saved {kind} has missing or invalid Plotly figure data.'
        if reason:
            sections[barcode.id] = heading + f'<p class="note">{reason}</p></section>'
            continue
        source = escape(path.relative_to(root).as_posix())
        digest = hashlib.sha256(raw).hexdigest()
        sections[barcode.id] = (heading + '<div class="saved-histogram"></div>'
            f'<script type="application/json" class="histogram-figure">{payload}</script>'
            f'<p class="note">{escape(note)}</p>'
            f'<details class="note"><summary>Plot source</summary>{source}<br>SHA-256: {digest}</details></section>')
    return sections
