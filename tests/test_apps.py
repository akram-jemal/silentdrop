import asyncio
import json
import sys
from io import StringIO

import pytest
from aiohttp import web

from silentdrop import apps, cli


def test_startup_regular_app_check_records_only_user_observation(monkeypatch, tmp_path, capsys):
    class TerminalInput(StringIO):
        def isatty(self):
            return True

    async def unexpected_probe(*args, **kwargs):
        pytest.fail("Regular mode should not run a website probe")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(apps, "scan", unexpected_probe)
    monkeypatch.setattr(sys, "stdin", TerminalInput("9\n1\n1\n2\nUniversity Wi-Fi\n"))
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    assert cli.main([]) == 0
    output = capsys.readouterr().out
    assert "Regular mode" in output and "Nerd mode" in output
    assert "Enter one of the listed numbers" in output
    assert "Telegram  /  Message delivery  Didn't work" in output
    assert "Website diagnostics" not in output
    (path,) = tmp_path.glob("reports/apps/*.json")
    report = json.loads(path.read_text())
    assert report["outcome"] == "failed"
    assert report["source"] == "user_observation"
    assert report["network_label"] == "University Wi-Fi"
    assert report["website_probe"] is None


@pytest.mark.asyncio
async def test_nerd_mode_distinguishes_app_failure_from_a_successful_website_probe(
    https_server, monkeypatch, tmp_path, capsys
):
    requests = []

    async def respond(request):
        requests.append((request.method, request.path))
        return web.Response(status=200)

    await https_server(respond)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", StringIO("1\n2\n\n"))
    assert await asyncio.to_thread(cli.main, ["app", "--mode", "nerd"]) == 0
    assert requests == [("HEAD", "/")]
    output = capsys.readouterr().out
    assert "Message delivery  Didn't work" in output
    assert "HTTPS HEAD https://web.telegram.org/" in output
    assert "DNS ok  /  TCP ok  /  TLS ok" in output
    assert "HTTP 200" in output
    (path,) = tmp_path.glob("reports/apps/*.json")
    report = json.loads(path.read_text())
    assert report["outcome"] == "failed"
    assert report["network_label"] is None
    assert report["website_probe"]["http_status"] == 200
    assert report["website_probe"]["method"] == "HEAD"


@pytest.mark.parametrize("selections", ["0\n", "1\n0\n", "1\n1\n"])
def test_exit_or_closed_input_saves_no_report(selections, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", StringIO(selections))
    assert cli.main(["app"]) == 0
    assert not (tmp_path / "reports").exists()
