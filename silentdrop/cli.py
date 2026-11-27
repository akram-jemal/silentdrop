"""Command-line entry point for SilentDrop."""

import argparse
import sys
from collections.abc import Sequence

from rich.console import Console
from rich.table import Table
from rich.text import Text

from . import __version__
from .catalog import SERVICE_BY_SLUG, SERVICES
from .doctor import PROBE_HOST, run_doctor
from .results import Verdict

_COLORS = {
    Verdict.LOADED: "#8ee5a1",
    Verdict.PLAYED: "#8ee5a1",
    Verdict.BLOCK_PAGE: "#ff929c",
    Verdict.UNVERIFIED: "#f4ce88",
}
_HEADER = "bold #75e5c2"


def build_parser() -> argparse.ArgumentParser:
    """Define interactive and scriptable entry points."""
    parser = argparse.ArgumentParser(
        prog="silentdrop",
        description="Check public pages and playback on your current network.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--no-color", action="store_true", help="disable color in command output")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")

    check = commands.add_parser("check", help="check one service or all services")
    check.add_argument("service", metavar="SERVICE", help="service from silentdrop list, or all")
    check.add_argument(
        "--mode",
        choices=("regular", "nerd"),
        default="regular",
        help="show plain or technical results",
    )
    commands.add_parser("list", help="list supported service names and check types")

    doctor = commands.add_parser("doctor", help="check local Python TLS and proxy settings")
    doctor.add_argument(
        "--probe",
        action="store_true",
        help=f"also send one verified HTTPS probe to {PROBE_HOST}",
    )
    return parser


def _list(console: Console) -> None:
    table = Table(box=None, header_style=_HEADER)
    table.add_column("Service")
    table.add_column("Category")
    table.add_column("Check")
    for service in SERVICES:
        check_type = (
            "Public page and optional video playback" if service.video_url else "Public page"
        )
        table.add_row(service.slug, service.category, check_type)
    console.print(table)


def _check(console: Console, slug: str, mode: str) -> None:
    import asyncio

    from rich.progress import Progress

    from .runner import check_services

    selected = SERVICES if slug == "all" else (SERVICE_BY_SLUG[slug],)
    with Progress(console=console, transient=True, disable=not console.is_terminal) as progress:
        task = progress.add_task("Checking services", total=len(selected))
        results = asyncio.run(
            check_services(selected, on_result=lambda result: progress.advance(task))
        )

    table = Table(box=None, header_style=_HEADER)
    table.add_column("Service")
    table.add_column("Result")
    for result in results:
        label = (
            result.summary
            if result.verdict is Verdict.LOADED and result.service.video_url
            else result.verdict.value
        )
        table.add_row(result.service.name, Text(label, style=_COLORS[result.verdict]))
    console.print(table)

    if mode == "nerd":
        for result in results:
            console.print(
                Text(f"\n{result.service.name}  /  {result.verdict.value}", style=_HEADER)
            )
            console.print(Text(result.summary))
            for line in result.details:
                console.print(Text(line))


def main(argv: Sequence[str] | None = None) -> int:
    """Run a command or open the interactive dashboard from a terminal."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "check" and args.service != "all" and args.service not in SERVICE_BY_SLUG:
        parser.error(f"unknown service {args.service!r}. Run silentdrop list for service names.")

    console = Console(no_color=args.no_color or None, highlight=False)
    try:
        if args.command == "check":
            _check(console, args.service, args.mode)
        elif args.command == "list":
            _list(console)
        elif args.command == "doctor":
            return run_doctor(console, probe=args.probe)
        elif sys.stdin.isatty() and sys.stdout.isatty() and not args.no_color:
            from .terminal import run_terminal

            run_terminal()
        else:
            parser.print_help()
    except KeyboardInterrupt:
        Console(stderr=True, no_color=args.no_color or None).print("Interrupted.", style="yellow")
        return 130
    return 0
