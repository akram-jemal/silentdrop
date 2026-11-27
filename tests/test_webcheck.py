import asyncio
import socket
import ssl

import aiohttp
import pytest
import pytest_asyncio
import trustme
from aiohttp import web

from silentdrop import webcheck
from silentdrop.catalog import Service
from silentdrop.results import Verdict

_SERVICE = Service(
    "testchat", "TestChat", "Chat", "https://entry.example/", ("TestChat",), ("edge.example",)
)


@pytest_asyncio.fixture
async def entry_server(monkeypatch):
    """Keep approved test names and port checks intact while routing to loopback."""
    ca = trustme.CA()
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ca.issue_cert(*_SERVICE.hosts).configure_cert(server_context)
    runners = []

    async def start(handler, *, trust=True):
        app = web.Application()
        app.router.add_route("*", "/{path:.*}", handler)
        runner = web.AppRunner(app, shutdown_timeout=0.2)
        await runner.setup()
        runners.append(runner)
        await web.TCPSite(runner, "127.0.0.1", 0, ssl_context=server_context).start()
        port = runner.addresses[0][1]

        async def resolve(self, host, port_requested, family):
            assert host in _SERVICE.hosts
            assert port_requested == 443
            return [
                {
                    "hostname": host,
                    "host": "127.0.0.1",
                    "port": port,
                    "family": socket.AF_INET,
                    "proto": socket.IPPROTO_TCP,
                    "flags": socket.AI_NUMERICHOST,
                }
            ]

        monkeypatch.setattr(aiohttp.ThreadedResolver, "resolve", resolve)
        if trust:
            client_context = ssl.create_default_context()
            ca.configure_trust(client_context)
            monkeypatch.setattr(ssl, "create_default_context", lambda: client_context)

    yield start
    for runner in runners:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_page_get_follows_reviewed_redirects_without_cookies(entry_server):
    requests = []

    async def handler(request):
        assert request.headers["Accept-Encoding"] == "identity"
        assert "Cookie" not in request.headers
        assert "Authorization" not in request.headers
        requests.append((request.method, request.host, request.path))
        if request.path == "/":
            return web.Response(
                status=302,
                headers={
                    "Location": "/next",
                    "Set-Cookie": "private-session=is-never-resent; Path=/",
                },
            )
        if request.path == "/next":
            return web.Response(
                status=302,
                headers={
                    "Location": "https://edge.example/path-marker?query-marker=opaque#fragment-marker"
                },
            )
        return web.Response(text="<title>TestChat</title>", content_type="text/html")

    await entry_server(handler)
    result = await webcheck.check_page(_SERVICE)
    assert result.verdict is Verdict.LOADED
    assert requests == [
        ("GET", "entry.example", "/"),
        ("GET", "entry.example", "/next"),
        ("GET", "edge.example", "/path-marker"),
    ]
    assert result.details[:-1] == (
        "HTTPS GET edge.example",
        "DNS ok / TCP ok / TLS ok",
        "HTTP 200",
        "Redirects followed: 2",
    )
    assert result.details[-1].startswith("Elapsed ")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "location",
    [
        "https://outside.example/secret-marker",
        "//outside.example/secret-marker",
        "http://entry.example/secret-marker",
        "https://entry.example:8443/secret-marker",
        "https://user:secret-marker@entry.example/",
    ],
)
async def test_page_leaves_unapproved_redirect_destinations_unrequested(entry_server, location):
    requests = []

    async def handler(request):
        requests.append(request.host)
        return web.Response(status=302, headers={"Location": location})

    await entry_server(handler)
    result = await webcheck.check_page(_SERVICE)
    assert result.verdict is Verdict.UNVERIFIED
    assert requests == ["entry.example"]
    assert "reviewed HTTPS entry points" in result.summary
    assert "secret-marker" not in repr(result)


@pytest.mark.asyncio
async def test_page_bounds_total_redirect_hops(entry_server):
    requests = []

    async def handler(request):
        requests.append(request.path)
        return web.Response(status=307, headers={"Location": f"/next/{len(requests)}"})

    await entry_server(handler)
    result = await webcheck.check_page(_SERVICE)
    assert result.verdict is Verdict.UNVERIFIED
    assert "limit" in result.summary
    assert len(requests) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "body", "headers", "expected"),
    [
        (200, '<meta property="og:site_name" content="TestChat">', {}, Verdict.LOADED),
        (200, "<title>TestChat</title>", {}, Verdict.LOADED),
        (200, "<title>UnofficialTestChat</title>", {}, Verdict.UNVERIFIED),
        (200, "<script>let title = '<title>TestChat</title>';</script>", {}, Verdict.UNVERIFIED),
        (200, "<title>Log in to TestChat</title>", {}, Verdict.UNVERIFIED),
        (200, "<title>TestChat</title><input type='password'>", {}, Verdict.UNVERIFIED),
        (
            200,
            "<title>TestChat</title><meta http-equiv='refresh' content='0; url=/login'>",
            {},
            Verdict.UNVERIFIED,
        ),
        (200, "<title>TestChat</title>", {"cf-mitigated": "challenge"}, Verdict.UNVERIFIED),
        (403, "<title>TestChat Access Denied</title>", {}, Verdict.UNVERIFIED),
        (451, "<title>Unavailable for Legal Reasons</title>", {}, Verdict.UNVERIFIED),
        (
            403,
            "<p>Policy details.</p>",
            {"X-Squid-Error": "ERR_ACCESS_DENIED 0"},
            Verdict.BLOCK_PAGE,
        ),
        (
            200,
            "<title>FortiGuard Web Filtering</title><h1>Web page blocked</h1>"
            "<p>You are not permitted to access this site.</p>",
            {},
            Verdict.BLOCK_PAGE,
        ),
        (
            200,
            "<title>TestChat</title><script>let block = 'Fortinet web page blocked';</script>",
            {},
            Verdict.LOADED,
        ),
        (200, "<title>TestChat</title>", {"Content-Encoding": "gzip"}, Verdict.UNVERIFIED),
        (200, "<title>TestChat</title><h1>Site Blocked</h1>", {}, Verdict.UNVERIFIED),
    ],
)
async def test_page_classification_uses_strong_clues(entry_server, status, body, headers, expected):
    async def handler(request):
        return web.Response(status=status, text=body, content_type="text/html", headers=headers)

    await entry_server(handler)
    result = await webcheck.check_page(_SERVICE)
    assert result.verdict is expected
    assert result.details[2] == f"HTTP {status}"


@pytest.mark.asyncio
async def test_page_ignores_markers_beyond_sample_budget(entry_server):
    async def handler(request):
        body = b"x" * (64 * 1024) + b"<title>TestChat</title>"
        return web.Response(body=body, content_type="text/html")

    await entry_server(handler)
    result = await webcheck.check_page(_SERVICE)
    assert result.verdict is Verdict.UNVERIFIED
    assert "no recognizable" in result.summary


@pytest.mark.asyncio
async def test_page_timeout_after_headers_preserves_http_status(monkeypatch, entry_server):
    async def handler(request):
        response = web.StreamResponse(headers={"Content-Type": "text/html"})
        await response.prepare(request)
        await asyncio.Event().wait()
        return response

    await entry_server(handler)
    monkeypatch.setattr(webcheck, "DEFAULT_TIMEOUT", 0.5)
    result = await webcheck.check_page(_SERVICE)
    assert result.verdict is Verdict.UNVERIFIED
    assert "entry-page sample could not be read" in result.summary
    assert "HTTP 200" in result.details


@pytest.mark.asyncio
async def test_page_never_accepts_an_untrusted_tls_certificate(entry_server):
    async def handler(request):
        pytest.fail("untrusted server must receive no HTTP request")

    await entry_server(handler, trust=False)
    result = await webcheck.check_page(_SERVICE)
    assert result.verdict is Verdict.UNVERIFIED
    assert "certificate verification failed" in result.summary
    assert "DNS ok / TCP ok / TLS failed" in result.details
