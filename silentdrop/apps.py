"""Guide a user through an app check and optionally probe its public website."""

import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from rich.console import Console
from rich.text import Text

from . import __version__
from .dataset import Domain
from .models import utc_timestamp
from .reporter import atomic_report
from .scanner import scan

MODES = ("regular", "nerd")


@dataclass(frozen=True)
class AppCheck:
    name: str
    action: str
    instructions: str
    host: str


_MESSAGE = "Send a test message to an account you control and check that it arrives."
_FEED = "Refresh the feed and open a recent post you haven't already loaded."
_APPS = (
    AppCheck("Telegram", "Message delivery", _MESSAGE, "web.telegram.org"),
    AppCheck("WhatsApp", "Message delivery", _MESSAGE, "web.whatsapp.com"),
    AppCheck("Signal", "Message delivery", _MESSAGE, "signal.org"),
    AppCheck("Discord", "Message delivery", _MESSAGE, "discord.com"),
    AppCheck("Messenger", "Message delivery", _MESSAGE, "www.messenger.com"),
    AppCheck("WeChat", "Message delivery", _MESSAGE, "www.wechat.com"),
    AppCheck("Snapchat", "Chat delivery", _MESSAGE, "www.snapchat.com"),
    AppCheck("Slack", "Message delivery", _MESSAGE, "slack.com"),
    AppCheck("Microsoft Teams", "Message delivery", _MESSAGE, "teams.microsoft.com"),
    AppCheck("Instagram", "Feed and post loading", _FEED, "www.instagram.com"),
    AppCheck("Facebook", "Feed and post loading", _FEED, "www.facebook.com"),
    AppCheck("Reddit", "Feed and post loading", _FEED, "www.reddit.com"),
    AppCheck("X", "Feed and post loading", _FEED, "x.com"),
    AppCheck("Threads", "Feed and post loading", _FEED, "www.threads.net"),
    AppCheck("Bluesky", "Feed and post loading", _FEED, "bsky.app"),
    AppCheck("LinkedIn", "Feed and post loading", _FEED, "www.linkedin.com"),
    AppCheck(
        "TikTok", "Video playback", "Open a new video and check that it plays.", "www.tiktok.com"
    ),
    AppCheck(
        "YouTube", "Video playback", "Open a new video and check that it plays.", "www.youtube.com"
    ),
)
_OUTCOMES = {
    "worked": "Worked",
    "failed": "Didn't work",
    "untested": "Couldn't check",
}


def _choose(console: Console, question: str, options: tuple[str, ...]) -> int | None:
    console.print(question, style="bold")
    for index, label in enumerate(options, start=1):
        console.print(f"  {index:2}  {label}")
    console.print("   0  Exit", style="dim")
    choices = {str(index): index - 1 for index in range(1, len(options) + 1)}
    while True:
        answer = console.input("Choice: ").strip()
        if answer == "0":
            return None
        if answer in choices:
            return choices[answer]
        console.print("Enter one of the listed numbers.", style="yellow")


def _website_probe(console: Console, app: AppCheck) -> dict[str, object]:
    console.print()
    console.print(f"Website diagnostics  HTTPS HEAD https://{app.host}/", style="bold")
    console.print("This is a separate check of the public web endpoint.", style="dim")
    request = {"domain": app.host, "scheme": "https", "method": "HEAD"}
    try:
        (probe,) = asyncio.run(
            scan((Domain(app.host, "app-website", "silentdrop"),), concurrency=1)
        )
    except (OSError, ValueError):
        message = "Could not start the HTTPS probe. Run silentdrop doctor for setup details."
        console.print(message, style="yellow")
        return {**request, "error": message}

    console.print(
        f"DNS {probe.dns.value}  /  TCP {probe.connection.value}  /  TLS {probe.tls.value}"
    )
    status = probe.http_status if probe.http_status is not None else "unavailable"
    console.print(f"HTTP {status}  /  {probe.latency_ms:.0f} ms  /  {probe.classification.value}")
    if probe.error:
        console.print(Text(probe.error, style="yellow"))
    return {**request, **asdict(probe)}


def run_app_check(console: Console, mode: str | None) -> None:
    """Record an app action observed by the user."""
    console.print("SilentDrop  /  App check", style="bold cyan")
    if mode is None:
        choice = _choose(
            console,
            "Choose a mode",
            ("Regular mode  (plain-language result)", "Nerd mode  (HTTPS diagnostics)"),
        )
        if choice is None:
            return
        mode = MODES[choice]

    choice = _choose(console, "Choose an app", tuple(app.name for app in _APPS))
    if choice is None:
        return
    app = _APPS[choice]

    console.print()
    console.print(f"{app.name}  /  {app.action}", style="bold")
    console.print(app.instructions)
    choice = _choose(console, "What happened in the app?", tuple(_OUTCOMES.values()))
    if choice is None:
        return
    observed_at = utc_timestamp()
    outcome = tuple(_OUTCOMES)[choice]
    label = console.input("Network label (optional, e.g. University Wi-Fi): ").strip()
    network = "".join(char for char in label if char.isprintable())[:80] or None

    console.print(Text.assemble((f"{app.name}  /  {app.action}  ", "bold"), _OUTCOMES[outcome]))
    console.print(
        "Result recorded from your app test. Cause undetermined."
        if outcome == "failed"
        else "Result recorded from your app test.",
        style="dim",
    )
    probe = _website_probe(console, app) if mode == "nerd" else None

    unique_stamp = observed_at.translate(str.maketrans("", "", "-:."))
    path = Path("reports") / "apps" / f"app-check-{unique_stamp}.json"
    report = {
        "schema_version": 1,
        "report_type": "app_check",
        "application_version": __version__,
        "observed_at": observed_at,
        "network_label": network,
        "mode": mode,
        "app": app.name,
        "action": app.action,
        "outcome": outcome,
        "source": "user_observation",
        "website_probe": probe,
    }
    with atomic_report(path) as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    console.print(Text.assemble(("Saved  ", "dim"), str(path)))
