"""Stable motif colors shared by overview, barcode and read presentations."""
import colorsys
import hashlib

# Canonical repeats are context, never a TVR category. Preset variants receive
# distinct colors; reverse complements share the same biological motif color.
PRESET = dict(zip(
    ('TCAGGG', 'TGAGGG', 'TTGGGG', 'CGAGGG', 'CTAGGG', 'CTGGGG',
     'TAAGGG', 'TCCGGG', 'TTCGGG', 'CTAGG', 'AACCGC'),
    ('#E69F00', '#009E73', '#D55E00', '#8B5FC7', '#CC79A7', '#007F86',
     '#9B6B30', '#739C21', '#DB527D', '#5066A5', '#A58A00')))


# These exported long motifs previously hashed to several near-identical greens.
# Explicit colors make this common panel distinct and stable across barcodes.
PRESET.update({
    'AACCGC': '#E87524',
    'CCCCTAGAACTCTTA': '#159D9A',
    'CCCCTAGTACGCTCTA': '#8657B5',
    'CCCCTAGTTCGCTCTA': '#D64D64',
    'CCCCTAGTTGACTA': '#C99B20',
})


def motif_color(label):
    """Keep a motif's color stable even when another barcode lacks that motif."""
    if label.endswith(' (canonical)'):
        return '#3979CC'
    motif = label.upper()
    reverse = motif.translate(str.maketrans('ACGT', 'TGCA'))[::-1]
    for key in (motif, reverse):
        if key in PRESET:
            return PRESET[key]
    # User-defined motifs get deterministic hues rather than one purple fallback.
    key = min(motif, reverse)
    hue = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) / 0x100000000
    rgb = colorsys.hls_to_rgb(hue, .46, .62)
    return '#' + ''.join(f'{round(channel * 255):02X}' for channel in rgb)
