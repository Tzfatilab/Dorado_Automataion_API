"""Display NanoTel's saved text results without recalculating statistics."""
from html import escape
from pathlib import Path
import re
import math


def results_section(barcode, results_root):
    """Prefer the normal barcode directory; support older summaries folders."""
    heading = '<section class="barcode-results"><h2><span class="number">2</span>Telomere Completeness &amp; Kaplan-Meier Estimate</h2>'
    if results_root is None:
        return heading + '<p class="note">Saved results unavailable.</p></section>'
    root = Path(results_root)
    name = barcode.label + '_results.txt'
    paths = [p for p in root.rglob(name) if p.parent.name == barcode.label]
    if not paths:
        paths = [p for p in root.rglob(name)
                 if p.parent.name == 'summaries' and p.parent.parent.name == barcode.label]
    if len(paths) != 1:
        return heading + '<p class="note">Saved results unavailable or ambiguous.</p></section>'
    text = paths[0].read_text(encoding='utf-8-sig')
    # Parse only known exported measurements; missing values stay unavailable.
    fields = dict(line.split(':', 1) for line in text.splitlines() if ':' in line)
    fields = {key.strip(): value.strip() for key, value in fields.items()}
    def number(key):
        raw = fields.get(key, '').replace(',', '')
        match = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)\s*(?:bp|%)?', raw)
        return float(match[1]) if match and math.isfinite(float(match[1])) else None
    complete = number('Complete Telomeric Reads')
    incomplete = number('Incomplete Telomeric Reads')
    total = number('Number of telomeric reads (post-filtration)')
    median = number('KM Median Telomeric Length')
    width = number('KM Whole Relative CI Width')
    ci = re.fullmatch(r'([0-9,]+(?:\.[0-9]+)?)\s*[-\u2013\u2014]\s*([0-9,]+(?:\.[0-9]+)?)\s*bp',
                      fields.get('KM Median 95% Confidence Interval', ''))
    low, high = (map(lambda v: float(v.replace(',', '')), ci.groups()) if ci else (None, None))
    help_index = 0
    def tip(message):
        """Native buttons support mouse, touch, Enter and Space offline."""
        nonlocal help_index
        help_index += 1
        target = 'km-help-' + barcode.id + '-' + str(help_index)
        action = "const p=document.getElementById(this.getAttribute('aria-controls'));p.hidden=!p.hidden;this.setAttribute('aria-expanded',String(!p.hidden));"
        return ('<button type="button" class="km-info" aria-label="Show explanation" aria-expanded="false" aria-controls="'
                + escape(target, quote=True) + '" onclick="' + escape(action, quote=True) + '">?</button>'
                + '<span class="km-help-text" id="' + escape(target, quote=True) + '" hidden>'
                + escape(message) + '</span>')
    bar = '<p class="note">Completeness unavailable</p>'
    if (complete is not None and incomplete is not None and total and total > 0
            and complete + incomplete == total):
        cp, ip = 100 * complete / total, 100 * incomplete / total
        bar = (f'<div class="completeness-bar" role="img" aria-label="{cp:.1f}% complete, {ip:.1f}% incomplete">'
               f'<span style="width:{cp}%"></span><span style="width:{ip}%"></span></div>'
               f'<div class="completeness-labels"><span><b>{complete:,.0f}</b> complete ({cp:.1f}%)</span>'
               f'<span><b>{incomplete:,.0f}</b> incomplete ({ip:.1f}%)</span></div>')
    short = '<p class="note">Short-telomere percentage unavailable</p>'
    for key in fields:
        threshold = re.fullmatch(r'% of telomeres shorter than ([0-9,]+) bp', key)
        value = number(key)
        if threshold and value is not None and 0 <= value <= 100:
            short = (f'<div class="km-card short-card"><span class="short-icon" aria-hidden="true">&#9602;&#9605;&#9607;</span>'
                     f'<span><b>Short telomeres</b><br>&lt; {int(threshold[1].replace(",", "")):,} bp</span>'
                     f'<strong>{value:.1f}%</strong></div>')
            break
    estimate = '<p class="note">KM estimate or confidence interval unavailable</p>'
    if median is not None and low is not None and 0 <= low <= median <= high:
        # The dot position respects the exported CI; rounding affects labels only.
        dot = 180 if high == low else 60 + 240 * (median-low) / (high-low)
        estimate = (f'<svg class="km-interval" viewBox="0 0 360 112" role="img" aria-label="KM median {median/1000:.2f} kb; 95% confidence interval {low/1000:.2f} to {high/1000:.2f} kb">'
                    f'<path d="M60 26H300 M60 18V34 M300 18V34"/><path class="km-center-line" d="M{dot} 8V45"/>'
                    f'<circle cx="{dot}" cy="26" r="6"/>'
                    f'<text x="48" y="75">{low/1000:.2f} kb</text><text class="km-median" x="180" y="75">{median/1000:.2f} kb</text>'
                    f'<text x="312" y="75">{high/1000:.2f} kb</text><text x="180" y="100">KM median</text></svg>'
                    f'<div class="km-card km-ci"><b>95% CI: {low/1000:.2f} &ndash; {high/1000:.2f} kb</b><br>'
                    + (f'Relative CI width: {width:.1f}% ' if width is not None else 'Relative CI width unavailable ')
                    + tip('Relative CI width = (upper confidence limit - lower confidence limit) / KM median x 100. A smaller percentage indicates a narrower interval relative to the estimated median. This is uncertainty in the estimate, not the spread of individual telomere lengths.') + '</div>')
    return (heading + '<div class="km-grid"><div><h3>Read completeness '
            + tip('Complete reads have a telomere length treated as fully observed by NanoTel. Incomplete (censored) reads provide an observed length that is a lower bound: the telomere may continue beyond the read. The green and pink segments show their proportions among the exported post-filtered reads. Pink ticks below the length histogram mark censored observations, not TVRs.')
            + '</h3>' + bar + short + '</div><div><h3>Kaplan-Meier telomere length '
            + tip('Kaplan-Meier estimates the telomere-length distribution while accounting for incomplete (censored) measurements. The dot shows the exported KM median; the horizontal line shows its 95% confidence interval. This interval describes uncertainty in the median estimate, not a range containing 95% of reads. Values come from NanoTel; this dashboard does not refit the estimate.')
            + '</h3>' + estimate + '</div></div><details class="note km-source"><summary>Source results</summary><pre>'
            + escape(text) + '</pre></details></section>')
