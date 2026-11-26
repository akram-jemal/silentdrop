"""Interpret observed network and HTTP outcomes conservatively."""

from enum import Enum

from .models import Classification


class Failure(Enum):
    DNS = "dns"
    TIMEOUT = "timeout"
    REFUSED = "refused"
    CERTIFICATE = "certificate"
    TLS = "tls"
    CONNECTION = "connection"
    HTTP = "http"


FAILED_CLASSIFICATIONS = frozenset(
    {
        Classification.DNS_FAILURE,
        Classification.CONNECTION_TIMEOUT,
        Classification.CONNECTION_REFUSED,
        Classification.TLS_ERROR,
        Classification.HTTP_RESTRICTED,
    }
)

_NETWORK_FAILURES = {
    Failure.DNS: (
        Classification.DNS_FAILURE,
        "The system resolver could not resolve the hostname.",
    ),
    Failure.TIMEOUT: (
        Classification.CONNECTION_TIMEOUT,
        "The request timed out before receiving HTTP headers.",
    ),
    Failure.REFUSED: (Classification.CONNECTION_REFUSED, "The connection was refused."),
    Failure.CERTIFICATE: (Classification.TLS_ERROR, "TLS certificate verification failed."),
    Failure.TLS: (Classification.TLS_ERROR, "TLS negotiation failed."),
    Failure.CONNECTION: (
        Classification.INCONCLUSIVE,
        "A transport error prevented the request from completing.",
    ),
    Failure.HTTP: (Classification.INCONCLUSIVE, "The client could not parse an HTTP response."),
}
_RESTRICTIONS = {
    401: "The endpoint requires authentication (HTTP 401).",
    403: "The endpoint denied this HEAD request (HTTP 403).",
    407: "The response requires proxy authentication (HTTP 407).",
    511: "The response indicates that network authentication is required (HTTP 511).",
}


def classify(
    http_status: int | None = None, *, failure: Failure | None = None
) -> tuple[Classification, str | None]:
    """Return a result class and a diagnostic description from observed evidence."""
    if failure is not None:
        return _NETWORK_FAILURES[failure]
    if http_status is None:
        return Classification.INCONCLUSIVE, "No HTTP status was received."
    if 200 <= http_status < 400:
        return Classification.ACCESSIBLE, None
    if http_status in _RESTRICTIONS:
        return Classification.HTTP_RESTRICTED, _RESTRICTIONS[http_status]
    if http_status == 451:
        return (
            Classification.SUSPECTED_FILTERING,
            "HTTP 451 reports a legal restriction. Its source is unverified.",
        )
    if http_status == 429:
        return Classification.INCONCLUSIVE, "The endpoint reported rate limiting (HTTP 429)."
    if 500 <= http_status < 600:
        return (
            Classification.INCONCLUSIVE,
            f"The endpoint returned a server error (HTTP {http_status}).",
        )
    return Classification.INCONCLUSIVE, f"The endpoint returned HTTP {http_status} to HEAD."
