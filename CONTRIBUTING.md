# Contributing to SilentDrop

Use a Python 3.10 or newer virtual environment and install the development
dependencies from the checkout. [Installation steps](README.md#quick-start)

```sh
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
python -m pytest -q -W error
python -m build
```

The test suite uses loopback HTTPS and mocked DNS errors. For changes to
networking behavior, use controlled endpoints in tests. CI runs lint,
formatting, tests and a wheel installation check on Ubuntu with Python 3.10
and 3.12. [CI workflow](.github/workflows/ci.yml)

## Code layout

| File | Responsibility |
| --- | --- |
| `silentdrop/cli.py` | Parse commands and options, run scans and save reports. |
| `silentdrop/dataset.py` and `silentdrop/data/` | Load and validate the packaged hostname list and its metadata. |
| `silentdrop/scanner.py` | Schedule bounded HTTPS probes and record observed connection stages. |
| `silentdrop/classifier.py` | Translate probe outcomes into classifications. |
| `silentdrop/reporter.py` and `silentdrop/comparison.py` | Serialize local reports and compare classifications offline. |
| `silentdrop/ui.py` | Render progress, tables and diagnostics with Rich. |

## Preparing a change

Describe what changes for the user, how to reproduce the original behavior
and which checks you ran. Update the relevant guide when command behavior,
classifications or report fields change.

For dataset changes, record the source and reason for each proposed hostname.
For changes to examples, use reserved `.example` hostnames and label synthetic
results clearly. [Dataset maintenance](silentdrop/data/ATTRIBUTION.md)

Include the command, application version, dataset version and relevant result
when reporting a bug. Remove private paths and shell prompts before attaching
screenshots or logs. [Issues](https://github.com/akram-jemal/silentdrop/issues)
