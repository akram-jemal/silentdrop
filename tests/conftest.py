import ssl

import pytest_asyncio
import trustme
from aiohttp import web

from silentdrop import scanner


@pytest_asyncio.fixture
async def https_server(monkeypatch):
    """Expose a loopback HTTPS endpoint and a temporary CA for the test client."""
    ca = trustme.CA()
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ca.issue_cert("localhost").configure_cert(server_context)
    runners = []

    async def start(handler, *, trust=True):
        app = web.Application()
        app.router.add_route("*", "/{path:.*}", handler)
        runner = web.AppRunner(app, shutdown_timeout=0.2)
        await runner.setup()
        runners.append(runner)
        await web.TCPSite(runner, "127.0.0.1", 0, ssl_context=server_context).start()
        port = runner.addresses[0][1]
        monkeypatch.setattr(scanner, "_probe_url", lambda entry: f"https://localhost:{port}/")
        if trust:
            client_context = ssl.create_default_context()
            ca.configure_trust(client_context)
            monkeypatch.setattr(scanner.ssl, "create_default_context", lambda: client_context)

    yield start
    for runner in runners:
        await runner.cleanup()
