import sys
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from silentdrop import playback
from silentdrop.catalog import SERVICE_BY_SLUG
from silentdrop.results import Verdict

YOUTUBE = SERVICE_BY_SLUG["youtube"]


class BrowserError(Exception):
    """A stand-in for Playwright transport errors."""


@pytest.fixture
def browser_pipeline(monkeypatch):
    page = SimpleNamespace(
        url=YOUTUBE.video_url,
        goto=AsyncMock(return_value=SimpleNamespace(ok=True)),
        evaluate=AsyncMock(return_value={"reason": "played", "seconds": 0.86}),
    )
    context = SimpleNamespace(new_page=AsyncMock(return_value=page), route=AsyncMock())
    browser = SimpleNamespace(new_context=AsyncMock(return_value=context), close=AsyncMock())
    launch = AsyncMock(return_value=browser)
    manager = AsyncMock()
    manager.__aenter__.return_value = SimpleNamespace(chromium=SimpleNamespace(launch=launch))
    api = SimpleNamespace(Error=BrowserError, async_playwright=Mock(return_value=manager))
    monkeypatch.setitem(sys.modules, "playwright.async_api", api)
    return SimpleNamespace(
        page=page, context=context, browser=browser, launch=launch, driver=manager
    )


@pytest.mark.asyncio
async def test_browser_support_is_optional(monkeypatch):
    monkeypatch.setitem(sys.modules, "playwright.async_api", None)

    result = await playback.check_playback(YOUTUBE)

    assert result.verdict is Verdict.UNVERIFIED
    assert any(".[playback]" in detail for detail in result.details)
    assert any("playwright install chromium" in detail for detail in result.details)


@pytest.mark.asyncio
async def test_rejects_unreviewed_video_navigation(browser_pipeline):
    requested = replace(YOUTUBE, video_url="https://outside.example/watch?v=ABCDEFGHIJK")

    result = await playback.check_playback(requested)

    assert result.verdict is Verdict.UNVERIFIED
    browser_pipeline.launch.assert_not_called()


@pytest.mark.asyncio
async def test_positive_verdict_requires_bounded_advancing_playback(browser_pipeline):
    result = await playback.check_playback(YOUTUBE)

    assert result.verdict is Verdict.PLAYED
    assert "0.9 s" in result.details[0]
    assert "consecutive intervals" in result.details[0]
    browser_pipeline.page.goto.assert_awaited_once_with(
        YOUTUBE.video_url, wait_until="domcontentloaded", timeout=8_000
    )
    browser_pipeline.page.evaluate.assert_awaited_once()
    browser_pipeline.browser.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("observation", "fragment"),
    [
        ({"reason": "gate"}, "sign-in, consent or verification"),
        ({"reason": "ad"}, "advertisement"),
        ({"reason": "missing"}, "visible player"),
        ({"reason": "stalled"}, "did not advance consistently"),
        ({"reason": "played", "seconds": 0}, "could not be verified"),
    ],
)
async def test_unverified_observations_never_claim_playback(
    browser_pipeline, observation, fragment
):
    browser_pipeline.page.evaluate.return_value = observation

    result = await playback.check_playback(YOUTUBE)

    assert result.verdict is Verdict.UNVERIFIED
    assert fragment in result.details[0]
    browser_pipeline.browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_browser_setup_failure_does_not_echo_paths(browser_pipeline):
    browser_pipeline.launch.side_effect = BrowserError("private-browser-path-marker")

    result = await playback.check_playback(YOUTUBE)

    assert result.verdict is Verdict.UNVERIFIED
    assert any("Chromium could not start" in detail for detail in result.details)
    assert "private-browser-path-marker" not in repr(result)


@pytest.mark.asyncio
async def test_unavailable_driver_leaves_playback_unverified(browser_pipeline):
    browser_pipeline.driver.__aenter__.side_effect = PermissionError("private-driver-marker")

    result = await playback.check_playback(YOUTUBE)

    assert result.verdict is Verdict.UNVERIFIED
    assert "private-driver-marker" not in repr(result)
    browser_pipeline.launch.assert_not_called()


@pytest.mark.asyncio
async def test_browser_route_rejects_main_frame_redirect_and_disallowed_host(browser_pipeline):
    await playback.check_playback(YOUTUBE)
    _, handler = browser_pipeline.context.route.await_args.args

    request = SimpleNamespace(
        method="GET",
        url="https://outside.example/",
        frame=SimpleNamespace(parent_frame=None),
        is_navigation_request=lambda: True,
    )
    route = SimpleNamespace(
        request=request,
        abort=AsyncMock(),
        fetch=AsyncMock(return_value=SimpleNamespace(status=302)),
        fulfill=AsyncMock(),
        continue_=AsyncMock(),
    )
    await handler(route)
    route.abort.assert_awaited_once()
    route.fetch.assert_not_called()

    route.abort.reset_mock()
    route.request.url = YOUTUBE.video_url
    await handler(route)
    route.fetch.assert_awaited_once_with(max_redirects=0, timeout=7_000)
    route.abort.assert_awaited_once()
    route.fulfill.assert_not_called()
