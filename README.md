# SilentDrop

![SilentDrop wordmark with a mint descending signal](assets/silentdrop-logo.webp)

*Not every connection dies loudly.*

[![CI](https://github.com/akram-jemal/silentdrop/actions/workflows/ci.yml/badge.svg)](https://github.com/akram-jemal/silentdrop/actions/workflows/ci.yml)
[![MIT license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

SilentDrop checks whether public parts of popular services are reachable from
your network. The terminal app lets you search for one service or check the
entire catalog of 30 social, messaging, video, music, and gaming services.

**Regular mode** explains the result in plain language. **Nerd mode** shows the
endpoint, HTTP status, timing, and other evidence behind the result. An
optional browser check can verify whether a curated public clip actually plays.

## Quick start

Use Python 3.10 or later. Clone the repository or extract the source ZIP, then
open a terminal in the folder containing `pyproject.toml`.
[Download main](https://github.com/akram-jemal/silentdrop/archive/refs/heads/main.zip) · [Releases](https://github.com/akram-jemal/silentdrop/releases)

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
silentdrop
```

On Windows, create the environment with `py -m venv .venv` and activate it in
PowerShell with `.\.venv\Scripts\Activate.ps1`. You can also invoke the CLI with
`python -m silentdrop`.

Select **Check one** to search the catalog or **Check all** to run through it.
Use **View** to switch between Regular and Nerd mode.

## Command-line use

| Task | Command |
| --- | --- |
| List services and their command names | `silentdrop list` |
| Check YouTube with technical details | `silentdrop check youtube --mode nerd` |
| Check all 30 services | `silentdrop check all --mode regular` |
| Check one service with color disabled | `silentdrop --no-color check discord` |
| Inspect local TLS trust and proxy settings | `silentdrop doctor` |
| Run the Doctor HTTPS probe | `silentdrop doctor --probe` |

## Optional playback checks

Install the playback extra and Chromium in your active environment to enable
browser checks of curated public YouTube and TikTok clips.

```sh
python -m pip install '.[playback]'
python -m playwright install chromium
```

A result identifies the observed public page or clip. Private messages,
account actions, subscriptions, and native app behavior are outside the test
scope. Run checks where direct HTTPS diagnostics are permitted.
[Operating guide](docs/usage.md)

## Documentation

- Interactive controls, result interpretation, and troubleshooting. [Operating guide](docs/usage.md)
- Development setup and checks. [Contributing](CONTRIBUTING.md)
- Changes and earlier release notes. [Changelog](CHANGELOG.md)
- The earlier website scanner and report tools. [v1.1.0 documentation](https://github.com/akram-jemal/silentdrop/tree/v1.1.0#readme)

## License

SilentDrop uses the MIT license. [License](LICENSE)
