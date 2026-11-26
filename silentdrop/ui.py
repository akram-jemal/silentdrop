"""Render dataset information, scan progress and reports with Rich."""

from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from rich import box
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

from . import __version__
from .classifier import CERTIFICATE_ERROR, summary_group
from .comparison import Comparison
from .dataset import CATEGORIES, DATASET_LICENSE, DATASET_VERSION, Domain
from .models import Classification, ProbeResult
from .reporter import LIMITATIONS, ScanReport

_ACCENT = "cyan"
_GROUP_STYLES = {"accessible": "green", "failed": "red", "inconclusive": "yellow"}


def _result_label(classification: Classification | None) -> Text:
    if classification is None:
        return Text("Absent", style="dim")
    color = _GROUP_STYLES[summary_group(classification)]
    if classification is Classification.HTTP_RESTRICTED:
        color = "yellow"
    return Text(classification.value.replace("_", " ").capitalize(), style=color)


def _table(*, expand: bool = False) -> Table:
    return Table(
        box=box.SIMPLE,
        border_style="dim",
        header_style="bold",
        padding=(0, 1),
        expand=expand,
    )


def print_scan_start(console: Console, total: int, category: str | None) -> None:
    scope = CATEGORIES[category] if category else "All categories"
    mark = ("-----", "----", "--", ".")
    identity = (
        Text.assemble(("SilentDrop", "bold"), (f"  v{__version__}", "dim")),
        Text("Not every connection dies loudly."),
        Text(f"{scope}  /  {total} hosts", style="dim"),
        Text(f"Dataset {DATASET_VERSION}", style="dim"),
    )
    console.print()
    for stroke, line in zip(mark, identity, strict=True):
        console.print(Text.assemble((f"{stroke:<7}  ", f"bold {_ACCENT}"), line))
    console.print()


@contextmanager
def scan_progress(console: Console, total: int) -> Iterator[Callable[[ProbeResult], None]]:
    """Track completed probes during an interactive scan."""
    columns = [
        TextColumn(f"[bold {_ACCENT}]HTTPS[/]"),
        BarColumn(bar_width=None, complete_style=_ACCENT, finished_style=_ACCENT),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    ]
    if console.width >= 76:
        columns.append(
            TextColumn(
                "[green]{task.fields[accessible]} accessible[/]  "
                "[red]{task.fields[failed]} failed[/]  "
                "[yellow]{task.fields[inconclusive]} inconclusive[/]"
            )
        )
    with Progress(
        *columns,
        console=console,
        disable=not console.is_terminal,
        transient=True,
        expand=True,
    ) as progress:
        counts = {"accessible": 0, "failed": 0, "inconclusive": 0}
        task = progress.add_task("Scan", total=total, **counts)

        def on_result(result: ProbeResult) -> None:
            counts[summary_group(result.classification)] += 1
            progress.update(task, advance=1, **counts)

        yield on_result


def print_scan_results(
    console: Console, report: ScanReport, path: Path, elapsed: float, *, failed_only: bool
) -> None:
    totals = report.summary
    console.print(
        Text.assemble(
            ("Scan complete", "bold"), (f"  {totals.total} tested / {elapsed:.1f} s", "dim")
        )
    )
    console.print(
        Text.assemble(
            (f"{totals.accessible} accessible", "green"),
            "   ",
            (f"{totals.failed} failed", "red"),
            "   ",
            (f"{totals.inconclusive} inconclusive", "yellow"),
        )
    )
    console.print(Text.assemble(("Report  ", "dim"), str(path), overflow="fold"))
    console.print()

    categories = report.categories
    width = console.width
    compact = width < 56
    show_category = len(categories) > 1 and width >= 72
    table = _table(expand=True)
    table.show_header = not compact
    table.add_column("Domain", overflow="fold", ratio=1)
    if not compact:
        if show_category:
            table.add_column("Category", style="dim")
        table.add_column("Result", overflow="fold", width=20)
        table.add_column("HTTP", justify="right", style="dim", no_wrap=True)
        table.add_column("Latency", justify="right", style="dim", no_wrap=True)

    for result in report.results:
        if failed_only and summary_group(result.classification) != "failed":
            continue
        domain = Text(result.domain)
        if len(categories) > 1 and not show_category:
            domain.append(f"\n{result.category}", style="dim")
        label = _result_label(result.classification)
        http = str(result.http_status) if result.http_status is not None else "-"
        latency = f"{result.latency_ms:.0f} ms"
        if compact:
            domain.append("\n  ")
            domain.append_text(label)
            domain.append(f"\n  HTTP {http} / {latency}", style="dim")
            table.add_row(domain)
        else:
            row = [domain]
            if show_category:
                row.append(Text(result.category))
            table.add_row(*row, label, http, latency)

    if table.row_count:
        console.print("Failed requests" if failed_only else "Domain results", style="bold")
        console.print(table)
    else:
        console.print("No failed results to display.", style="dim")

    if len(categories) > 1:
        _print_category_summary(console, report)

    certificate_failures = sum(
        result.classification is Classification.TLS_ERROR and result.error == CERTIFICATE_ERROR
        for result in report.results
    )
    if certificate_failures > 1:
        console.print(
            f"Certificate verification failed for {certificate_failures} of {totals.total} hosts.",
            style="yellow",
        )
        console.print(
            "Check the certificate store for the Python installation running SilentDrop. "
            "For python.org builds on macOS, run Install Certificates.command from the "
            "Python folder in Applications. On a managed network, ask IT which CA Python should trust.",
            style="dim",
        )

    if any(result.classification is Classification.HTTP_RESTRICTED for result in report.results):
        console.print(
            "HTTP restricted means HTTPS worked and the endpoint denied the probe or required "
            "authentication. Browsers can receive a different response.",
            style="dim",
        )
    console.print(LIMITATIONS[1], style="dim")


def _print_category_summary(console: Console, report: ScanReport) -> None:
    console.print("By category", style="bold")
    table = _table()
    table.add_column("Category", overflow="fold")
    table.add_column("Accessible", justify="right", style="green")
    table.add_column("Failed", justify="right", style="red")
    table.add_column("Inconclusive", justify="right", style="yellow")
    for category, summary in report.categories.items():
        table.add_row(
            category, str(summary.accessible), str(summary.failed), str(summary.inconclusive)
        )
    console.print(table)


def print_categories(console: Console, entries: tuple[Domain, ...]) -> None:
    counts = Counter(entry.category for entry in entries)
    console.print("Dataset categories", style="bold")
    table = _table()
    table.add_column("Category", style=_ACCENT)
    table.add_column("Service type")
    table.add_column("Hosts", justify="right")
    for category, label in CATEGORIES.items():
        table.add_row(category, label, str(counts[category]))
    console.print(table)


def print_dataset_info(console: Console, entries: tuple[Domain, ...]) -> None:
    upstream_count = sum(entry.source.startswith("citizenlab/") for entry in entries)
    console.print(f"Dataset {DATASET_VERSION} | {len(entries)} reviewed hostnames", style="bold")
    console.print(f"Citizen Lab Test Lists ({upstream_count}) and SilentDrop additions")
    console.print(f"Dataset license {DATASET_LICENSE}")
    print_categories(console, entries)


def print_comparison(console: Console, comparison: Comparison, before: str, after: str) -> None:
    console.print(Text.assemble(("Baseline ", "bold"), before))
    console.print(Text.assemble(("Compared ", "bold"), after))
    if comparison.changes:
        console.print("Accessibility differences", style="bold")
        table = _table()
        table.add_column("Domain", overflow="fold")
        table.add_column("Before", overflow="fold")
        table.add_column("After", overflow="fold")
        for change in comparison.changes:
            table.add_row(change.domain, _result_label(change.before), _result_label(change.after))
        console.print(table)
    console.print(f"Changes {len(comparison.changes)} | Unchanged {comparison.unchanged}")
