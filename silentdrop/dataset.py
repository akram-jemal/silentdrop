"""Load the curated dataset from the installed package."""

import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass
from importlib.resources import files
from urllib.parse import urlsplit

DATASET_VERSION = "2026-11-26.1"
DATASET_LICENSE = "CC BY-NC-SA 4.0"
CATEGORIES = {
    "social": "Social media",
    "messaging": "Messaging",
    "gaming": "Gaming",
    "streaming": "Streaming",
    "entertainment": "Entertainment",
    "education": "Education",
    "developer": "Developer tools",
    "ai": "AI tools",
    "productivity": "Productivity",
    "general": "General services",
}
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
_COLUMNS = ["domain", "category", "source", "upstream_category"]


@dataclass(frozen=True)
class Domain:
    """One reviewed HTTPS hostname and its dataset provenance."""

    hostname: str
    category: str
    source: str
    upstream_category: str = ""


def normalize_domain(value: str) -> str:
    """Return the lowercase ASCII hostname of an HTTP(S) URL or bare domain."""
    value = value.strip()
    if not value or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("expected a hostname or HTTP(S) URL")
    if value.startswith("//"):
        value = f"https:{value}"
    elif "://" not in value:
        value = f"https://{value}"

    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise ValueError("expected a hostname or HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("credentials are not allowed in dataset URLs")
    default_port = 443 if parsed.scheme == "https" else 80
    if parsed.port not in {None, default_port}:
        raise ValueError("only default HTTP(S) ports are supported")

    domain = parsed.hostname.encode("idna").decode("ascii").lower().removesuffix(".")
    labels = domain.split(".")
    if (
        len(domain) > 253
        or len(labels) < 2
        or not all(_LABEL.fullmatch(label) for label in labels)
        or not labels[-1][0].isalpha()
    ):
        raise ValueError("expected a DNS hostname with at least two labels")
    return domain


def read_dataset(lines: Iterable[str]) -> tuple[Domain, ...]:
    """Parse reviewed CSV entries and keep the first row for each hostname."""
    rows = csv.DictReader(lines, strict=True)
    if rows.fieldnames != _COLUMNS:
        raise ValueError("unexpected dataset CSV columns")

    entries: dict[str, Domain] = {}
    for line_number, row in enumerate(rows, start=2):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"incomplete dataset row {line_number}")
        try:
            hostname = normalize_domain(row["domain"])
        except ValueError as exc:
            raise ValueError(f"invalid domain on dataset row {line_number}: {exc}") from exc
        category = row["category"].strip()
        source = row["source"].strip()
        if category not in CATEGORIES or not source:
            raise ValueError(f"invalid category or source on dataset row {line_number}")
        entries.setdefault(
            hostname, Domain(hostname, category, source, row["upstream_category"].strip())
        )

    if not entries:
        raise ValueError("the dataset contains no domains")
    return tuple(entries.values())


def load_dataset() -> tuple[Domain, ...]:
    """Read the packaged data with no network calls or checkout dependencies."""
    resource = files("silentdrop").joinpath("data").joinpath("domains.csv")
    with resource.open("r", encoding="utf-8", newline="") as stream:
        return read_dataset(stream)


def filter_category(entries: tuple[Domain, ...], category: str | None) -> tuple[Domain, ...]:
    """Select a known category or return the full dataset."""
    if category is None:
        return entries
    if category not in CATEGORIES:
        raise ValueError(f"unknown category {category!r}")
    return tuple(entry for entry in entries if entry.category == category)
