import asyncio
import os
import socket
import ssl
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import trustme
from aiohttp import web

from silentdrop import cli, doctor
from silentdrop.dataset import load_dataset


def test_doctor_defaults_to_offline_and_hides_environment_values(monkeypatch, tmp_path, capsys):
    def unexpected_network(*args, **kwargs):
        pytest.fail("offline doctor attempted a network operation")

    monkeypatch.setattr(socket, "getaddrinfo", unexpected_network)
    monkeypatch.setattr(socket, "create_connection", unexpected_network)
    monkeypatch.chdir(tmp_path)
    ca_file = tmp_path / "local-ca-path-marker.pem"
    trustme.CA().cert_pem.write_to_path(ca_file)
    monkeypatch.setenv("SSL_CERT_FILE", str(ca_file))
    monkeypatch.setenv("SSLKEYLOGFILE", str(tmp_path / "sslkeylog.log"))
    monkeypatch.setenv("https_proxy", "http://user:proxy-password-marker@proxy.example:8080")
    monkeypatch.setenv("NO_PROXY", "private-host-marker.example")

    assert cli.main(["--no-color", "doctor"]) == 0

    output = capsys.readouterr().out
    assert "Python" in output
    assert "TLS" in output
    assert "HTTP proxy configuration detected" in output
    assert "local-ca-path-marker" not in output
    assert "proxy-password-marker" not in output
    assert "private-host-marker" not in output
    assert {path.name for path in tmp_path.iterdir()} == {ca_file.name}


def test_doctor_rejects_arbitrary_probe_target(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["doctor", "--probe", "other.example"])

    assert exc_info.value.code == 2
    assert "other.example" in capsys.readouterr().err


def test_offline_doctor_leaves_tls_key_log_untouched_on_startup(monkeypatch, tmp_path):
    ca_file = tmp_path / "ca.pem"
    trustme.CA().cert_pem.write_to_path(ca_file)
    key_log = tmp_path / "sslkeys.log"
    monkeypatch.setenv("SSL_CERT_FILE", str(ca_file))
    monkeypatch.setenv("SSLKEYLOGFILE", str(key_log))

    process = subprocess.run(
        [sys.executable, "-m", "silentdrop", "doctor"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    assert "SilentDrop doctor" in process.stdout
    assert not key_log.exists()


def test_doctor_stops_when_tls_context_initialization_fails(monkeypatch, capsys):
    def broken_context():
        raise ssl.SSLError("private-path-marker")

    async def unexpected_probe(*args, **kwargs):
        pytest.fail("doctor reached the probe without usable TLS configuration")

    monkeypatch.setattr(doctor, "_load_trust_context", broken_context)
    monkeypatch.setattr(doctor, "scan", unexpected_probe)

    assert cli.main(["doctor", "--probe"]) == 1

    output = capsys.readouterr().out
    assert "TLS" in output
    assert "private-path-marker" not in output


def test_probe_setup_failure_hides_paths(monkeypatch, capsys):
    async def broken_probe(*args, **kwargs):
        raise PermissionError("private-keylog-path-marker")

    monkeypatch.setattr(doctor, "scan", broken_probe)

    assert cli.main(["doctor", "--probe"]) == 1

    output = capsys.readouterr()
    assert "Could not initialize the HTTPS probe" in output.out
    assert "private-keylog-path-marker" not in output.out + output.err


@pytest.mark.parametrize("ca_directory_exists", [False, True])
def test_doctor_distinguishes_missing_trust_from_lazy_ca_directory(
    monkeypatch, tmp_path, capsys, ca_directory_exists
):
    ca_file = tmp_path / "missing-path-marker.pem"
    ca_directory = tmp_path / "ca-directory-marker"
    if ca_directory_exists:
        ca_directory.mkdir()
    empty_context = SimpleNamespace(cert_store_stats=lambda: {"x509_ca": 0})
    paths = ssl.get_default_verify_paths()._replace(cafile=None, capath=None)
    monkeypatch.setattr(doctor, "_load_trust_context", lambda: empty_context)
    monkeypatch.setattr(ssl, "get_default_verify_paths", lambda: paths)
    monkeypatch.setenv(paths.openssl_cafile_env, str(ca_file))
    monkeypatch.setenv(
        paths.openssl_capath_env, f"{tmp_path / 'missing'}{os.pathsep}{ca_directory}"
    )

    assert cli.main(["doctor"]) == (0 if ca_directory_exists else 1)

    output = capsys.readouterr().out
    expected = (
        "Certificates may load on demand"
        if ca_directory_exists
        else "No CA certificates loaded and no CA directory found"
    )
    assert expected in output
    assert "Python could not find a CA bundle" in output
    assert "missing-path-marker" not in output
    assert "ca-directory-marker" not in output


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [302, 403])
async def test_doctor_probe_reports_verified_http_response_without_following_redirects(
    https_server, monkeypatch, tmp_path, capsys, status
):
    async def reply(request):
        requests.append((request.method, request.path))
        return web.Response(status=status, headers={"Location": "/another-page"})

    monkeypatch.chdir(tmp_path)
    requests = []
    await https_server(reply)

    assert doctor.PROBE_HOST in {entry.hostname for entry in load_dataset()}
    assert await asyncio.to_thread(cli.main, ["doctor", "--probe"]) == 0

    output = capsys.readouterr().out
    assert doctor.PROBE_HOST in output
    assert f"HTTP {status} over verified TLS" in output
    assert requests == [("HEAD", "/")]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_doctor_probe_rejects_untrusted_server_certificate(https_server, monkeypatch, capsys):
    async def unexpected_request(request):
        pytest.fail("doctor sent HTTP headers to a server with an untrusted certificate")

    await https_server(unexpected_request, trust=False)
    # Use a separate, populated trust store that cannot contain the server's CA.
    cert_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    trustme.CA().configure_trust(cert_context)
    monkeypatch.setattr(ssl, "create_default_context", lambda: cert_context)

    assert await asyncio.to_thread(cli.main, ["doctor", "--probe"]) == 1

    output = capsys.readouterr().out.lower()
    assert "tls certificate verification failed" in output
