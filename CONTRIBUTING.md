# Contributing to SilentDrop

Use a Python 3.10 or newer virtual environment and install the development
dependencies from the checkout. [Installation steps](README.md#quick-start)

```sh
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
python -m pytest -q -W error
python -m build
```

Use loopback endpoints and fixtures to exercise network and browser behavior
in tests. Tests should run without a live service or a browser download.
[CI workflow](.github/workflows/ci.yml)

## Code layout

| File | Responsibility |
| --- | --- |
| `silentdrop/cli.py` and `silentdrop/terminal.py` | Command-line entry points and the interactive terminal app. |
| `silentdrop/catalog.py` and `silentdrop/results.py` | Reviewed service entries and result types. |
| `silentdrop/webcheck.py` and `silentdrop/playback.py` | Public page requests and optional browser checks. |
| `silentdrop/runner.py` | Schedule checks and combine the available evidence for each service. |
| `silentdrop/doctor.py` | Inspect local TLS trust and proxy configuration. |

## Preparing a change

Describe what changes for the user, how to reproduce the original behavior,
and which checks you ran. Update the operating guide whenever command
syntax, result wording, or the scope of a check changes.

For a catalog change, document the service, the public endpoint or clip, and
the evidence that supports the expected result. Keep test inputs to approved
public services and redirects. Use an unauthenticated public clip for playback
and keep a separate public page signal for when playback cannot be verified.

Include the command, application version, and relevant result when reporting
a bug. Remove private paths and shell prompts before attaching screenshots or
logs. [Issues](https://github.com/akram-jemal/silentdrop/issues)

## Releases

For a release, update `silentdrop/__init__.py` and add a matching version
heading to `CHANGELOG.md`. A pushed version tag triggers CI. After the checks
pass, the workflow uses that changelog section as release notes and publishes
the release with a wheel and source distribution.
[Release workflow](.github/workflows/ci.yml)
