"""Types shared by the scanner, classification and reporting."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class Outcome(str, Enum):
    OK = "ok"
    FAILED = "failed"
    UNKNOWN = "unknown"


class Classification(str, Enum):
    ACCESSIBLE = "ACCESSIBLE"
    DNS_FAILURE = "DNS_FAILURE"
    CONNECTION_TIMEOUT = "CONNECTION_TIMEOUT"
    CONNECTION_REFUSED = "CONNECTION_REFUSED"
    TLS_ERROR = "TLS_ERROR"
    HTTP_RESTRICTED = "HTTP_RESTRICTED"
    SUSPECTED_FILTERING = "SUSPECTED_FILTERING"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class ProbeResult:
    """Observed stages and classification for one HTTPS request."""

    domain: str
    category: str
    dns: Outcome
    connection: Outcome
    tls: Outcome
    http_status: int | None
    latency_ms: float
    error: str | None
    timestamp: str
    classification: Classification


def utc_timestamp() -> str:
    """Produce an ISO 8601 timestamp with an explicit UTC offset."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
