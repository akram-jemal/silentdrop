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
from .classifier import summary_group
from .comparison import Comparison
from .dataset import CATEGORIES, DATASET_LICENSE, DATASET_VERSION, Domain
from .models import Classification, ProbeResult
from .reporter import LIMITATIONS, ScanReport

_GROUP_STYLES = {"accessible": "green", "failed": "red", "inconclusive": "yellow"}


def _result_label(classification: Classification | None) -> Text:
    if classification is None:
        return Text("Absent", style="dim")
    return Text(classification.value, style=_GROUP_STYLES[summary_group(classification)])


def print_scan_start(console: Console, total: int, category: str | None) -> None:
    banner = "+-------------------+\n|    SILENTDROP     |\n+-------------------+"
    console.print(Text(banner, style="bold green"))
    console.print(f"SilentDrop v{__version__}", style="bold")
    console.print("Not every connection dies loudly.")
    scope = CATEGORIES[category] if category else "all categories"
    console.print(f"Dataset {DATASET_VERSION} | Hosts {total} | {scope}\n", style="dim")


@contextmanager
def scan_progress(console: Console, total: int) -> Iterator[Callable[[ProbeResult], None]]:
    """Track completed probes during an interactive scan."""
    with Progress(
        TextColumn("[green]HTTPS[/]"),
        BarColumn(bar_width=None, complete_style="green", finished_style="green"),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TextColumn(
            "[green]{task.fields[accessible]} accessible[/]  "
            "[red]{task.fields[failed]} failed[/]  "
            "[yellow]{task.fields[inconclusive]} inconclusive[/]"
        ),
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
    title = "Failed results" if failed_only else "Domain results"
    table = Table(title=title, box=box.ASCII)
    table.add_column("Domain", overflow="fold")
    table.add_column("Category", overflow="fold")
    table.add_column("Classification", overflow="fold")
    table.add_column("HTTP", justify="right")
    table.add_column("Latency", justify="right")
    for result in report.results:
        if failed_only and summary_group(result.classification) != "failed":
            continue
        table.add_row(
            result.domain,
            result.category,
            _result_label(result.classification),
            str(result.http_status) if result.http_status is not None else "-",
            f"{result.latency_ms:.0f} ms",
        )
    if table.row_count:
        console.print(table)
    else:
        console.print("No failed results to display.")

    categories = Table(title="Category summary", box=box.ASCII)
    categories.add_column("Category")
    categories.add_column("Tested", justify="right")
    categories.add_column("Accessible", justify="right", style="green")
    categories.add_column("Failed", justify="right", style="red")
    categories.add_column("Inconclusive", justify="right", style="yellow")
    for category, summary in report.categories.items():
        categories.add_row(
            category,
            str(summary.total),
            str(summary.accessible),
            str(summary.failed),
            str(summary.inconclusive),
        )
    totals = report.summary
    categories.add_row(
        "Total",
        str(totals.total),
        str(totals.accessible),
        str(totals.failed),
        str(totals.inconclusive),
        style="bold",
    )
    console.print(categories)
    console.print(f"Checks completed {totals.total} | Elapsed {elapsed:.1f} s")
    console.print(Text.assemble(("Report ", "bold"), str(path)))
    console.print(" ".join(LIMITATIONS[:2]), style="dim")


def print_categories(console: Console, entries: tuple[Domain, ...]) -> None:
    counts = Counter(entry.category for entry in entries)
    table = Table(title="Dataset categories", box=box.ASCII)
    table.add_column("Category", style="green")
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
        table = Table(title="Accessibility differences", box=box.ASCII)
        table.add_column("Domain", overflow="fold")
        table.add_column("Before", overflow="fold")
        table.add_column("After", overflow="fold")
        for change in comparison.changes:
            table.add_row(change.domain, _result_label(change.before), _result_label(change.after))
        console.print(table)
    console.print(f"Changes {len(comparison.changes)} | Unchanged {comparison.unchanged}")
