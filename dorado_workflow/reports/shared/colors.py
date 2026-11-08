"""Stable motif colors shared by overview, barcode and read presentations."""
import colorsys
import hashlib

# Canonical repeats are context, never a TVR category. Preset variants receive
# distinct colors; reverse complements share the same biological motif color.
PRESET = {
    'TCAGGG': '#D5B800',  # mustard
    'TGAGGG': '#008060',  # emerald
    'TTGGGG': '#A62128',  # brick
    'CGAGGG': '#C218A8',  # magenta
    'CTAGGG': '#E7A8B8',  # blush
    'CTGGGG': '#16BAC5',  # cyan
    'TAAGGG': '#7C4A21',  # brown
    'TCCGGG': '#91BA22',  # lime
    'TTCGGG': '#172653',  # navy
    'CTAGG': '#6F6D00',   # olive
    'AACCGC': '#E87524',
    'CCCCTAGAACTCTTA': '#005566',  # deep teal
    'CCCCTAGTACGCTCTA': '#255B2A',  # forest
    'CCCCTAGTTCGCTCTA': '#EF476F',  # rose
    'CCCCTAGTTGACTA': '#B9A5E8',    # lavender
}


def motif_color(label):
    """Keep a motif's color stable even when another barcode lacks that motif.

    Args:
        label: Display label.

    Returns:
        Deterministic hexadecimal display color for the motif label.
    """
    if label.endswith(' (canonical)'):
        return '#3979CC'
    # Mismatch sequences are combined into one presentation category.
    if label == 'Mismatch':
        return '#7C3AED'
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
