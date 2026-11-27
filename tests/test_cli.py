import asyncio
from dataclasses import replace
from urllib.parse import urlsplit

import pytest

from silentdrop import __version__, cli
from silentdrop.catalog import SERVICE_BY_SLUG, SERVICES
from silentdrop.results import Result, Verdict


def test_catalog_has_30_reviewed_public_services():
    assert len(SERVICES) == len(SERVICE_BY_SLUG) == 30
    assert {service.category for service in SERVICES} == {
        "Social",
        "Chat",
        "Video",
        "Music",
        "Gaming",
    }
    for service in SERVICES:
        for url in (service.url, service.video_url):
            if url:
                parsed = urlsplit(url)
                assert parsed.scheme == "https" and parsed.hostname in service.hosts
                assert parsed.username is None and parsed.password is None


def test_list_and_version_are_offline(capsys):
    assert cli.main(["--no-color", "list"]) == 0
    output = capsys.readouterr().out
    assert "telegram-web" in output and "Public page" in output
    assert "youtube" in output and "optional video playback" in output
    with pytest.raises(SystemExit) as info:
        cli.main(["--version"])
    assert info.value.code == 0
    assert capsys.readouterr().out == f"silentdrop {__version__}\n"


def test_unknown_service_fails_before_network(capsys):
    with pytest.raises(SystemExit) as info:
        cli.main(["check", "arbitrary.example"])
    assert info.value.code == 2
    assert "Run silentdrop list" in capsys.readouterr().err


def test_check_modes_share_results_and_nerd_displays_details(capsys, monkeypatch):
    from silentdrop import runner

    async def checks(services, *, on_result):
        result = Result(
            services[0], Verdict.LOADED, "Public page loaded", ("HTTPS GET", "HTTP 200")
        )
        on_result(result)
        return (result,)

    monkeypatch.setattr(runner, "check_services", checks)
    for mode in ("regular", "nerd"):
        assert cli.main(["--no-color", "check", "telegram-web", "--mode", mode]) == 0
        output = capsys.readouterr().out
        assert "Telegram Web" in output and "Page loaded" in output
        assert ("HTTP 200" in output) is (mode == "nerd")


@pytest.mark.asyncio
async def test_batch_preserves_catalog_order_and_bounds_concurrent_page_checks(monkeypatch):
    from silentdrop import runner

    batch = tuple(replace(service, video_url=None) for service in SERVICES)
    active = peak = 0
    completed = []

    async def page(service):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0)
            return Result(service, Verdict.LOADED, "Public page loaded", ())
        finally:
            active -= 1

    monkeypatch.setattr(runner, "check_page", page)
    results = await runner.check_services(batch, on_result=completed.append)
    assert 1 < peak <= 6
    assert tuple(result.service for result in results) == batch
    assert len(completed) == len(results) == 30


@pytest.mark.asyncio
@pytest.mark.parametrize("verdict", [Verdict.BLOCK_PAGE, Verdict.LOADED])
async def test_playback_fallback_preserves_page_evidence(monkeypatch, verdict):
    from silentdrop import runner

    service = SERVICE_BY_SLUG["youtube"]
    probes = []

    async def page(target):
        return Result(target, verdict, verdict.value, ("Page evidence",))

    async def browser(target):
        probes.append(target)
        return Result(target, Verdict.UNVERIFIED, "Couldn't verify", ("Playback unavailable",))

    monkeypatch.setattr(runner, "check_page", page)
    monkeypatch.setattr(runner, "check_playback", browser)
    (result,) = await runner.check_services((service,))
    assert result.verdict is verdict
    if verdict is Verdict.BLOCK_PAGE:
        assert probes == []
    else:
        assert probes == [service]
        assert result.summary == "Page loaded, playback unverified"
        assert result.details == ("Page loaded", "Page evidence", "Playback unavailable")
