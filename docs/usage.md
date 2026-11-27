# Operating guide

SilentDrop checks public service pages and, when available, curated public
playback samples. Checks run automatically and display results in the
terminal. Install SilentDrop first. [Quick start](../README.md#quick-start)

## Interactive checks

In a terminal, run `silentdrop` with no arguments.

1. Select **Check one** or press **Ctrl+F**. Type a service name to narrow
   the list, use **Down** to enter the results, and press **Enter** on a
   service to check it or open its existing result.
2. Select **Check all** or press **F5** to check the whole catalog with live
   progress.
3. Use **View** or **F2** to switch between Regular and Nerd mode. Press
   **Esc** to cancel an active check or **Q** to quit outside the search box.

Regular mode gives a plain-language result and describes the evidence that
supported it. Nerd mode shows the details behind that same check.

## Commands

| Command | Behavior |
| --- | --- |
| `silentdrop list` | List the 30 services and their slugs. |
| `silentdrop check youtube` | Check YouTube. |
| `silentdrop check youtube --mode nerd` | Show technical evidence for the same check. |
| `silentdrop check all --mode regular` | Check the full catalog with plain-language results. |
| `silentdrop doctor` | Inspect local Python, TLS trust, and detected proxy settings offline. |
| `silentdrop doctor --probe` | Send one verified HTTPS HEAD request to `www.iana.org`. |
| `silentdrop --version` | Print the application version. |

Regular is the default mode. Use an explicit command when redirecting output
or running in a script. For colorless output, put `--no-color` before the
command. Pass `--help` to see available options.

```sh
silentdrop --no-color check discord --mode nerd
```

The `check` command returns exit code `0` when the check completes, even when
the result is unverified. Invalid arguments return `2`, and an interruption
returns `130`. Doctor returns `1` if local TLS trust is unavailable in an offline
check or the requested probe cannot receive a response over verified TLS.

## Read the result

An HTTPS check sends an ordinary GET request to a curated public service
endpoint with certificate verification. Within an eight-second deadline,
it reads up to 64 KiB of HTML in memory and follows up to three HTTPS
redirects within the service's approved hostnames. Results appear in the
terminal and stay in the session.

Use these distinctions when interpreting a result.

| Result | Meaning |
| --- | --- |
| Page loaded | The endpoint returned a successful HTTP status and recognizable service content. |
| Video played | A curated public clip's playback advanced during the check. |
| Network block page detected | The response contained recognizable evidence of a network intermediary's restriction. |
| Couldn't verify | A sign-in page, an off-catalog redirect, or another problem left the result uncertain. |

A web result describes the specific page or clip. Private messages, account
actions, subscriptions, and native app behavior are outside the scope.
A generic HTTP 403 or 451 leaves the source of a restriction uncertain.
Service login requirements and bot protection can also affect the result.

## Enable playback checks

From the SilentDrop checkout in your active virtual environment, install the
optional dependency and Chromium.

```sh
python -m pip install '.[playback]'
python -m playwright install chromium
```

With that setup, the YouTube and TikTok checks can try their curated public
clips in a fresh browser context. The stronger playback result requires
observed media progress. If it cannot verify playback, SilentDrop reports
playback as unverified and keeps the public page evidence.

## Troubleshooting

**TLS trust or proxy configuration looks wrong.** Run `silentdrop doctor`.
It checks the Python runtime and OpenSSL backend, CA availability, CA
overrides, and whether Python detects proxy configuration. The checks run
offline and keep environment variable values private. On macOS with
python.org builds, run `Install Certificates.command` from the corresponding
Python folder in Applications. On a managed network, ask IT which CA that
Python installation should trust.

**The browser works through an organization proxy.** SilentDrop's direct
HTTPS checks can reach a different result from a browser using that proxy.
Use SilentDrop where direct HTTPS diagnostics are permitted.

**You need evidence that TLS works.** Run `silentdrop doctor --probe` where
permitted. The 8-second check sends one verified HTTPS HEAD request to
`www.iana.org`. A verified HTTPS response, including HTTP 403 or 503, means
the TLS handshake worked for that endpoint.

**A clip stayed unverified.** Check that the playback extra and Chromium
are installed in the environment running SilentDrop. A consent screen,
regional availability, or an unavailable clip can also prevent verification.

## Earlier workflow

The earlier site scanner and report comparison commands are available in
the v1.1.0 release. [Earlier operating guide](https://github.com/akram-jemal/silentdrop/blob/v1.1.0/docs/usage.md) · [Earlier report reference](https://github.com/akram-jemal/silentdrop/blob/v1.1.0/docs/reports.md)
