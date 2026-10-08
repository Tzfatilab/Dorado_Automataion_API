"""Versioned presentation models. No detection, calling or filtering belongs here."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any


class Availability(str, Enum):
    AVAILABLE = "available"
    NOT_REQUESTED = "not_requested"
    NOT_EXPORTED = "not_exported"
    MISSING = "missing"
    INVALID = "invalid"
    NOT_APPLICABLE = "not_applicable"


def safe_id(kind: str, *parts: str) -> str:
    """Hash a structured identity; delimiters and hostile names cannot alias paths."""
    if kind not in {"b", "r", "s", "run"}:
        raise ValueError("Unsupported ID kind")
    encoded = json.dumps(parts, ensure_ascii=True, separators=(",", ":")).encode()
    return kind + "-" + hashlib.sha256(encoded).hexdigest()


@dataclass
class Source:
    id: str
    path: str
    sha256: str
    format: str
    sheet: str | None = None


@dataclass
class Evidence:
    source_id: str
    row: int | None = None
    fields: list[str] = field(default_factory=list)


@dataclass
class Fact:
    status: Availability
    value: Any = None
    reason: str = ""
    unit: str | None = None
    population: str | None = None
    origin: str = "source_reported"
    evidence: list[Evidence] = field(default_factory=list)


def unavailable(reason: str, status=Availability.NOT_EXPORTED) -> Fact:
    return Fact(status, reason=reason)


@dataclass
class Read:
    id: str
    original_id: str
    barcode_id: str
    metrics: dict[str, Fact]
    calls: dict[str, dict[str, Fact]]
    filtering: Fact
    alignments: Fact
    tracks: dict[str, Fact]
    evidence: list[Evidence]
    warnings: list[str] = field(default_factory=list)


@dataclass
class Barcode:
    id: str
    label: str
    reads: list[Read] = field(default_factory=list)
    metrics: dict[str, Fact] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class Run:
    id: str
    label: str
    organism: Fact
    settings: Fact
    stages: dict[str, Fact]
    barcodes: list[Barcode]
    sources: list[Source]
    metrics: dict[str, Fact]
    warnings: list[str] = field(default_factory=list)
    schema_version: str = "1.0"

    def to_dict(self):
        validate(self)
        return asdict(self)


def validate(run: Run) -> None:
    """Reject malformed availability, unsafe IDs, broken joins and nonfinite JSON."""
    if run.schema_version != "1.0":
        raise ValueError("Unsupported schema version")
    source_ids = {s.id for s in run.sources}
    if len(source_ids) != len(run.sources):
        raise ValueError("Duplicate source IDs")
    for source in run.sources:
        if not re.fullmatch(r"[a-f0-9]{64}", source.sha256) or source.format not in {"csv", "xlsx", "json", "log"}:
            raise ValueError("Invalid source provenance")
    seen = set()
    for entity in [run, *run.sources, *run.barcodes, *(r for b in run.barcodes for r in b.reads)]:
        if not re.fullmatch(r"(?:run|s|b|r)-[a-f0-9]{64}", entity.id) or entity.id in seen:
            raise ValueError("Invalid or duplicate entity ID")
        prefix = {Run: "run-", Source: "s-", Barcode: "b-", Read: "r-"}[type(entity)]
        if not entity.id.startswith(prefix):
            raise ValueError("ID kind does not match entity")
        seen.add(entity.id)
    for barcode in run.barcodes:
        for read in barcode.reads:
            if read.barcode_id != barcode.id:
                raise ValueError("Read belongs to a different barcode")

    def walk(value):
        if isinstance(value, Fact):
            Availability(value.status)
            if value.status == Availability.AVAILABLE:
                if value.value is None:
                    raise ValueError("Available fact requires a value")
            elif value.value is not None or not value.reason:
                raise ValueError("Unavailable fact requires null value and reason")
            if value.origin not in {"source_reported", "presentation_aggregate"}:
                raise ValueError("Unknown metric origin")
            if value.status == Availability.AVAILABLE and not value.evidence:
                raise ValueError("Available fact requires provenance")
            if value.unit == "bp" and isinstance(value.value, dict):
                interval = value.value
                if (interval.get("convention") != "zero_based_half_open"
                        or type(interval.get("start")) is not int or type(interval.get("end")) is not int
                        or interval["start"] < 0 or interval["end"] <= interval["start"]
                        or interval.get("space") not in {"reference", "nanotel_analyzed_read"}):
                    raise ValueError("Invalid normalized interval")
        if isinstance(value, Evidence):
            if value.source_id not in source_ids or (value.row is not None and (type(value.row) is not int or value.row < 1)):
                raise ValueError("Invalid evidence reference")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Nonfinite value")
        if hasattr(value, "__dataclass_fields__"):
            for key in value.__dataclass_fields__:
                walk(getattr(value, key))
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, (tuple, list)):
            for item in value:
                walk(item)
    walk(run)
    json.dumps(asdict(run), allow_nan=False)
