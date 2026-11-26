"""Compare classifications from two locally stored scan reports."""

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from .dataset import normalize_domain
from .models import Classification
from .reporter import SCHEMA_VERSION, report_format

_DATASET_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}")


@dataclass(frozen=True)
class Snapshot:
    dataset_version: str
    results: dict[str, Classification]


@dataclass(frozen=True)
class Change:
    domain: str
    before: Classification | None
    after: Classification | None


@dataclass(frozen=True)
class Comparison:
    changes: tuple[Change, ...]
    unchanged: int


def _snapshot(dataset_version: object, rows: object) -> Snapshot:
    if not isinstance(dataset_version, str) or not _DATASET_ID.fullmatch(dataset_version):
        raise ValueError("missing or invalid dataset version")
    if not isinstance(rows, list) or not rows:
        raise ValueError("the report contains no results")

    results: dict[str, Classification] = {}
    for position, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"invalid result at position {position}")
        domain = row.get("domain")
        try:
            if not isinstance(domain, str) or normalize_domain(domain) != domain:
                raise ValueError("hostname must be normalized")
            classification = Classification(row.get("classification"))
        except ValueError as exc:
            raise ValueError(f"invalid hostname or classification at result {position}") from exc
        if domain in results:
            raise ValueError(f"duplicate hostname at result {position}")
        results[domain] = classification
    return Snapshot(dataset_version, results)


def _read_json(stream: TextIO) -> Snapshot:
    document = json.load(stream)
    if not isinstance(document, dict):
        raise ValueError("expected a JSON report object")
    schema = document.get("schema_version")
    if type(schema) is not int or schema != SCHEMA_VERSION:
        raise ValueError("unsupported or missing JSON report schema version")
    return _snapshot(document.get("dataset_version"), document.get("results"))


def _read_csv(stream: TextIO) -> Snapshot:
    reader = csv.DictReader(stream, strict=True)
    required = {"schema_version", "dataset_version", "domain", "classification"}
    columns = reader.fieldnames or []
    if not required.issubset(columns):
        raise ValueError("missing required report CSV columns")
    if len(columns) != len(set(columns)):
        raise ValueError("duplicate report CSV columns")
    rows = list(reader)
    if not rows:
        raise ValueError("the report contains no results")
    if any(None in row or row["schema_version"] != str(SCHEMA_VERSION) for row in rows):
        raise ValueError("invalid CSV row or unsupported report schema version")
    dataset_version = rows[0]["dataset_version"]
    if any(row["dataset_version"] != dataset_version for row in rows):
        raise ValueError("inconsistent dataset versions in CSV report")
    return _snapshot(dataset_version, rows)


def load_report(path: Path) -> Snapshot:
    """Read the dataset ID and domain classifications needed for comparison."""
    try:
        format_name = report_format(path)
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            if format_name == "json":
                return _read_json(stream)
            return _read_csv(stream)
    except (OSError, ValueError, csv.Error) as exc:
        raise ValueError(f"{path}: {exc}") from exc


def compare(before: Snapshot, after: Snapshot) -> Comparison:
    """Identify classification changes and domains present in only one report."""
    domains = before.results.keys() | after.results.keys()
    changes = tuple(
        Change(domain, before.results.get(domain), after.results.get(domain))
        for domain in sorted(domains)
        if before.results.get(domain) != after.results.get(domain)
    )
    return Comparison(changes=changes, unchanged=len(domains) - len(changes))
