"""Interactive SilentDrop service picker and results console."""

from collections import Counter
from collections.abc import Sequence

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Key, Resize
from textual.widgets import Button, DataTable, Footer, Input, ProgressBar, Static
from textual.worker import Worker, WorkerState

from .catalog import SERVICES, Service
from .results import Result, Verdict
from .runner import check_services

MOTTO = "Not every connection dies loudly."
_MINT = "#75e5c2"
_COLORS = {
    Verdict.LOADED: "#8ee5a1",
    Verdict.PLAYED: "#8ee5a1",
    Verdict.BLOCK_PAGE: "#ff929c",
    Verdict.UNVERIFIED: "#f4ce88",
}


class SilentDropApp(App[None]):
    """Check public services and inspect the results without leaving the terminal."""

    TITLE = "SilentDrop"
    BINDINGS = (
        Binding("ctrl+f", "choose_one", "Find", show=False),
        Binding("f5", "check_all", "Check all"),
        Binding("f2", "toggle_mode", "View"),
        Binding("escape", "back", "Back"),
        Binding("q", "quit", "Quit"),
    )
    CSS = """
    Screen { background: #0d171c; color: #e2f0ee; }
    #workspace {
        width: 100%;
        max-width: 120;
        height: 1fr;
        padding: 0 2;
        align-horizontal: left;
    }
    #identity {
        height: 3;
        padding-top: 1;
        border-left: thick #75e5c2;
        padding-left: 1;
    }
    #motto { color: #a2bbb8; }
    #tools { height: 2; margin-top: 1; }
    Button {
        min-width: 1;
        height: 1;
        border: none;
        background: #1b2c34;
        color: #dbece9;
        padding: 0;
        margin-right: 1;
    }
    Button:focus { background: #75e5c2; color: #0d171c; text-style: bold; }
    #view-mode { color: #75e5c2; }
    #view-mode:focus { color: #0d171c; }
    #filter {
        height: 3;
        border: tall #355350;
        background: #132228;
        color: #e2f0ee;
    }
    #filter:focus { border: tall #75e5c2; }
    #services {
        height: 1fr;
        min-height: 3;
        background: #122027;
        scrollbar-size-vertical: 1;
    }
    DataTable > .datatable--header { background: #1b2c34; color: #afcfca; text-style: bold; }
    DataTable > .datatable--odd-row { background: #15242b; }
    DataTable > .datatable--even-row { background: #122027; }
    DataTable > .datatable--cursor { background: #244844; color: #f1fffb; text-style: bold; }
    #details {
        display: none;
        height: auto;
        max-height: 8;
        margin-top: 1;
        border-left: thick #75e5c2;
        background: #17282e;
        padding: 0 1;
        scrollbar-size-vertical: 1;
    }
    #details-text { height: auto; }
    #status { color: #b1c7c4; min-height: 1; height: auto; margin-top: 1; }
    #progress { display: none; height: 1; margin-bottom: 1; width: 100%; }
    #progress Bar { width: 1fr; }
    #progress Bar > .bar--bar { color: #75e5c2; background: #1b2c34; }
    Footer { background: #17282e; color: #c5dbd8; }
    FooterKey > .footer-key--key { color: #75e5c2; background: #17282e; }
    FooterKey > .footer-key--description { color: #c5dbd8; background: #17282e; }
    #workspace.compact { padding: 0 1; }
    #workspace.compact #tools { margin-top: 0; height: 1; }
    #workspace.compact #details { max-height: 6; margin-top: 0; }
    #workspace.compact #status { margin-top: 0; }
    """

    def __init__(self, services: Sequence[Service] = SERVICES) -> None:
        super().__init__()
        self._services = tuple(services)
        self._targets: tuple[Service, ...] | None = None
        self._visible: tuple[Service, ...] = ()
        self._results: dict[str, Result] = {}
        self._nerd = False
        self._worker: Worker[tuple[Result, ...]] | None = None
        self._checking = False
        self._columns: tuple[int, ...] = ()
        self._final: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="workspace"):
            with Vertical(id="identity"):
                yield Static(Text("S I L E N T D R O P", style=f"bold {_MINT}"))
                yield Static(MOTTO, id="motto", markup=False)
            with Horizontal(id="tools"):
                yield Button("Check one", id="check-one")
                yield Button("Check all", id="check-all")
                yield Button("View: Regular", id="view-mode")
            yield Input(placeholder="Filter services", id="filter")
            yield DataTable(
                id="services",
                cursor_type="row",
                zebra_stripes=True,
                show_row_labels=False,
            )
            with VerticalScroll(id="details"):
                yield Static(id="details-text", markup=False)
            yield Static(id="status", markup=False)
            yield ProgressBar(id="progress", show_percentage=False, show_eta=False)
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self._update_layout()
        self._render_table()
        self._render_status()
        self.query_one("#check-one", Button).focus()

    def on_resize(self, event: Resize) -> None:
        if self.is_mounted and self._layout_widths(event.size.width) != self._columns:
            self._update_layout()
            self._render_table()
            self._render_status()

    def _update_layout(self) -> None:
        compact = self.size.width < 54
        self.query_one("#workspace", Vertical).set_class(compact, "compact")
        mode = "Nerd" if self._nerd else "Regular"
        self.query_one("#view-mode", Button).label = mode if compact else f"View: {mode}"

    @staticmethod
    def _layout_widths(width: int) -> tuple[int, ...]:
        inner = min(width, 120) - 5
        if width >= 72:
            service = min(28, max(20, inner // 3))
            return (service, 16, max(21, inner - service - 22))
        service = max(12, min(26, inner - 31))
        return (service, max(12, inner - service - 4))

    def _query_filter(self) -> Input:
        return self.query_one("#filter", Input)

    def _table(self) -> DataTable:
        return self.query_one("#services", DataTable)

    def _result_cell(self, slug: str) -> Text:
        result = self._results.get(slug)
        if result is None:
            return Text("Queued" if self._checking else "—", style="#a2bbb8")
        label = result.verdict.value
        if len(self._columns) == 2:
            if result.verdict is Verdict.BLOCK_PAGE:
                label = "Block page detected"
            elif result.verdict is Verdict.LOADED and result.service.video_url:
                label = "Page only"
        return Text(
            label,
            style=_COLORS[result.verdict],
            no_wrap=True,
            overflow="ellipsis",
        )

    def _check_cell(self, service: Service) -> Text:
        result = self._results.get(service.slug)
        if service.video_url and result is not None and result.verdict is Verdict.LOADED:
            scope = "Page only"
        else:
            scope = "Page + video" if service.video_url else "Public page"
        return Text(scope, style="#b1c7c4", no_wrap=True, overflow="ellipsis")

    def _render_table(self) -> None:
        table = self._table()
        previous = (
            self._visible[table.cursor_row].slug if table.cursor_row < len(self._visible) else None
        )
        widths = self._layout_widths(self.size.width)
        wide = len(widths) == 3
        table.clear(columns=widths != self._columns)
        if widths != self._columns:
            headings = ("Service", "Check", "Result") if wide else ("Service", "Result")
            for heading, width in zip(headings, widths, strict=True):
                table.add_column(heading, width=width, key=heading.lower())
            self._columns = widths
        search = self._query_filter().value.strip().casefold()
        services = self._services if self._targets is None else self._targets
        self._visible = tuple(
            service
            for service in services
            if search in f"{service.name} {service.slug} {service.category}".casefold()
        )
        highlighted = 0
        for row, service in enumerate(self._visible):
            cells = [Text(service.name, no_wrap=True, overflow="ellipsis")]
            if wide:
                cells.append(self._check_cell(service))
            cells.append(self._result_cell(service.slug))
            table.add_row(*cells, key=service.slug)
            if service.slug == previous:
                highlighted = row
        if self._visible:
            table.move_cursor(row=highlighted, column=0)
        self._render_details()

    def _render_details(self) -> None:
        panel = self.query_one("#details", VerticalScroll)
        row = self._table().cursor_row
        service = self._visible[row] if row < len(self._visible) else None
        result = self._results.get(service.slug) if service else None
        panel.display = result is not None and self._targets is not None
        if not panel.display or result is None:
            return
        detail = Text.assemble(
            (result.service.name, "bold"),
            "  ·  ",
            (result.verdict.value, _COLORS[result.verdict]),
        )
        detail.append(f"\n{result.summary}")
        if self._nerd and result.details:
            detail.append("\n" + "\n".join(result.details), style="#b1c7c4")
        self.query_one("#details-text", Static).update(detail)
        panel.scroll_home(animate=False)

    def _render_status(self) -> None:
        status = self.query_one("#status", Static)
        if self._targets is None:
            hint = f"{len(self._visible)} of {len(self._services)} services"
            if not self._visible:
                hint = "No services match the filter"
            status.update(hint)
            return
        counts = Counter(result.verdict for result in self._results.values())
        text = Text(f"{len(self._results)}/{len(self._targets)} checked")
        if self._final:
            text.append(f"  /  {self._final}", style="bold")
        labels = {
            Verdict.LOADED: "Pages",
            Verdict.PLAYED: "Video",
            Verdict.BLOCK_PAGE: "Blocks",
            Verdict.UNVERIFIED: "Unsure",
        }
        separator = "\n" if self.size.width < 54 else "  ·  "
        for verdict, label in labels.items():
            if counts[verdict]:
                text.append(separator)
                text.append(f"{label} {counts[verdict]}", style=_COLORS[verdict])
                separator = " · "
        status.update(text)

    def action_choose_one(self) -> None:
        if not self._checking:
            self._targets = None
            self._query_filter().value = ""
            self._render_table()
            self._render_status()
            self._query_filter().focus()

    def action_check_all(self) -> None:
        self._start(self._services)

    def action_toggle_mode(self) -> None:
        self._nerd = not self._nerd
        self._update_layout()
        self._render_details()

    def action_back(self) -> None:
        if self._checking and self._worker is not None:
            self._worker.cancel()
        elif self.focused is self.query_one("#details", VerticalScroll):
            self._table().focus()
        elif self._targets is not None:
            self.action_choose_one()
        else:
            self._query_filter().value = ""

    @on(Button.Pressed)
    def _activate_button(self, event: Button.Pressed) -> None:
        if event.button.id == "check-one":
            self.action_choose_one()
        elif event.button.id == "check-all":
            self.action_check_all()
        elif event.button.id == "view-mode":
            self.action_toggle_mode()

    @on(Input.Changed, "#filter")
    def _filter_services(self) -> None:
        self._render_table()
        self._render_status()

    @on(Input.Submitted, "#filter")
    def _submit_filter(self) -> None:
        if self._visible:
            self._table().focus()
            if len(self._visible) == 1 and self._targets is None:
                self._start(self._visible)

    def on_key(self, event: Key) -> None:
        if event.key == "down" and self.focused is self._query_filter() and self._visible:
            self._table().focus()
            event.stop()

    @on(DataTable.RowHighlighted, "#services")
    def _highlight_service(self) -> None:
        self._render_details()

    @on(DataTable.RowSelected, "#services")
    def _select_service(self, event: DataTable.RowSelected) -> None:
        if self._targets is None and event.cursor_row < len(self._visible):
            self._start((self._visible[event.cursor_row],))
        else:
            self._render_details()
            details = self.query_one("#details", VerticalScroll)
            if details.display:
                details.focus()

    def _start(self, services: tuple[Service, ...]) -> None:
        if self._checking or not services:
            return
        self._checking = True
        self._targets = services
        self._results.clear()
        self._final = None
        self._query_filter().value = ""
        self._set_controls_busy(True)
        self._render_table()
        self._table().focus()
        self._render_status()
        progress = self.query_one(ProgressBar)
        progress.update(total=len(services), progress=0)
        progress.display = True
        self._worker = self.run_worker(
            check_services(services, on_result=self._record_result), exit_on_error=False
        )

    def _set_controls_busy(self, busy: bool) -> None:
        self.query_one("#check-one", Button).disabled = busy
        self.query_one("#check-all", Button).disabled = busy
        self._query_filter().disabled = busy

    def _record_result(self, result: Result) -> None:
        self._results[result.service.slug] = result
        table = self._table()
        slug = result.service.slug
        table.update_cell(slug, "result", self._result_cell(slug))
        if len(self._columns) == 3:
            table.update_cell(slug, "check", self._check_cell(result.service))
        self.query_one(ProgressBar).update(progress=len(self._results))
        self._render_status()
        self._render_details()

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        endings = {
            WorkerState.SUCCESS: "Complete",
            WorkerState.CANCELLED: "Cancelled",
            WorkerState.ERROR: "Check ended early",
        }
        if event.worker is not self._worker or event.state not in endings:
            return
        self._worker = None
        self._checking = False
        self._final = endings[event.state]
        self._set_controls_busy(False)
        self.query_one(ProgressBar).display = False
        self._render_table()
        self._render_status()


def run_terminal() -> None:
    """Open the interactive terminal application."""
    SilentDropApp().run()
