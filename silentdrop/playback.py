"""Check public video playback in an isolated, optional Chromium session."""

from __future__ import annotations

import asyncio
import math
import re
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

from .results import Result, Verdict

if TYPE_CHECKING:
    from .catalog import Service


_TIMEOUT = 22
_SETUP = 'Install the playback extra with pip install ".[playback]".'
_BROWSER_SETUP = "Install Chromium with python -m playwright install chromium."
_PLAYER_SELECTORS = {
    "youtube": "#movie_player video.html5-main-video",
    "tiktok": "video",
}
_AD_SELECTORS = {
    "youtube": "#movie_player.ad-showing, #movie_player.ad-interrupting",
    "tiktok": '[data-e2e="video-ad-label"], [data-e2e="ad-label"]',
}
_GATE_SELECTOR = (
    '[role="dialog"], dialog[open], #captcha-verify-container, iframe[src*="captcha"], '
    'yt-consent-bump-v2-lightbox, ytd-enforcement-message-view-model, [data-e2e="login-modal"]'
)
_OBSERVATION_NOTES = {
    "identity": "The browser did not show the expected public video.",
    "gate": "The player displayed a sign-in, consent or verification prompt.",
    "ad": "The player showed an advertisement. The selected video remains unverified.",
    "missing": "The browser did not expose one visible player for the selected video.",
    "stalled": "The selected video did not advance consistently during the observation.",
}

# A native media element must show three consecutive samples with two positive
# advances. Track the same element and source across the samples to reject
# source swaps. Compare video time with elapsed wall time to reject seeks.
_OBSERVE_PLAYBACK = r"""
async ({ expected, hosts, slug, selector, gates, ads, videoId }) => {
    const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
    const target = new URL(expected);
    const visible = element => {
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return rect.width > 1 && rect.height > 1 && rect.right > 0 && rect.bottom > 0 &&
            rect.left < innerWidth && rect.top < innerHeight &&
            style.visibility === 'visible' && style.display !== 'none' && style.opacity !== '0';
    };
    const matchingUrl = value => {
        if (!value) return false;
        const url = new URL(value, location.href);
        if (url.protocol !== 'https:' || url.username || url.password ||
            (url.port && url.port !== '443') || !hosts.includes(url.hostname)) return false;
        if (slug === 'youtube') {
            const ids = url.searchParams.getAll('v');
            return url.pathname === target.pathname && ids.length === 1 && ids[0] === videoId;
        }
        return url.pathname.replace(/\/$/, '') === target.pathname.replace(/\/$/, '');
    };
    const visibleMatch = selector => [...document.querySelectorAll(selector)].some(visible);
    const gate = () => {
        if (visibleMatch(gates)) return 'gate';
        if (!matchingUrl(location.href)) return 'identity';
        if (visibleMatch(ads)) return 'ad';
        return null;
    };
    const visibleVideos = () => [...document.querySelectorAll(selector)].filter(visible);
    const expectedVideo = () => {
        if (!matchingUrl(document.querySelector('link[rel="canonical"]')?.href)) return false;
        if (slug !== 'youtube') return true;
        const data = document.querySelector('#movie_player')?.getVideoData?.();
        return data?.video_id === videoId;
    };
    let video;
    for (let i = 0; i < 20; i++) {
        const reason = gate();
        if (reason) return { reason };
        const candidates = visibleVideos();
        if (expectedVideo() && candidates.length === 1) {
            video = candidates[0];
            break;
        }
        await sleep(250);
    }
    if (!video) return { reason: 'missing' };

    if (video.paused) {
        video.muted = true;
        video.play().catch(() => {});
    }
    const sample = () => {
        if (video.paused || video.seeking || video.ended || video.error ||
            video.readyState < 2 || !video.videoWidth || !video.videoHeight ||
            !Number.isFinite(video.duration) || !Number.isFinite(video.currentTime) ||
            !video.currentSrc || video.playbackRate < 0.75 || video.playbackRate > 1.25) return null;
        return { time: video.currentTime, source: video.currentSrc, wall: performance.now() };
    };
    let previous = sample(), advances = 0, total = 0;
    for (let i = 0; i < 12; i++) {
        await sleep(500);
        const reason = gate();
        if (reason) return { reason };
        const candidates = visibleVideos();
        if (candidates.length !== 1 || candidates[0] !== video || !expectedVideo()) {
            return { reason: 'identity' };
        }
        const next = sample();
        const delta = next && previous && next.time - previous.time;
        if (delta > 0.12 && next.source === previous.source &&
            delta <= ((next.wall - previous.wall) / 1000) * 1.25 + 0.15) {
            advances++;
            total += delta;
            if (advances >= 2) return { reason: 'played', seconds: total };
        } else {
            advances = 0;
            total = 0;
        }
        previous = next;
    }
    return { reason: 'stalled' };
}
"""


def _allowed(url: str, hosts: frozenset[str]) -> bool:
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname in hosts
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
        )
    except ValueError:
        return False


def _video_id(service: Service) -> str | None:
    url = service.video_url
    if url is None or not _allowed(url, service.hosts):
        return None
    parsed = urlsplit(url)
    if service.slug == "youtube" and parsed.path == "/watch":
        ids = parse_qs(parsed.query, keep_blank_values=True).get("v", [])
        if len(ids) == 1 and re.fullmatch(r"[A-Za-z0-9_-]{11}", ids[0]):
            return ids[0]
    if service.slug == "tiktok":
        match = re.fullmatch(r"/@[A-Za-z0-9._]+/video/([0-9]{16,22})/?", parsed.path)
        if match:
            return match.group(1)
    return None


def _unverified(service: Service, *details: str) -> Result:
    return Result(service, Verdict.UNVERIFIED, "Could not verify public video playback", details)


async def check_playback(service: Service) -> Result:
    """Verify advancing media only at the catalog's vetted video URL."""
    video_url = service.video_url
    video_id = _video_id(service)
    if video_url is None or video_id is None:
        return _unverified(service, "This service has no supported public test video.")
    try:
        from playwright.async_api import Error, async_playwright
    except ImportError:
        return _unverified(
            service, "Browser playback support is unavailable.", _SETUP, _BROWSER_SETUP
        )

    async def observe() -> Result:
        async with async_playwright() as playwright:
            try:
                browser = await playwright.chromium.launch(
                    headless=True, chromium_sandbox=True, timeout=8_000
                )
            except (Error, OSError):
                return _unverified(service, "Chromium could not start.", _BROWSER_SETUP)
            try:
                context = await browser.new_context(service_workers="block")
                page = await context.new_page()

                async def restrict_navigation(route):
                    request = route.request
                    if request.is_navigation_request():
                        try:
                            top_level = request.frame.parent_frame is None
                        except Error:
                            top_level = True
                        if top_level:
                            if request.method != "GET" or not _allowed(request.url, service.hosts):
                                await route.abort()
                                return
                            try:
                                response = await route.fetch(max_redirects=0, timeout=7_000)
                            except Error:
                                await route.abort()
                                return
                            if 300 <= response.status < 400:
                                await route.abort()
                                return
                            await route.fulfill(response=response)
                            return
                    await route.continue_()

                await context.route("**/*", restrict_navigation)
                response = await page.goto(video_url, wait_until="domcontentloaded", timeout=8_000)
                if response is None or not response.ok or not _allowed(page.url, service.hosts):
                    return _unverified(service, "The browser could not open the public video page.")
                observation = await page.evaluate(
                    _OBSERVE_PLAYBACK,
                    {
                        "expected": video_url,
                        "hosts": sorted(service.hosts),
                        "slug": service.slug,
                        "selector": _PLAYER_SELECTORS[service.slug],
                        "gates": _GATE_SELECTOR,
                        "ads": _AD_SELECTORS[service.slug],
                        "videoId": video_id,
                    },
                )
                reason = observation.get("reason") if isinstance(observation, dict) else None
                if reason == "played":
                    seconds = observation.get("seconds")
                    if (
                        isinstance(seconds, (int, float))
                        and math.isfinite(seconds)
                        and 0.24 < seconds <= _TIMEOUT
                    ):
                        return Result(
                            service,
                            Verdict.PLAYED,
                            "Public video played in Chromium",
                            (
                                f"Playback advanced {seconds:.1f} s across two consecutive intervals.",
                                f"Chromium / HTTPS / Reviewed public clip on "
                                f"{urlsplit(video_url).hostname}.",
                            ),
                        )
                if not isinstance(reason, str):
                    reason = ""
                return _unverified(
                    service,
                    _OBSERVATION_NOTES.get(reason, "The public video could not be verified."),
                )
            finally:
                await browser.close()

    try:
        return await asyncio.wait_for(observe(), timeout=_TIMEOUT)
    except (TimeoutError, asyncio.TimeoutError):
        return _unverified(service, "The browser check reached its time limit.")
    except (Error, OSError):
        return _unverified(service, "The browser could not load or inspect the public video.")
