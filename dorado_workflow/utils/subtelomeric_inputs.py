"""Read NanoTel's already-cut mapping FASTA; never reread or recut FASTQ.

NanoTel exports before-filter flanks in Full and Summary only when mapping is
requested. Coordinates are carried in that temporary FASTA, not a sidecar file.
The workflow owns its lifetime. Reanalyze uses saved BAMs and skips this step.
"""
import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re


BOUNDARY_COLUMNS = {
    "exact": ("Telomere_start", "Telomere_end"),
    "mismatch": ("Telomere_start_mismatch", "Telomere_end_mismatch"),
    "variant_inclusive": ("Telomere_start_mismatch_tvr", "Telomere_end_mismatch_tvr"),
}
_MISSING = {"", "NA", "NaN", "nan"}


def _integer(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number != number.to_integral_value():
            raise ValueError("Expected an integral coordinate or length.")
        return int(number)
    except (InvalidOperation, TypeError) as error:
        raise ValueError("Expected an integral coordinate or length.") from error


@dataclass(frozen=True)
class PreparedSubtelomericInputs:
    """Existing NanoTel FASTA and small in-memory transforms, without DNA copies."""
    fasta: Path
    barcode: str
    boundary_method: str
    coordinates: dict
    source_rows: int
    no_subtelomere: int
    missing_boundary: int

    @property
    def queries(self):
        return len(self.coordinates)


def _fasta_records(stream, check_cancelled):
    """Read headers and sequence lengths, retaining no complete sequence strings."""
    header, length = None, 0
    for line in stream:
        check_cancelled()
        line = line.rstrip("\r\n")
        if line.startswith(">"):
            if header is not None:
                yield header, length
            header, length = line[1:], 0
        else:
            if header is None or not re.fullmatch(r"[ACGTRYSWKMBDHVNacgtryswkmbdhvn]+", line):
                raise ValueError("Invalid sequence in NanoTel subtelomeric FASTA.")
            length += len(line)
    if header is not None:
        yield header, length


def prepare_subtelomeric_inputs(summary_csv, query_fasta, *, boundary_method,
                               check_cancelled=None):
    """Validate NanoTel's direct export and link temporary query IDs to source rows.

    The original before-filter summary supplies read IDs. The FASTA supplies
    cut coordinates and orientation, including an initial comment for an empty
    export. Python validates the link; it never searches, cuts or complements
    sequences. All coordinate intervals here are 0-based half-open.
    """
    check_cancelled = check_cancelled or (lambda: None)
    check_cancelled()
    summary_csv, query_fasta = Path(summary_csv), Path(query_fasta)
    match = re.fullmatch(r"(barcode\d+)_summary\.csv", summary_csv.name)
    if not match or boundary_method not in BOUNDARY_COLUMNS:
        raise ValueError("An original barcodeXX_summary.csv and explicit boundary method are required.")
    with query_fasta.open(encoding="utf-8") as stream:
        metadata = re.fullmatch(
            r";nanotel_subtelomeric_v1 rc=([01]) right_edge=([01]) method=(exact|mismatch|variant_inclusive)",
            stream.readline().rstrip("\r\n"))
        if metadata is None or metadata[3] != boundary_method:
            raise ValueError("Missing or inconsistent NanoTel subtelomeric export metadata.")
        reversed_read, right_edge = metadata[1] == "1", metadata[2] == "1"
        start_column, end_column = BOUNDARY_COLUMNS[boundary_method]
        expected, source_names = {}, set()
        counts = dict(source_rows=0, no_subtelomere=0, missing_boundary=0)
        serials = set()
        with summary_csv.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            required = {"Serial", "sequence_ID", "sequence_length", start_column, end_column}
            if not required.issubset(reader.fieldnames or ()):
                raise ValueError("NanoTel source summary is missing identity or boundary columns.")
            for row in reader:
                check_cancelled()
                counts["source_rows"] += 1
                serial = _integer(row["Serial"])
                header = row["sequence_ID"]
                name = header.split()[0] if header and header.split() else ""
                # SAM omits FASTQ comments, so distinct full headers must not
                # collapse onto the same read name in the downstream join.
                if (serial <= 0 or serial in serials or name in source_names
                        or not re.fullmatch(r"[!-?A-~]{1,254}", name)):
                    raise ValueError("Missing or ambiguous NanoTel source read identity.")
                serials.add(serial)
                source_names.add(name)
                values = [row[start_column], row[end_column]]
                if any(value in _MISSING for value in values):
                    counts["missing_boundary"] += 1
                    continue
                start, end = map(_integer, values)
                length = _integer(row["sequence_length"])
                if not 1 <= start <= end <= length:
                    raise ValueError("Invalid saved NanoTel telomere boundary.")
                a, b = (0, start-1) if right_edge else (end, length)
                if a == b:
                    counts["no_subtelomere"] += 1
                    continue
                # Coordinate arithmetic only: the DNA was already cut by R.
                lo, hi = (length-b, length-a) if reversed_read else (a, b)
                query_id = f"subtelo_{serial}"
                expected[query_id] = dict(read_id=header, source_serial=serial,
                    status="ready", query_id=query_id, boundary_method=boundary_method,
                    telomere_start=start, telomere_end=end, original_length=length,
                    original_start=lo, original_end=hi, analyzed_start=a, analyzed_end=b,
                    analyzed_reverse_complemented=reversed_read,
                    query_reverse_complemented=reversed_read != right_edge)
        seen = set()
        for header, sequence_length in _fasta_records(stream, check_cancelled):
            fields = re.fullmatch(r"(subtelo_[1-9]\d*) start=(\d+) end=(\d+) length=(\d+)", header)
            if fields is None or fields[1] not in expected or fields[1] in seen:
                raise ValueError("Unexpected or duplicate NanoTel subtelomeric query.")
            query = expected[fields[1]]
            values = tuple(map(int, fields.group(2, 3, 4)))
            if (values != (query["original_start"], query["original_end"], query["original_length"])
                    or sequence_length != query["original_end"]-query["original_start"]):
                raise ValueError("Exported subtelomere disagrees with its saved NanoTel call.")
            seen.add(fields[1])
        if seen != set(expected):
            raise ValueError("NanoTel subtelomeric FASTA is missing expected source reads.")
    return PreparedSubtelomericInputs(fasta=query_fasta, barcode=match[1],
        boundary_method=boundary_method, coordinates=expected, **counts)
