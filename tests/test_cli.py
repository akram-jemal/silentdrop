import asyncio
import io
import json
from pathlib import Path

import pytest
from aiohttp import web
from rich.console import Console

from silentdrop import __version__, cli
from silentdrop.dataset import DATASET_VERSION, Domain
from silentdrop.models import Classification, Outcome, ProbeResult
from silentdrop.reporter import ScanReport
from silentdrop.ui import print_scan_results


@pytest.mark.parametrize(
    ("args", "error"),
    [
        (["scan", "--category", "unknown"], "invalid choice"),
        (["scan", "--timeout", "nan"], "--timeout must be"),
        (["scan", "--timeout", "0"], "--timeout must be"),
        (["scan", "--concurrency", "33"], "--concurrency must be"),
        (["scan", "--format", "xml"], "invalid choice"),
        (["scan", "--output", "file.txt"], "use a .json or .csv report filename"),
        (["scan", "--output", "file.csv", "--format", "json"], "--format must match"),
        (["compare", "only-one.json"], "required"),
        (["dataset"], "required"),
    ],
)
def test_rejects_invalid_arguments(args, error, capsys, monkeypatch):
    async def unexpected_scan(*args, **kwargs):
        pytest.fail("invalid arguments reached the scanner")

    monkeypatch.setattr(cli, "scan", unexpected_scan)
    with pytest.raises(SystemExit) as exit_info:
        cli.main(args)
    assert exit_info.value.code == 2
    assert error in capsys.readouterr().err


def test_help_version_categories_and_dataset_info(capsys):
    assert cli.main([]) == 0
    help_output = capsys.readouterr().out
    assert "categories" in help_output and "compare" in help_output

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out == f"silentdrop {__version__}\n"

    assert cli.main(["categories"]) == 0
    categories = capsys.readouterr().out
    assert "gaming" in categories and "Social media" in categories

    assert cli.main(["dataset", "info"]) == 0
    dataset = capsys.readouterr().out
    assert DATASET_VERSION in dataset and "CC BY-NC-SA 4.0" in dataset


def test_compare_reports_read_failure_is_actionable(capsys, tmp_path):
    missing = tmp_path / "missing.json"
    assert cli.main(["compare", str(missing), str(missing)]) == 1
    assert "missing.json" in capsys.readouterr().err


@pytest.mark.asyncio
async def test_scan_and_compare_reports_via_cli_with_loopback_https(
    https_server, capsys, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    entries = (
        Domain("play.example", "gaming", "silentdrop"),
        Domain("social.example", "social", "silentdrop"),
    )
    monkeypatch.setattr(cli, "load_dataset", lambda: entries)
    statuses = iter((200, 403))

    async def respond(request):
        return web.Response(status=next(statuses))

    await https_server(respond)

    before = tmp_path / "reports" / "before.json"
    args = ["--no-color", "scan", "--category", "gaming", "--failed-only"]
    assert await asyncio.to_thread(cli.main, [*args, "--output", str(before)]) == 0
    output = capsys.readouterr().out
    assert f"SilentDrop  v{__version__}" in output
    assert "No failed results" in output
    document = json.loads(before.read_text(encoding="utf-8"))
    assert document["summary"]["total"] == document["summary"]["accessible"] == 1
    assert [result["domain"] for result in document["results"]] == ["play.example"]

    assert await asyncio.to_thread(cli.main, [*args, "--format", "csv"]) == 0
    output = capsys.readouterr().out
    assert "HTTP restricted" in output
    assert "denied request or an authentication requirement" in output
    (after,) = (tmp_path / "reports").glob("silentdrop-*.csv")

    assert cli.main(["compare", str(before), str(after)]) == 0
    comparison = capsys.readouterr().out
    assert "play.example" in comparison
    assert "Changes 1 | Unchanged 0" in comparison


def test_interrupted_scan_returns_130_and_leaves_no_report(monkeypatch, capsys, tmp_path):
    def interrupt(coroutine):
        coroutine.close()
        raise KeyboardInterrupt

    monkeypatch.setattr(cli.asyncio, "run", interrupt)
    destination = tmp_path / "interrupted.json"
    assert cli.main(["scan", "--output", str(destination)]) == 130
    assert "Interrupted." in capsys.readouterr().err
    assert not destination.exists()


def test_narrow_scan_results_keep_label_and_http_details_readable():
    result = ProbeResult(
        domain="service.example",
        category="social",
        dns=Outcome.OK,
        connection=Outcome.OK,
        tls=Outcome.OK,
        http_status=403,
        latency_ms=199,
        error=None,
        timestamp="2026-11-26T12:00:00Z",
        classification=Classification.HTTP_RESTRICTED,
    )
    output = io.StringIO()
    console = Console(file=output, width=42, color_system=None)
    report = ScanReport(DATASET_VERSION, result.timestamp, (result,))
    print_scan_results(console, report, Path("reports/sample.json"), 0.2, failed_only=False)
    rendered = output.getvalue()
    assert "service.example" in rendered
    assert "HTTP restricted" in rendered
    assert "HTTP 403 / 199 ms" in rendered
    assert "\x1b" not in rendered
    assert max(map(len, rendered.splitlines())) <= 42
