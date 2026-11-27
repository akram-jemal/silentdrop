"""Summarize scan results and write reports to local files."""

import csv
import json
from collections import Counter, defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TextIO

from . import __version__
from .classifier import summary_group
from .models import ProbeResult

SCHEMA_VERSION = 1
REPORT_FORMATS = ("json", "csv")
LIMITATIONS = (
    "Each result describes an HTTPS HEAD request to a website at the time of the scan.",
    "The scan cannot establish firewall rules or mobile app accessibility.",
    "Redirect destinations and page content are outside the scope of the check.",
)


@dataclass(frozen=True)
class Summary:
    total: int
    accessible: int
    failed: int
    inconclusive: int


def summarize(results: list[ProbeResult] | tuple[ProbeResult, ...]) -> Summary:
    """Count the three summary groups."""
    counts = Counter(summary_group(result.classification) for result in results)
    return Summary(len(results), counts["accessible"], counts["failed"], counts["inconclusive"])


@dataclass(frozen=True)
class ScanReport:
    dataset_version: str
    scan_timestamp: str
    results: tuple[ProbeResult, ...]

    @property
    def summary(self) -> Summary:
        return summarize(self.results)

    @property
    def categories(self) -> dict[str, Summary]:
        groups: dict[str, list[ProbeResult]] = defaultdict(list)
        for result in self.results:
            groups[result.category].append(result)
        return {category: summarize(results) for category, results in sorted(groups.items())}


def report_format(path: Path) -> str:
    """Infer the report format from a supported file extension."""
    extension = path.suffix.lower().removeprefix(".")
    if extension not in REPORT_FORMATS:
        raise ValueError("use a .json or .csv report filename")
    return extension


def _metadata(report: ScanReport) -> dict[str, int | str]:
    return {
        "schema_version": SCHEMA_VERSION,
        "application_version": __version__,
        "dataset_version": report.dataset_version,
        "scan_timestamp": report.scan_timestamp,
    }


def _write_json(report: ScanReport, stream: TextIO) -> None:
    document = {
        **_metadata(report),
        "summary": asdict(report.summary),
        "categories": {
            category: asdict(summary) for category, summary in report.categories.items()
        },
        "limitations": LIMITATIONS,
        "results": [asdict(result) for result in report.results],
    }
    json.dump(document, stream, indent=2, allow_nan=False)
    stream.write("\n")


def _write_csv(report: ScanReport, stream: TextIO) -> None:
    common = {**_metadata(report), **asdict(report.summary), "limitations": " ".join(LIMITATIONS)}
    category_totals = {
        category: {f"category_{key}": count for key, count in asdict(summary).items()}
        for category, summary in report.categories.items()
    }
    writer = csv.DictWriter(
        stream,
        fieldnames=[
            *common,
            *(f"category_{field.name}" for field in fields(Summary)),
            *(field.name for field in fields(ProbeResult)),
        ],
    )
    writer.writeheader()
    for result in report.results:
        row = asdict(result)
        row.update(
            dns=result.dns.value,
            connection=result.connection.value,
            tls=result.tls.value,
            classification=result.classification.value,
        )
        writer.writerow({**common, **category_totals[result.category], **row})


def save_report(report: ScanReport, path: Path) -> None:
    """Write a report atomically in the destination directory."""
    format_name = report_format(path)
    with atomic_report(path) as stream:
        if format_name == "json":
            _write_json(report, stream)
        else:
            _write_csv(report, stream)


@contextmanager
def atomic_report(path: Path) -> Iterator[TextIO]:
    """Write to a temporary file and replace the destination on success."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=".silentdrop-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            yield stream
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
