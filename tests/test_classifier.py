import pytest

from silentdrop.classifier import FAILED_CLASSIFICATIONS, Failure, classify
from silentdrop.models import Classification


@pytest.mark.parametrize(
    ("status", "classification"),
    [
        (200, Classification.ACCESSIBLE),
        (301, Classification.ACCESSIBLE),
        (401, Classification.HTTP_RESTRICTED),
        (403, Classification.HTTP_RESTRICTED),
        (404, Classification.INCONCLUSIVE),
        (405, Classification.INCONCLUSIVE),
        (407, Classification.HTTP_RESTRICTED),
        (429, Classification.INCONCLUSIVE),
        (451, Classification.SUSPECTED_FILTERING),
        (500, Classification.INCONCLUSIVE),
        (503, Classification.INCONCLUSIVE),
        (511, Classification.HTTP_RESTRICTED),
        (None, Classification.INCONCLUSIVE),
    ],
)
def test_classifies_http_evidence_without_inferring_firewall_rules(status, classification):
    actual, diagnostic = classify(status)
    assert actual is classification
    assert (diagnostic is None) == (classification is Classification.ACCESSIBLE)


@pytest.mark.parametrize(
    ("failure", "classification"),
    [
        (Failure.DNS, Classification.DNS_FAILURE),
        (Failure.TIMEOUT, Classification.CONNECTION_TIMEOUT),
        (Failure.REFUSED, Classification.CONNECTION_REFUSED),
        (Failure.CERTIFICATE, Classification.TLS_ERROR),
        (Failure.TLS, Classification.TLS_ERROR),
        (Failure.CONNECTION, Classification.INCONCLUSIVE),
        (Failure.HTTP, Classification.INCONCLUSIVE),
    ],
)
def test_classifies_network_failures(failure, classification):
    actual, diagnostic = classify(failure=failure)
    assert actual is classification
    assert diagnostic
    assert (actual in FAILED_CLASSIFICATIONS) == (actual is not Classification.INCONCLUSIVE)
