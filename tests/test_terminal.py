import asyncio

import pytest
from textual.containers import VerticalScroll
from textual.widgets import Button, DataTable, Input, ProgressBar, Static

from silentdrop import terminal
from silentdrop.catalog import Service
from silentdrop.results import Result, Verdict

TELEGRAM = Service("telegram", "Telegram", "Chat", "https://telegram.example/", ("Telegram",))
VIDEO = Service(
    "video",
    "Video",
    "Streaming",
    "https://video.example/",
    ("Video",),
    video_url="https://video.example/watch",
)


@pytest.mark.asyncio
async def test_keyboard_search_and_same_result_in_nerd_mode(monkeypatch):
    calls = []

    async def check(services, *, on_result):
        calls.append(services)
        (service,) = services
        result = Result(service, Verdict.LOADED, "The public page answered.", ("HTTP 200",))
        on_result(result)
        return (result,)

    monkeypatch.setattr(terminal, "check_services", check)
    app = terminal.SilentDropApp((TELEGRAM, VIDEO))

    async with app.run_test(size=(86, 24)) as pilot:
        table = app.query_one(DataTable)
        search = app.query_one(Input)
        details = app.query_one("#details-text", Static)
        await pilot.press("ctrl+f", "q")
        assert search.value == "q"
        assert table.row_count == 0

        await pilot.press("backspace", *"telegram", "down", "enter")
        await pilot.pause()
        assert calls == [(TELEGRAM,)]
        assert app.query_one("#details", VerticalScroll).display
        assert "The public page answered." in str(details.content)
        assert "HTTP 200" not in str(details.content)
        await pilot.press("f2")
        assert str(app.query_one("#view-mode", Button).label) == "View: Nerd"
        assert "HTTP 200" in str(details.content)
        assert calls == [(TELEGRAM,)]

        await pilot.press("escape")
        assert table.row_count == 2


@pytest.mark.asyncio
async def test_check_all_shows_progress_and_keeps_partial_results_on_cancel(monkeypatch):
    started = asyncio.Event()

    async def check(services, *, on_result):
        assert services == (TELEGRAM, VIDEO)
        on_result(Result(VIDEO, Verdict.LOADED, "Page loaded, playback unverified", ()))
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(terminal, "check_services", check)
    app = terminal.SilentDropApp((TELEGRAM, VIDEO))

    async with app.run_test(size=(86, 24)) as pilot:
        await pilot.press("f5")
        await asyncio.wait_for(started.wait(), timeout=3)
        await pilot.pause()

        table = app.query_one(DataTable)
        progress = app.query_one(ProgressBar)
        assert progress.display
        assert progress.progress == 1
        assert str(table.get_cell("video", "check")) == "Page only"
        assert str(table.get_cell("telegram", "result")) == "Queued"

        await pilot.press("escape")
        await pilot.pause()

        assert not progress.display
        assert "Cancelled" in str(app.query_one("#status", Static).content)
        assert str(table.get_cell("video", "result")) == Verdict.LOADED.value


@pytest.mark.asyncio
async def test_narrow_view_keeps_results_readable(monkeypatch):
    async def check(services, *, on_result):
        results = (
            Result(services[0], Verdict.BLOCK_PAGE, "A network policy page answered.", ()),
            Result(services[1], Verdict.LOADED, "Page loaded, playback unverified.", ()),
        )
        for result in results:
            on_result(result)
        return results

    monkeypatch.setattr(terminal, "check_services", check)
    app = terminal.SilentDropApp((TELEGRAM, VIDEO))
    async with app.run_test(size=(42, 20)) as pilot:
        table = app.query_one(DataTable)
        assert len(table.columns) == 2
        assert table.row_count == 2
        assert app.query_one("#view-mode", Button).region.right <= app.size.width
        await pilot.press("f5")
        await pilot.pause()
        assert str(table.get_cell("telegram", "result")) == "Block page detected"
        assert str(table.get_cell("video", "result")) == "Page only"
        status = str(app.query_one("#status", Static).content)
        assert status.splitlines() == ["2/2 checked  /  Complete", "Pages 1 · Blocks 1"]
