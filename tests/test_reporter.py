import csv
import json
from dataclasses import replace

import pytest

from silentdrop import __version__
from silentdrop.comparison import Change, compare, load_report
from silentdrop.models import Classification, Outcome, ProbeResult
from silentdrop.reporter import SCHEMA_VERSION, ScanReport, save_report

SCAN_TIME = "2026-01-01T12:00:00.000000Z"


@pytest.fixture
def report():
    accessible = ProbeResult(
        domain="play.example",
        category="gaming",
        dns=Outcome.OK,
        connection=Outcome.OK,
        tls=Outcome.OK,
        http_status=200,
        latency_ms=51.3,
        error=None,
        timestamp=SCAN_TIME,
        classification=Classification.ACCESSIBLE,
    )
    restricted = replace(
        accessible,
        domain="chat.example",
        category="messaging",
        http_status=403,
        error="The endpoint denied this HEAD request (HTTP 403).",
        classification=Classification.HTTP_RESTRICTED,
    )
    uncertain = replace(
        accessible,
        domain="learn.example",
        category="education",
        http_status=451,
        error="HTTP 451 reports a legal restriction. Its source is unverified.",
        classification=Classification.SUSPECTED_FILTERING,
    )
    return ScanReport("synthetic-1", SCAN_TIME, (accessible, restricted, uncertain))


def test_json_export_contains_report_metadata_and_diagnostics(tmp_path, report):
    filename = tmp_path / "reports" / "network.json"
    save_report(report, filename)
    document = json.loads(filename.read_text(encoding="utf-8"))
    assert document["schema_version"] == SCHEMA_VERSION
    assert document["application_version"] == __version__
    assert document["dataset_version"] == "synthetic-1"
    assert document["scan_timestamp"] == SCAN_TIME
    assert document["summary"] == {"total": 3, "accessible": 1, "failed": 1, "inconclusive": 1}
    assert document["categories"]["gaming"] == {
        "total": 1,
        "accessible": 1,
        "failed": 0,
        "inconclusive": 0,
    }
    assert document["results"][0]["dns"] == "ok"
    assert document["results"][0]["latency_ms"] == 51.3
    assert document["results"][0]["error"] is None
    assert document["results"][1]["classification"] == "HTTP_RESTRICTED"
    assert document["results"][1]["error"].endswith("(HTTP 403).")
    assert document["limitations"]


def test_csv_export_contains_run_and_category_counts(tmp_path, report):
    filename = tmp_path / "network.CSV"
    save_report(report, filename)
    with filename.open(encoding="utf-8", newline="") as stream:
        play, chat, learn = csv.DictReader(stream)
    assert play["domain"] == "play.example"
    assert play["classification"] == "ACCESSIBLE"
    assert play["dns"] == play["connection"] == play["tls"] == "ok"
    assert play["error"] == ""
    assert chat["application_version"] == __version__
    assert chat["dataset_version"] == "synthetic-1"
    assert chat["scan_timestamp"] == SCAN_TIME
    assert chat["http_status"] == "403"
    assert chat["total"] == "3"
    assert chat["category_failed"] == "1"
    assert learn["inconclusive"] == "1"
    assert learn["category_inconclusive"] == "1"
    assert learn["limitations"]


def test_failed_write_preserves_an_existing_report(tmp_path, report):
    filename = tmp_path / "network.json"
    save_report(report, filename)
    original = filename.read_bytes()
    invalid = replace(report, results=(replace(report.results[0], latency_ms=float("nan")),))
    with pytest.raises(ValueError):
        save_report(invalid, filename)
    assert filename.read_bytes() == original
    assert list(tmp_path.iterdir()) == [filename]


def test_compares_json_and_csv_with_added_removed_and_changed_domains(tmp_path, report):
    baseline = tmp_path / "baseline.json"
    other = tmp_path / "other.csv"
    changed = replace(
        report.results[0],
        http_status=403,
        classification=Classification.HTTP_RESTRICTED,
    )
    added = replace(report.results[0], domain="new.example")
    save_report(report, baseline)
    save_report(
        replace(report, dataset_version="synthetic-2", results=(changed, report.results[1], added)),
        other,
    )
    before, after = load_report(baseline), load_report(other)
    assert before.dataset_version == "synthetic-1"
    assert after.dataset_version == "synthetic-2"
    comparison = compare(before, after)
    assert comparison.unchanged == 1
    assert comparison.changes == (
        Change("learn.example", Classification.SUSPECTED_FILTERING, None),
        Change("new.example", None, Classification.ACCESSIBLE),
        Change("play.example", Classification.ACCESSIBLE, Classification.HTTP_RESTRICTED),
    )
    assert compare(before, before).changes == ()


def test_rejects_duplicate_domains_in_reports(tmp_path, report):
    filename = tmp_path / "network.json"
    save_report(replace(report, results=(report.results[0], report.results[0])), filename)
    with pytest.raises(ValueError, match="duplicate hostname"):
        load_report(filename)


@pytest.mark.parametrize(
    ("filename", "contents", "diagnostic"),
    [
        ("network.json", '{"schema_version":2}', "JSON report schema"),
        ("network.json", '{"schema_version":true}', "JSON report schema"),
        ("network.json", "{", "network.json"),
        ("network.csv", "domain,classification\nplay.example,ACCESSIBLE\n", "CSV columns"),
        ("network.txt", "", "use a .json or .csv report filename"),
    ],
)
def test_rejects_invalid_report_files(tmp_path, filename, contents, diagnostic):
    path = tmp_path / filename
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError, match=diagnostic):
        load_report(path)
