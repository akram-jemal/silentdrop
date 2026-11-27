"""Check the public HTTPS entry page of a reviewed service."""

from __future__ import annotations

import asyncio
import re
import ssl
from dataclasses import dataclass, field
from html.parser import HTMLParser
from time import perf_counter
from typing import TYPE_CHECKING

from yarl import URL

from .classifier import classify
from .results import Result, Verdict
from .scanner import DEFAULT_TIMEOUT, _observe_failure, _Stages, _trace_config

if TYPE_CHECKING:
    import aiohttp

    from .catalog import Service

_MAX_REDIRECTS = 3
_MAX_BYTES = 64 * 1024
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_HTML_TYPES = {"text/html", "application/xhtml+xml"}
_SIGN_IN = (
    "log in",
    "login",
    "sign in",
    "authenticate",
    "authentication required",
    "network authentication",
    "link a device",
)
_CHALLENGE = (
    "just a moment",
    "checking your browser",
    "verify you are human",
    "verify that you are human",
    "security check",
    "attention required",
    "access denied",
    "request blocked",
    "page not found",
    "service unavailable",
)
_GATEWAY_NAMES = (
    "fortiguard web filtering",
    "fortinet",
    "cisco umbrella",
    "palo alto networks",
    "zscaler",
    "sophos web filtering",
)
_BLOCK_HEADINGS = (
    "web page blocked",
    "website blocked",
    "site blocked",
    "web filter violation",
    "web page access denied",
    "access denied",
)
_POLICY_DENIAL = (
    "blocked by your organization",
    "blocked by your network administrator",
    "blocked by your administrator",
    "blocked by your network policy",
    "blocked by your company policy",
    "access to this web page is denied",
    "you are not permitted to access",
)


def _words(value: str) -> str:
    return " " + " ".join(re.findall(r"\w+\+?", value.casefold())) + " "


def _contains_any(value: str, phrases: tuple[str, ...]) -> bool:
    return any(_words(phrase) in value for phrase in phrases)


class _Page(HTMLParser):
    """Gather a small set of identity and gateway clues from the HTML sample."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.identity: list[str] = []
        self.visible: list[str] = []
        self.heading: list[str] = []
        self.heading_tag: str | None = None
        self.ignored_tag: str | None = None
        self.password_field = False
        self.refresh = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.ignored_tag:
            return
        if tag in {"script", "style", "template", "noscript"}:
            self.ignored_tag = tag
        if tag in {"title", "h1"}:
            self.heading_tag = tag
            self.heading = []
        fields = dict(attrs)
        if tag == "meta":
            key = (fields.get("property") or fields.get("name") or "").casefold()
            content = fields.get("content")
            if key in {"og:site_name", "og:title", "application-name"} and content:
                self.identity.append(content)
            if (fields.get("http-equiv") or "").strip().casefold() == "refresh":
                self.refresh = True
        if tag == "input" and (fields.get("type") or "").casefold() == "password":
            self.password_field = True

    def handle_endtag(self, tag: str) -> None:
        if self.ignored_tag:
            if tag == self.ignored_tag:
                self.ignored_tag = None
            return
        if tag == self.heading_tag:
            self.identity.append("".join(self.heading))
            self.heading_tag = None

    def handle_data(self, data: str) -> None:
        if not self.ignored_tag:
            self.visible.append(data)
            if self.heading_tag:
                self.heading.append(data)


@dataclass
class _Evidence:
    host: str
    stages: _Stages = field(default_factory=_Stages)
    status: int | None = None
    redirects: int = 0
    elapsed_ms: float = 0.0

    def details(self) -> tuple[str, ...]:
        return (
            f"HTTPS GET {self.host}",
            f"DNS {self.stages.dns.value} / TCP {self.stages.connection.value}"
            f" / TLS {self.stages.tls.value}",
            f"HTTP {self.status if self.status is not None else 'unavailable'}",
            f"Redirects followed: {self.redirects}",
            f"Elapsed {self.elapsed_ms:.0f} ms",
        )


def _checked_url(url: str, hosts: frozenset[str], *, base: URL | None = None) -> URL:
    if any(ord(char) < 32 or ord(char) == 127 for char in url):
        raise ValueError("invalid URL")
    candidate = URL(url)
    if base is not None:
        candidate = base.join(candidate)
    if (
        candidate.scheme != "https"
        or candidate.raw_host not in hosts
        or candidate.port != 443
        or candidate.raw_user is not None
        or candidate.raw_password is not None
    ):
        raise ValueError("URL is outside the reviewed service")
    return candidate.with_fragment(None)


async def _sample(response: aiohttp.ClientResponse) -> bytes:
    """Read at most the sample budget without decompressing the response."""
    data = bytearray()
    while len(data) < _MAX_BYTES:
        chunk = await response.content.read(min(4096, _MAX_BYTES - len(data)))
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


async def _interpret(
    service: Service, url: URL, response: aiohttp.ClientResponse
) -> tuple[Verdict, str]:
    squid_error = response.headers.get("X-Squid-Error", "").split(maxsplit=1)
    if squid_error and squid_error[0].upper() == "ERR_ACCESS_DENIED":
        return Verdict.BLOCK_PAGE, "The response carried a recognizable Squid access-denied signal."
    if response.headers.get("cf-mitigated", "").strip().casefold() == "challenge":
        return Verdict.UNVERIFIED, "The endpoint returned an automated browser challenge."
    encoding = response.headers.get("Content-Encoding", "identity").strip().casefold()
    page = _Page()
    if response.content_type in _HTML_TYPES and encoding in {"", "identity"}:
        charset = (response.charset or "utf-8").casefold()
        if charset not in {"utf-8", "iso-8859-1", "windows-1252", "us-ascii"}:
            charset = "utf-8"
        sample = (await _sample(response)).decode(charset, errors="replace")
        try:
            page.feed(sample)
            page.close()
        except (AssertionError, ValueError):
            return Verdict.UNVERIFIED, "The entry-page sample could not be parsed as HTML."

    identity = tuple(_words(text) for text in page.identity)
    visible = _words(" ".join(page.visible))
    block_heading = any(_contains_any(text, _BLOCK_HEADINGS) for text in identity)
    if block_heading and (
        _contains_any(visible, _POLICY_DENIAL)
        or (_contains_any(visible, _GATEWAY_NAMES) and _contains_any(visible, _BLOCK_HEADINGS))
    ):
        return Verdict.BLOCK_PAGE, "The response matched a recognizable web filtering block page."
    if not 200 <= response.status < 300:
        return Verdict.UNVERIFIED, f"The endpoint returned HTTP {response.status}."
    path = _words(url.path)
    if page.password_field or any(_contains_any(text, _SIGN_IN) for text in (*identity, path)):
        return Verdict.UNVERIFIED, "The endpoint led to a sign-in or authentication page."
    if page.refresh or response.headers.get("Refresh"):
        return Verdict.UNVERIFIED, "The response attempted a browser-driven redirect."
    if block_heading or any(_contains_any(text, _CHALLENGE) for text in identity):
        return Verdict.UNVERIFIED, "The response appeared to be a challenge or an error page."
    if any(_contains_any(text, service.markers) for text in identity):
        return Verdict.LOADED, "The HTTPS response contained the expected page branding."
    return Verdict.UNVERIFIED, "The response sample contained no recognizable entry-page branding."


async def _check(service: Service, url: URL, evidence: _Evidence) -> tuple[Verdict, str]:
    import aiohttp

    connector = aiohttp.TCPConnector(
        resolver=aiohttp.ThreadedResolver(),
        ssl=ssl.create_default_context(),
        force_close=True,
        limit=1,
        use_dns_cache=False,
    )
    visited = {url}
    async with aiohttp.ClientSession(
        connector=connector,
        cookie_jar=aiohttp.DummyCookieJar(),
        headers={"Accept": "text/html, application/xhtml+xml", "Accept-Encoding": "identity"},
        read_bufsize=4096,
        timeout=aiohttp.ClientTimeout(total=None),
        trace_configs=[_trace_config()],
        trust_env=False,
        auto_decompress=False,
    ) as session:
        while True:
            evidence.host = url.raw_host or evidence.host
            evidence.stages = _Stages()
            evidence.status = None
            async with session.get(
                url, allow_redirects=False, trace_request_ctx=evidence.stages
            ) as response:
                evidence.status = response.status
                if response.status not in _REDIRECT_STATUSES:
                    return await _interpret(service, url, response)
                location = response.headers.get("Location")
                if not location:
                    return Verdict.UNVERIFIED, "The response redirected without a destination."
                if evidence.redirects >= _MAX_REDIRECTS:
                    return Verdict.UNVERIFIED, "The redirect limit was reached."
                try:
                    next_url = _checked_url(location, service.hosts, base=url)
                except ValueError:
                    return Verdict.UNVERIFIED, "The redirect left the reviewed HTTPS entry points."
                if next_url in visited:
                    return Verdict.UNVERIFIED, "The service returned a redirect loop."
                visited.add(next_url)
                evidence.redirects += 1
                url = next_url


async def check_page(service: Service) -> Result:
    """Check one reviewed entry URL and return only bounded diagnostic evidence."""
    import aiohttp

    try:
        url = _checked_url(service.url, service.hosts)
    except (AssertionError, ValueError):
        return Result(service, Verdict.UNVERIFIED, "The catalog entry URL is invalid.", ())
    evidence = _Evidence(url.raw_host or "unavailable")
    started = perf_counter()
    try:
        verdict, summary = await asyncio.wait_for(_check(service, url, evidence), DEFAULT_TIMEOUT)
    except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as error:
        verdict = Verdict.UNVERIFIED
        if evidence.status is not None:
            summary = "The HTTP response arrived, but the entry-page sample could not be read."
        else:
            failure = _observe_failure(error, evidence.stages)
            _, diagnostic = classify(failure=failure)
            summary = diagnostic or "The HTTPS request did not complete."
    evidence.elapsed_ms = (perf_counter() - started) * 1000
    return Result(service, verdict, summary, evidence.details())
