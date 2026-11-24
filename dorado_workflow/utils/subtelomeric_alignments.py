"""Project subtelomeric SAM records onto their original full-read coordinate axis.

Only omitted flanks become hard clips. No omitted bases are aligned, reference
coordinates/scores are unchanged, and no full-read sequence copies are needed.

For example, a 4,000-base query after a 6,000-base telomere may align as 4000M.
On the full forward read this becomes 6000H4000M: H records omitted bases,
whereas M records aligned bases. The 6,000 telomere bases never reach Minimap2.
Hard clips also let existing summary/report code recover the full read length.
"""
import os
from pathlib import Path
import re
import tempfile


def validate_query_coordinates(queries):
    """Validate in-memory transforms, rejecting ambiguous original SAM names."""
    source_names = set()
    for query_id, record in queries.items():
        read_id = record.get("read_id")
        if not isinstance(read_id, str) or not read_id.split():
            raise ValueError("Missing original read identity in query coordinates.")
        name = read_id.split()[0]
        if not re.fullmatch(r"[!-?A-~]{1,254}", name) or name in source_names:
            raise ValueError("Original SAM read names are invalid or ambiguous in this barcode.")
        source_names.add(name)
        if (record.get("status") != "ready" or not isinstance(query_id, str)
                or not re.fullmatch(r"subtelo_[1-9]\d*", query_id)
                or record.get("query_id") != query_id):
            raise ValueError("Invalid prepared query identity.")
        a, b, length = (record.get(key) for key in
                        ("original_start", "original_end", "original_length"))
        if (any(type(value) is not int for value in (a, b, length))
                or not 0 <= a < b <= length
                or type(record.get("query_reverse_complemented")) is not bool
                or type(record.get("analyzed_reverse_complemented")) is not bool):
            raise ValueError("Invalid full-read coordinate transform.")
        expected = ((length-b, length-a) if record["analyzed_reverse_complemented"] else (a, b))
        if (record.get("analyzed_start"), record.get("analyzed_end")) != expected:
            raise ValueError("Original and analyzed coordinate transforms disagree.")


def project_cigar(cigar, record, query_reverse):
    """Pad a reference-facing query CIGAR with omitted full-read hard clips.

    The reference-facing sequence and alignment operations do not reverse.
    Instead, the SAM reverse flag changes when the input query was itself the
    reverse complement of the original-read slice.
    """
    if not re.fullmatch(r"(?:[1-9]\d*[MIDNSHP=X])+", cigar):
        raise ValueError("Invalid extracted-query CIGAR.")
    operations = [(int(size), op) for size, op in re.findall(r"(\d+)([MIDNSHP=X])", cigar)]
    core = [i for i, (_, op) in enumerate(operations) if op not in {"S", "H"}]
    if not core or any(op in {"S", "H"} for _, op in operations[core[0]:core[-1]+1]):
        raise ValueError("Invalid internal clipping in extracted-query CIGAR.")
    if (sum(size for size, op in operations if op in {"M", "I", "S", "H", "=", "X"})
            != record["original_end"]-record["original_start"]):
        raise ValueError("CIGAR length differs from the prepared query.")
    # Two independent strand choices: how the query was extracted from FASTQ,
    # and how Minimap2 aligned it. XOR gives the strand of the original read.
    original_reverse = query_reverse != record["query_reverse_complemented"]
    before, after = record["original_start"], record["original_length"]-record["original_end"]
    # CIGAR is written facing the reference. A reverse-strand alignment needs
    # the omitted original suffix on its left and original prefix on its right.
    if original_reverse:
        before, after = after, before
    padded = ([(before, "H")] if before else []) + operations + ([(after, "H")] if after else [])
    # Supplementary alignments can already have hard clips. Combine adjacent
    # H operations rather than leaving equivalent repeated clipping segments.
    merged = []
    for size, op in padded:
        if merged and merged[-1][1] == op:
            merged[-1] = (merged[-1][0]+size, op)
        else:
            merged.append((size, op))
    return "".join(f"{size}{op}" for size, op in merged), original_reverse


def _project_sa(value, record):
    """Update the SA tag's strand/CIGAR using the same full-read transform.

    SA lists other alignments for this query. Leaving their old query clipping
    or strand would contradict the main record after coordinate restoration.
    Reference names, reference positions, MAPQ and edit counts stay unchanged.
    """
    result = []
    for item in value.rstrip(";").split(";"):
        parts = item.split(",")
        if len(parts) != 6 or parts[2] not in {"+", "-"}:
            raise ValueError("Invalid supplementary alignment tag.")
        parts[3], reverse = project_cigar(parts[3], record, parts[2] == "-")
        parts[2] = "-" if reverse else "+"
        result.append(",".join(parts))
    return ";".join(result) + ";"


def project_subtelomeric_sam(source, destination, queries, check_cancelled=None):
    """Stream and atomically publish original-read SAM; never overwrite inputs.

    All mapped candidates, including secondary/supplementary ones, survive.
    Unmapped records keep their identity but carry no partial sequence pretending
    to be a full original read. Query identities remain in a local ``zq`` tag.
    """
    validate_query_coordinates(queries)
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise FileExistsError(f"Projected SAM already exists: {destination}")
    check_cancelled = check_cancelled or (lambda: None)
    check_cancelled()
    counts = dict(mapped=0, unmapped=0)
    seen = set()
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".projected-", suffix=".sam", dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output, source.open(encoding="utf-8") as stream:
            body = False
            for line in stream:
                check_cancelled()
                if line.startswith("@"):
                    if body:
                        raise ValueError("SAM header appears after alignment records.")
                    output.write(line)
                    continue
                if not body:
                    # An internal BAM-header comment survives sorting/linking.
                    # R uses it to recognize saved subtelomeric mappings during
                    # Reanalyze; no extra table column or JSON file is needed.
                    output.write("@CO\tmapping_mode=subtelomeric; query_coordinate_space=original_read; omitted flanks are hard clips.\n")
                    body = True
                fields = line.rstrip("\r\n").split("\t")
                if len(fields) < 11 or fields[0] not in queries:
                    raise ValueError("SAM record has no unambiguous prepared query.")
                query_id = fields[0]
                record = queries[query_id]
                seen.add(query_id)
                flag = int(fields[1])
                if flag < 0 or flag & 1 or fields[6] != "*":
                    raise ValueError("Expected unpaired subtelomeric query alignments.")
                fields[0] = record["read_id"].split()[0]
                if flag & 4:
                    if fields[2] != "*" or fields[5] != "*":
                        raise ValueError("Unmapped query has inconsistent alignment fields.")
                    # With no CIGAR there is no way to express omitted flanks.
                    # Keep the read identity, but do not label a short query's
                    # sequence as though it were the complete original read.
                    fields[9:11] = ["*", "*"]
                    counts["unmapped"] += 1
                else:
                    if fields[2] == "*" or int(fields[3]) < 1:
                        raise ValueError("Mapped query has no valid reference position.")
                    old_cigar = fields[5]
                    if fields[9] != "*":
                        consumed = sum(int(n) for n, op in re.findall(r"(\d+)([MIDNSHP=X])", old_cigar)
                                       if op in {"M", "I", "S", "=", "X"})
                        if len(fields[9]) != consumed or (fields[10] != "*" and len(fields[10]) != consumed):
                            raise ValueError("SAM sequence/quality length differs from query CIGAR.")
                    fields[5], reverse = project_cigar(old_cigar, record, bool(flag & 16))
                    fields[1] = str((flag & ~16) | (16 if reverse else 0))
                    counts["mapped"] += 1
                tags = []
                for tag in fields[11:]:
                    if tag.startswith("zq:"):
                        raise ValueError("SAM already uses the query provenance tag.")
                    tags.append("SA:Z:" + _project_sa(tag[5:], record) if tag.startswith("SA:Z:") else tag)
                fields[11:] = tags + ["zq:Z:" + query_id]
                output.write("\t".join(fields) + "\n")
            if seen != set(queries):
                raise ValueError("SAM is missing one or more prepared queries.")
        check_cancelled()
        if destination.exists():
            raise FileExistsError(f"Projected SAM already exists: {destination}")
        os.rename(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return counts
