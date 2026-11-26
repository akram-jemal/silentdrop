"""Command-line entry point for SilentDrop."""

import argparse
import asyncio
import csv
from collections.abc import Sequence
from pathlib import Path
from time import perf_counter

from rich.console import Console

from . import __version__
from .comparison import compare, load_report
from .dataset import CATEGORIES, DATASET_VERSION, filter_category, load_dataset
from .doctor import PROBE_HOST, run_doctor
from .models import utc_timestamp
from .reporter import REPORT_FORMATS, ScanReport, report_format, save_report
from .scanner import (
    DEFAULT_CONCURRENCY,
    DEFAULT_TIMEOUT,
    MAX_CONCURRENCY,
    MAX_TIMEOUT,
    MIN_TIMEOUT,
    scan,
)
from .ui import (
    print_categories,
    print_comparison,
    print_dataset_info,
    print_scan_results,
    print_scan_start,
    scan_progress,
)


def build_parser() -> argparse.ArgumentParser:
    """Define commands and options for both supported entry points."""
    parser = argparse.ArgumentParser(
        prog="silentdrop",
        description="Check a reviewed set of websites using ordinary HTTPS requests.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--no-color", action="store_true", help="disable color in terminal output")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")

    scan_parser = commands.add_parser("scan", help="check websites and save a local report")
    scan_parser.add_argument("--category", choices=CATEGORIES, help="scan one category")
    scan_parser.add_argument(
        "--failed-only", action="store_true", help="show only failures in the results table"
    )
    scan_parser.add_argument("--output", type=Path, help="report path ending in .json or .csv")
    scan_parser.add_argument(
        "--format",
        choices=REPORT_FORMATS,
        help="report format (default: infer from path or use JSON)",
    )
    scan_parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"simultaneous probes (1-{MAX_CONCURRENCY}, default: %(default)s)",
    )
    scan_parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        metavar="SECONDS",
        help=f"per-probe timeout ({MIN_TIMEOUT:g}-{MAX_TIMEOUT:g} seconds, default: %(default)s)",
    )
    scan_parser.set_defaults(handler=_run_scan)

    categories = commands.add_parser("categories", help="list categories and domain counts")
    categories.set_defaults(handler=_show_categories)

    dataset = commands.add_parser("dataset", help="inspect the offline dataset")
    dataset_commands = dataset.add_subparsers(dest="dataset_command", required=True)
    dataset_info = dataset_commands.add_parser("info", help="show dataset version and sources")
    dataset_info.set_defaults(handler=_show_dataset)

    doctor = commands.add_parser("doctor", help="check local Python TLS and proxy settings")
    doctor.add_argument(
        "--probe",
        action="store_true",
        help=f"also send one verified HTTPS probe to {PROBE_HOST}",
    )
    doctor.set_defaults(handler=_run_doctor)

    comparison = commands.add_parser("compare", help="compare two saved JSON or CSV reports")
    comparison.add_argument("before", type=Path, help="baseline report")
    comparison.add_argument("after", type=Path, help="report to compare with the baseline")
    comparison.set_defaults(handler=_compare_reports)
    return parser


def _validate_scan_options(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if not 1 <= args.concurrency <= MAX_CONCURRENCY:
        parser.error(f"--concurrency must be between 1 and {MAX_CONCURRENCY}")
    if not MIN_TIMEOUT <= args.timeout <= MAX_TIMEOUT:
        parser.error(f"--timeout must be between {MIN_TIMEOUT:g} and {MAX_TIMEOUT:g} seconds")
    if args.output is not None:
        try:
            extension = report_format(args.output)
        except ValueError as exc:
            parser.error(f"--output: {exc}")
        if args.format is not None and args.format != extension:
            parser.error("--format must match the --output filename extension")
        if args.output.is_dir():
            parser.error("--output must be a file path")


def _run_scan(args: argparse.Namespace, console: Console) -> None:
    entries = filter_category(load_dataset(), args.category)
    if not entries:
        raise ValueError("the selected category contains no domains")
    timestamp = utc_timestamp()
    path = args.output
    if path is None:
        stamp = timestamp.translate(str.maketrans("", "", "-:."))
        path = Path("reports") / f"silentdrop-{stamp}.{args.format or 'json'}"

    print_scan_start(console, len(entries), args.category)
    started = perf_counter()
    with scan_progress(console, len(entries)) as on_result:
        results = asyncio.run(
            scan(entries, concurrency=args.concurrency, timeout=args.timeout, on_result=on_result)
        )
    elapsed = perf_counter() - started
    report = ScanReport(DATASET_VERSION, timestamp, results)
    save_report(report, path)
    print_scan_results(console, report, path, elapsed, failed_only=args.failed_only)


def _show_categories(args: argparse.Namespace, console: Console) -> None:
    print_categories(console, load_dataset())


def _show_dataset(args: argparse.Namespace, console: Console) -> None:
    print_dataset_info(console, load_dataset())


def _run_doctor(args: argparse.Namespace, console: Console) -> int:
    return run_doctor(console, probe=args.probe)


def _compare_reports(args: argparse.Namespace, console: Console) -> None:
    before = load_report(args.before)
    after = load_report(args.after)
    print_comparison(
        console,
        compare(before, after),
        f"{args.before} (dataset {before.dataset_version})",
        f"{args.after} (dataset {after.dataset_version})",
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested command and return its process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    no_color = args.no_color or None
    console = Console(no_color=no_color, highlight=False)
    errors = Console(stderr=True, no_color=no_color, highlight=False)
    try:
        if args.command == "scan":
            _validate_scan_options(args, parser)
        return args.handler(args, console) or 0
    except KeyboardInterrupt:
        errors.print("Interrupted.", style="yellow")
        return 130
    except (OSError, ValueError, csv.Error) as exc:
        errors.print(str(exc), style="red", markup=False)
        return 1
