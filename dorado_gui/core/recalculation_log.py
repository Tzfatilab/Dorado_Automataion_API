"""Compact presentation of streamed Recalculate output; source logs stay intact."""
import re


class RecalculationLog:
    def __init__(self):
        self.json_depth = 0
        self.table = False
        self.barcode = None
        self.total = None
        self.index = 0
        self.input_reads = None
        self.last_mapping = None

    def format(self, line):
        line = line.strip()
        important = re.search(r'\b(?:warning|error|failed|failure|halted|traceback|cancelled)\b', line, re.I)
        # Diagnostics must survive even if they interrupt a configuration/table dump.
        if important:
            self.table = False
            match = re.search(r'Missing analysis values in (\d+) row\(s\) of (barcode\d+)_summary\.csv', line, re.I)
            if match:
                count = int(match[1])
                subject = '1 read has' if count == 1 else f'{count} reads have'
                return f'WARNING: {match[2].lower()}: {subject} missing analysis values.'
            match = re.search(r'Empty NanoTel dataset: (barcode\d+)_summary\.csv', line, re.I)
            if match:
                return f'WARNING: {match[1].lower()}: no telomeric reads to filter.'
            return line
        if self.json_depth or line == '{':
            # Ignore braces inside quoted JSON strings, including escaped quotes.
            structure = re.sub(r'"(?:\\.|[^"\\])*"', '', line)
            self.json_depth = max(0, self.json_depth + structure.count('{') - structure.count('}'))
            return None
        if line == 'NanoTel Summary Statistics:' or line.startswith('Generating summary statistics across all barcodes') or line.startswith('<chr>'):
            self.table = True
            return None
        if self.table:
            if re.match(r'^(?:\d+\s|barcode\b|\w+_|<|#|$)', line):
                return None
            self.table = False
        match = re.match(r'Found (\d+) NanoTel summary files$', line, re.I)
        if match:
            self.total = int(match[1])
            return f'Refiltering {self.total} barcodes'
        match = re.match(r'(?:Processing NanoTel file:\s*|Refiltering )(barcode\d+)(?:_summary\.csv)?', line, re.I)
        if match:
            self.barcode = match[1].lower()
            self.index += 1
            self.input_reads = None
            return None
        match = re.match(r'Applied density and start position filters:\s*(\d+)\s*->', line)
        if match:
            self.input_reads = int(match[1])
            return None
        if line.startswith('Applied minimum read length filter:'):
            return None
        match = re.match(r'Final filtering complete:\s*\d+\s*->\s*(\d+) reads for (barcode\d+)', line, re.I)
        if match:
            count = f'{int(match[1]):,}'
            population = f' of {self.input_reads:,}' if self.input_reads is not None else ''
            progress = f'[{self.index}/{self.total}] ' if self.total else ''
            return f'{progress}{match[2].lower()}: {count}{population} telomeric reads passed'
        match = re.match(r'Processing \d+ BAM files for barcode:\s*(barcode\d+)', line, re.I)
        if match:
            barcode = match[1].lower()
            if barcode == self.last_mapping:
                return None
            self.last_mapping = barcode
            return 'Refiltering saved mapping: ' + barcode
        if re.match(r'STEP 1: NANOTEL ANALYSIS', line, re.I):
            return 'Telomere filtering'
        if re.match(r'STEP 2: MAPPING ANALYSIS', line, re.I):
            return 'Saved mapping filtering'
        match = re.match(r'Completed processing for (barcode\d+) - Total reads:\s*(\d+)', line, re.I)
        if match:
            return f'{match[1].lower()}: {int(match[2]):,} reads passed mapping filters'
        if line.startswith('Generating All Barcodes dashboard and Excel workbook'):
            return 'Generating dashboard and Excel workbook...'
        if line.startswith('Post-analysis trimming:'):
            return line.replace('Post-analysis trimming:', 'Input trimming:', 1)
        if line.startswith('Post-analysis complete:'):
            return 'Dashboard ready: ' + line.split(':', 1)[1].strip()
        if not line or set(line) <= {'=', '-', '#', ' '}:
            return None
        if re.match(
            r'^(?:DEBUG\b|Starting |Command:|Location:|Exit code:\s*0$|'
            r'Successfully (?:read|wrote):|Loaded (?:alignment|NanoTel) data:|'
            r'Created |Creating |Extracting read IDs|Extracted \d+ unique read IDs|'
            r'After (?:NanoTel matching|removing unmapped|MAPQ/position filtering):|'
            r'BAM file:|Processing BAM file |Processing mapping for barcode:|'
            r'Processing (?:barcodes|NanoTel files):|Configuration loaded|'
            r'(?:Input directory|Output directory|Base output directory|BAM directory|Filtered NanoTel dir|Alignment summary):|'
            r'(?:Density threshold|Max telomere start|Maximum edge distance|Minimum read length):|'
            r'Looking for |All .*prerequisites validated|Validating .*prerequisites|'
            r'All required packages loaded|Found |Unique barcodes found:|Barcode BARCODE\d+\s*:|'
            r'Generating (?:summary statistics|NanoTel analysis report|mapping analysis report|comprehensive pipeline report)|'
            r'(?:Summary statistics|Analysis report|Mapping report|Complete pipeline report) saved to:|'
            r'(?:NanoTel|Mapping) batch analysis completed|Batch processing complete|Processed \d+ barcodes|'
            r'Skipping methylation analysis|Output directories initialized|KM disabled for recalculation|'
            r'Post-analysis(?:$| steps:|: restoring)|Running post-analysis pipeline|'
            r'(?:OK\s+)?(?:.*NanoTel analysis completed successfully|Analysis completed successfully)|'
            r'Mapping filter mode:)', line, re.I):
            return None
        return line
