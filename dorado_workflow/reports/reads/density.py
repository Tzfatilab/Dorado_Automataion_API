"""Source-only adapters for the interactive per-read density and motif tracks."""
from pathlib import Path
from dorado_workflow.reports.shared.colors import motif_color


def mismatch_enabled(settings):
    """Use the recorded option, not the existence of a duplicated export series."""
    if not settings or settings.status != 'available' or not isinstance(settings.value, dict):
        return None
    options = settings.value.get('nanotel_analysis', settings.value)
    value = options.get('max_mismatch') if isinstance(options, dict) else None
    if type(value) not in (int, float, str):
        return None
    if value in (0, '0'):
        return False
    if value in (1, '1'):
        return True
    return None


def saved_read_sequence(folder, serial, header, length):
    """Load NanoTel's analyzed-orientation FASTA, verifying identity and length.

    Do not fall back to raw FASTQ: its orientation may differ from the plots.
    """
    import gzip
    import re
    if folder is None or serial is None or length is None:
        return None
    folder = Path(folder)
    try:
        number = int(serial)
    except (ValueError, TypeError):
        return None
    names = (f'{folder.name}_read{number}', f'read{number}')
    for directory in (folder / 'reads', folder):
        for name in names:
            for suffix in ('.fasta.gz', '.fasta'):
                path = directory / (name + suffix)
                if not path.is_file():
                    continue
                opener = gzip.open if suffix.endswith('.gz') else open
                try:
                    with opener(path, 'rt', encoding='utf-8') as stream:
                        title = stream.readline().strip()
                        sequence = ''.join(line.strip() for line in stream).upper()
                except (OSError, EOFError, UnicodeError):
                    continue
                if (title.startswith('>') and title[1:].split()[0] == header.split()[0]
                        and len(sequence) == length and re.fullmatch('[ACGTRYSWKMBDHVN]+', sequence)):
                    return sequence
    return None


def read_track_data(read, folder=None):
    """Package exported samples without recalculating densities or telomere calls.

    The optional folder argument is retained for callers; JPEGs are no longer
    duplicated into the dashboard. NanoTel's original plot files stay on disk.
    Internal coordinates are zero-based half-open; window starts are converted
    back to source positions by the browser when drawing the density curve.
    """
    if read is None:
        return None
    result = dict(density={}, motifs=None, intervals={}, alignments=[])
    quality = read.metrics.get('mean_read_quality')
    result['mean_read_quality'] = quality.value if quality and quality.status == 'available' else None
    serial, length = read.metrics.get('read_number'), read.metrics.get('read_length')
    result['sequence'] = saved_read_sequence(folder,
        serial.value if serial and serial.status == 'available' else None,
        read.original_id, length.value if length and length.status == 'available' else None)
    for method, call in read.calls.items():
        interval = call.get('interval')
        if interval and interval.status == 'available':
            result['intervals'][method] = [interval.value['start'], interval.value['end']]
    density = read.tracks.get('density')
    if density and density.status == 'available':
        for sample in density.value:
            result['density'].setdefault(sample['method'], []).append(
                [sample['start'], sample['end'], sample['density']])
        for samples in result['density'].values():
            samples.sort(key=lambda sample: sample[0])
    fact = read.tracks.get('motifs')
    if fact and fact.status == 'available' and 'tvr_inclusive' in fact.value['methods']:
        groups = {}
        for hit in fact.value['matches']:
            if hit['method'] == 'tvr_inclusive':
                groups.setdefault((hit['motif'], hit['role']), []).append([hit['start'], hit['end']])
        result['motifs'] = [dict(label=motif + (' (canonical)' if role == 'canonical' else ''),
            role=role, color=motif_color(motif + (' (canonical)' if role == 'canonical' else '')),
            positions=positions) for (motif, role), positions in sorted(groups.items())]
    # Reference mappings are shown as annotations, never projected onto read
    # coordinates without an exported query interval and transformation.
    if read.alignments.status == 'available':
        for record in read.alignments.value:
            result['alignments'].append({key: value.value for key, value in record.items()
                if key in ('reference', 'chromosome', 'arm', 'strand', 'normalized')
                and value.status == 'available'})
    return result


# Keep browser presentation separate from Python data preparation. The asset is
# embedded in the generated HTML, so the report remains usable offline.
READ_TRACK_SCRIPT = '<script>\n' + (Path(__file__).parents[1] / 'assets' / 'read_density.js').read_text(encoding='utf-8') + '\n</script>'
