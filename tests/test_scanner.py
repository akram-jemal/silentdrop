import asyncio
import socket
from dataclasses import replace

import aiohttp
import pytest
from aiohttp import web

from silentdrop import scanner
from silentdrop.dataset import Domain
from silentdrop.models import Classification, Outcome, ProbeResult

ENTRY = Domain("service.example", "gaming", "silentdrop")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "classification"),
    [
        (200, Classification.ACCESSIBLE),
        (302, Classification.ACCESSIBLE),
        (403, Classification.HTTP_RESTRICTED),
        (429, Classification.INCONCLUSIVE),
        (451, Classification.SUSPECTED_FILTERING),
        (503, Classification.INCONCLUSIVE),
    ],
)
async def test_https_uses_head_and_leaves_redirects_unfollowed(
    https_server, status, classification
):
    requests = []

    async def respond(request):
        requests.append((request.method, request.path))
        if request.path == "/redirected":
            return web.Response(status=200)
        return web.Response(status=status, headers={"Location": "/redirected"})

    await https_server(respond)
    (result,) = await scanner.scan((ENTRY,))
    assert requests == [("HEAD", "/")]
    assert result.domain == ENTRY.hostname
    assert result.classification is classification
    assert result.http_status == status
    assert (result.dns, result.connection, result.tls) == (Outcome.OK,) * 3
    assert result.latency_ms > 0
    assert result.timestamp.endswith("Z")


@pytest.mark.asyncio
async def test_times_out_waiting_for_http_headers(https_server):
    processing = asyncio.Event()
    release = asyncio.Event()

    async def wait_for_release(request):
        processing.set()
        await release.wait()
        return web.Response()

    await https_server(wait_for_release)
    try:
        (result,) = await scanner.scan((ENTRY,), timeout=0.6)
    finally:
        release.set()
    assert processing.is_set()
    assert result.classification is Classification.CONNECTION_TIMEOUT
    assert result.http_status is None
    assert (result.dns, result.connection, result.tls) == (Outcome.OK,) * 3


@pytest.mark.asyncio
async def test_rejects_an_untrusted_tls_certificate(https_server):
    async def unexpected_request(request):
        pytest.fail("a request reached an untrusted HTTPS endpoint")

    await https_server(unexpected_request, trust=False)
    (result,) = await scanner.scan((ENTRY,))
    assert result.classification is Classification.TLS_ERROR
    assert result.connection is Outcome.OK
    assert result.tls is Outcome.FAILED
    assert result.http_status is None
    assert "certificate" in result.error


@pytest.mark.asyncio
async def test_reports_dns_failure_without_leaking_the_resolver_message(monkeypatch):
    async def fail_resolution(*args, **kwargs):
        raise socket.gaierror(socket.EAI_NONAME, "private resolver diagnostic")

    monkeypatch.setattr(aiohttp.ThreadedResolver, "resolve", fail_resolution)
    (result,) = await scanner.scan((ENTRY,))
    assert result.classification is Classification.DNS_FAILURE
    assert result.dns is Outcome.FAILED
    assert result.connection is Outcome.UNKNOWN
    assert result.tls is Outcome.UNKNOWN
    assert "private resolver diagnostic" not in result.error


@pytest.mark.asyncio
async def test_reports_refused_connections(monkeypatch):
    with socket.socket() as bound_socket:
        # A bound, non-listening socket reserves the port without accepting connections.
        bound_socket.bind(("127.0.0.1", 0))
        port = bound_socket.getsockname()[1]
        monkeypatch.setattr(scanner, "_probe_url", lambda entry: f"https://127.0.0.1:{port}/")
        (result,) = await scanner.scan((ENTRY,))
    assert result.classification is Classification.CONNECTION_REFUSED
    assert result.connection is Outcome.FAILED
    assert result.tls is Outcome.UNKNOWN


@pytest.mark.asyncio
async def test_scan_bounds_concurrency_and_preserves_dataset_order(monkeypatch):
    active = peak = 0

    async def fake_probe(session, entry):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        if entry == ENTRY:
            await asyncio.sleep(0)
        active -= 1
        return ProbeResult(
            entry.hostname,
            entry.category,
            Outcome.OK,
            Outcome.OK,
            Outcome.OK,
            200,
            10.5,
            None,
            "2026-01-01T00:00:00Z",
            Classification.ACCESSIBLE,
        )

    monkeypatch.setattr(scanner, "_probe", fake_probe)
    entries = (ENTRY, *(replace(ENTRY, hostname=f"service-{i}.example") for i in range(6)))
    completed = []
    results = await scanner.scan(entries, concurrency=2, on_result=completed.append)
    assert peak == 2
    assert [result.domain for result in results] == [entry.hostname for entry in entries]
    assert completed[0].domain != ENTRY.hostname
    assert len(completed) == len(entries)


@pytest.mark.asyncio
async def test_cancellation_stops_active_workers(monkeypatch):
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def wait_for_cancel(session, entry):
        started.set()
        try:
            await asyncio.Future()
        finally:
            stopped.set()

    monkeypatch.setattr(scanner, "_probe", wait_for_cancel)
    task = asyncio.create_task(scanner.scan((ENTRY,)))
    await asyncio.wait_for(started.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stopped.is_set()
