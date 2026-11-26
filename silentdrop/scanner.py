"""Run bounded HTTPS HEAD probes against the reviewed dataset."""

import asyncio
import errno
import ssl
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import perf_counter
from types import SimpleNamespace

import aiohttp

from .classifier import Failure, classify
from .dataset import Domain
from .models import Outcome, ProbeResult, utc_timestamp

DEFAULT_CONCURRENCY = 8
MAX_CONCURRENCY = 32
DEFAULT_TIMEOUT = 8.0
MIN_TIMEOUT = 0.1
MAX_TIMEOUT = 120.0


@dataclass
class _Stages:
    dns: Outcome = Outcome.UNKNOWN
    connection: Outcome = Outcome.UNKNOWN
    tls: Outcome = Outcome.UNKNOWN


def _trace_config() -> aiohttp.TraceConfig:
    trace = aiohttp.TraceConfig()

    async def dns_resolved(
        session: aiohttp.ClientSession,
        context: SimpleNamespace,
        params: aiohttp.TraceDnsResolveHostEndParams,
    ) -> None:
        context.trace_request_ctx.dns = Outcome.OK

    async def connection_ready(
        session: aiohttp.ClientSession,
        context: SimpleNamespace,
        params: aiohttp.TraceConnectionCreateEndParams,
    ) -> None:
        stages = context.trace_request_ctx
        stages.connection = Outcome.OK
        # The connector only receives HTTPS URLs and verifies the certificate.
        stages.tls = Outcome.OK

    trace.on_dns_resolvehost_end.append(dns_resolved)
    trace.on_connection_create_end.append(connection_ready)
    return trace


def _observe_failure(exc: Exception, stages: _Stages) -> Failure:
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return Failure.TIMEOUT
    if isinstance(exc, aiohttp.ClientConnectorDNSError):
        stages.dns = Outcome.FAILED
        return Failure.DNS
    if isinstance(exc, aiohttp.ClientSSLError):
        stages.connection = Outcome.OK
        stages.tls = Outcome.FAILED
        return (
            Failure.CERTIFICATE
            if isinstance(exc, aiohttp.ClientConnectorCertificateError)
            else Failure.TLS
        )
    if isinstance(exc, aiohttp.ClientConnectorError) and stages.connection is Outcome.UNKNOWN:
        stages.connection = Outcome.FAILED
        error = exc.os_error
        if error.errno == errno.ECONNREFUSED or getattr(error, "winerror", None) == 10061:
            return Failure.REFUSED
    if isinstance(exc, (aiohttp.ClientConnectionError, OSError)):
        return Failure.CONNECTION
    return Failure.HTTP


def _probe_url(entry: Domain) -> str:
    return f"https://{entry.hostname}/"


async def _probe(session: aiohttp.ClientSession, entry: Domain) -> ProbeResult:
    started_at = utc_timestamp()
    started = perf_counter()
    stages = _Stages()
    status = None
    failure = None
    try:
        async with session.head(
            _probe_url(entry), allow_redirects=False, trace_request_ctx=stages
        ) as response:
            status = response.status
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
        failure = _observe_failure(exc, stages)

    classification, diagnostic = classify(status, failure=failure)
    return ProbeResult(
        domain=entry.hostname,
        category=entry.category,
        dns=stages.dns,
        connection=stages.connection,
        tls=stages.tls,
        http_status=status,
        latency_ms=round((perf_counter() - started) * 1000, 2),
        error=diagnostic,
        timestamp=started_at,
        classification=classification,
    )


async def scan(
    entries: Sequence[Domain],
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout: float = DEFAULT_TIMEOUT,
    on_result: Callable[[ProbeResult], None] | None = None,
) -> tuple[ProbeResult, ...]:
    """Test reviewed hosts and return observations in dataset order."""
    if not 1 <= concurrency <= MAX_CONCURRENCY:
        raise ValueError(f"concurrency must be between 1 and {MAX_CONCURRENCY}")
    if not MIN_TIMEOUT <= timeout <= MAX_TIMEOUT:
        raise ValueError(f"timeout must be between {MIN_TIMEOUT} and {MAX_TIMEOUT} seconds")
    work = iter(enumerate(entries))
    results: dict[int, ProbeResult] = {}
    resolver = aiohttp.ThreadedResolver()
    connector = aiohttp.TCPConnector(
        resolver=resolver,
        ssl=ssl.create_default_context(),
        force_close=True,
        limit=concurrency,
        limit_per_host=1,
        use_dns_cache=False,
    )
    async with aiohttp.ClientSession(
        connector=connector,
        timeout=aiohttp.ClientTimeout(total=timeout, ceil_threshold=float("inf")),
        trace_configs=[_trace_config()],
        cookie_jar=aiohttp.DummyCookieJar(),
        trust_env=False,
        auto_decompress=False,
    ) as session:

        async def worker() -> None:
            # Advancing the shared iterator is synchronous in the event loop.
            for index, entry in work:
                result = await _probe(session, entry)
                results[index] = result
                if on_result is not None:
                    on_result(result)

        workers = [asyncio.create_task(worker()) for _ in range(min(concurrency, len(entries)))]
        try:
            await asyncio.gather(*workers)
        finally:
            for task in workers:
                task.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

    return tuple(results[index] for index in range(len(entries)))
