"""Inspect local HTTPS configuration and optionally check a reviewed host."""

import asyncio
import os
import platform
import ssl
import sys
from urllib.request import getproxies

from rich.console import Console

from .classifier import CERTIFICATE_ERROR
from .models import Domain, Outcome
from .scanner import scan

PROBE_HOST = "www.iana.org"
_PROBE = Domain(PROBE_HOST, "general")


def _load_trust_context() -> ssl.SSLContext:
    # Inspect the same trust sources as the scanner without initializing TLS key logging.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_default_certs()
    return context


def _print_trust(console: Console, context: ssl.SSLContext) -> bool:
    paths = ssl.get_default_verify_paths()
    file_override = paths.openssl_cafile_env
    directory_override = paths.openssl_capath_env
    # OpenSSL accepts a path list for CA directories. Python's path metadata
    # checks the full string as a single directory.
    directory_setting = os.environ.get(directory_override, paths.openssl_capath or "")
    ca_directory = paths.capath is not None or any(
        path and os.path.isdir(path) for path in directory_setting.split(os.pathsep)
    )
    ca_count = context.cert_store_stats()["x509_ca"]
    if ca_count:
        console.print(f"Trust  Loaded CA certificates: {ca_count}.")
    elif ca_directory:
        console.print("Trust  CA directory found. Certificates may load on demand.")
    else:
        console.print("Trust  No CA certificates loaded and no CA directory found.", style="yellow")

    if file_override in os.environ:
        console.print(f"Trust override  {file_override} is set.", markup=False)
        if paths.cafile is None:
            console.print("Python could not find a CA bundle at that setting.", style="yellow")
    if directory_override in os.environ:
        console.print(f"Trust override  {directory_override} is set.", markup=False)
        if not ca_directory:
            console.print("Python could not find a CA directory at that setting.", style="yellow")
    return ca_count > 0 or ca_directory


def _print_proxy(console: Console) -> None:
    try:
        proxy_types = getproxies().keys()
    except OSError:
        console.print("Proxy  Local proxy settings unavailable.", style="yellow")
        return
    if {"http", "https", "all"}.intersection(proxy_types):
        console.print("Proxy  HTTP proxy configuration detected. SilentDrop uses direct HTTPS.")
    else:
        console.print("Proxy  Python detected no HTTP proxy configuration.")


def _print_trust_help(console: Console) -> None:
    if sys.platform == "darwin":
        console.print(
            "For python.org builds on macOS, run Install Certificates.command "
            "from the corresponding Python folder in Applications."
        )
    console.print("On a managed network, ask IT which CA this Python installation should trust.")


def _run_probe(console: Console) -> int:
    console.print(f"HTTPS probe  {PROBE_HOST}")
    try:
        results = asyncio.run(scan((_PROBE,), concurrency=1))
    except (OSError, ValueError):
        console.print(
            "Could not initialize the HTTPS probe. Check Python's TLS configuration.",
            style="yellow",
        )
        return 1
    (result,) = results
    console.print(
        f"DNS {result.dns.value} / Connection {result.connection.value} / TLS {result.tls.value}"
    )
    if result.http_status is not None and result.tls is Outcome.OK:
        console.print(f"HTTP {result.http_status} over verified TLS.", style="green")
        return 0
    console.print(result.error or "No HTTP response over verified TLS.", style="yellow")
    if result.error == CERTIFICATE_ERROR:
        _print_trust_help(console)
    return 1


def run_doctor(console: Console, *, probe: bool = False) -> int:
    """Check Python and TLS configuration, with no network request by default."""
    console.print("SilentDrop doctor", style="bold")
    runtime = f"{platform.python_implementation()} {platform.python_version()}"
    environment = "virtual environment" if sys.prefix != sys.base_prefix else "base environment"
    console.print(f"Python  {runtime} ({environment})", markup=False)
    console.print(f"TLS  {ssl.OPENSSL_VERSION}", markup=False)
    _print_proxy(console)
    try:
        context = _load_trust_context()
    except (OSError, ValueError):
        console.print("Trust  Python could not initialize its TLS trust store.", style="yellow")
        _print_trust_help(console)
        return 1

    trust_available = _print_trust(console, context)
    if probe:
        return _run_probe(console)
    if not trust_available:
        _print_trust_help(console)
    console.print(f"HTTPS probe  Run silentdrop doctor --probe to check {PROBE_HOST}.")
    return 0 if trust_available else 1
