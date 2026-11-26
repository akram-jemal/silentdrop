# SilentDrop

![SilentDrop wordmark with a mint descending signal](assets/silentdrop-logo.webp)

*Not every connection dies loudly.*

[![CI](https://github.com/akram-jemal/silentdrop/actions/workflows/ci.yml/badge.svg)](https://github.com/akram-jemal/silentdrop/actions/workflows/ci.yml)
[![MIT code license](https://img.shields.io/badge/code-MIT-green)](LICENSE)

SilentDrop is a command-line tool for diagnosing website reachability. It shows
how far each HTTPS probe got through DNS, connection, TLS and HTTP. Scan a
curated list by category, save the results as JSON or CSV, and compare reports
from different networks offline.

## Terminal demo

Sample scan with synthetic results for reserved `.example` hostnames.

```text
-----    SilentDrop  v1.0.0
----     Not every connection dies loudly.
--       Gaming  /  3 hosts
.        Dataset 2026-11-26.1

Scan complete  3 tested / 8.0 s
1 accessible   1 failed   1 inconclusive
Report  reports/lab.json

Domain results

  Domain                     Result                 HTTP   Latency
 ──────────────────────────────────────────────────────────────────
  arena.example              Accessible              200     48 ms
  matches.example            Connection timeout        -   8002 ms
  scores.example             Inconclusive            429     81 ms

The scan cannot establish firewall rules or mobile app
accessibility.
```

## Install

Requires Python 3.10 or later. You can clone the repository or extract the
[source ZIP](https://github.com/akram-jemal/silentdrop/archive/refs/heads/main.zip).
Run the installation commands from the folder containing `pyproject.toml`.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

On Windows, use `py -m venv .venv` and activate it in PowerShell with
`.\.venv\Scripts\Activate.ps1`. Both `silentdrop` and `python -m silentdrop`
use the same CLI.

## Quick start

```sh
silentdrop categories
silentdrop scan --category gaming
```

Run `silentdrop scan` to check every bundled hostname. Each scan saves a
timestamped JSON report in `reports/` by default. `silentdrop categories` and
`silentdrop dataset info` work offline.

```sh
silentdrop scan --category social
silentdrop scan --failed-only
silentdrop scan --output reports/result.json
silentdrop scan --format csv
silentdrop scan --category education --concurrency 4 --timeout 5
silentdrop --no-color scan --category gaming
silentdrop scan --help
```

- `--failed-only` filters the terminal results table. The summary and report
  count every checked host.
- `--timeout` applies to an individual probe, from 0.1 to 120 seconds. The
  default is 8 seconds. `--concurrency` controls simultaneous probes, from
  1 to 32, and defaults to 8.
- `--output` accepts a `.json` or `.csv` path and determines the format when
  `--format` is omitted. An existing file at the chosen path is replaced on a
  successful write. This repository ignores locally generated report files.
- Ctrl+C cancels the scan. Exit status 0 means a command completed. Argument
  errors return 2, file or dataset errors return 1, and interruption returns 130.

## Compare reports

Use the same dataset and category on each authorized network. Save the first
report before switching networks, then save the second under a different name.

```sh
silentdrop scan --output reports/home.json
silentdrop scan --output reports/lab.json
silentdrop compare reports/home.json reports/lab.json
```

Comparison runs offline and accepts JSON or CSV. It matches hostnames and
shows changes in classification or coverage. Try it with the bundled reports.

```sh
silentdrop compare examples/synthetic-home.json examples/synthetic-lab.json
```

Reports include the application and dataset versions, UTC timestamps, overall
and category counts, and per-host diagnostics. CSV repeats scan metadata and
category counts on each row. This result is from the synthetic lab report.
[Full JSON example](examples/synthetic-lab.json)

```json
{
  "domain": "scores.example",
  "category": "gaming",
  "dns": "ok",
  "connection": "ok",
  "tls": "ok",
  "http_status": 429,
  "latency_ms": 81.02,
  "error": "The endpoint reported rate limiting (HTTP 429).",
  "timestamp": "2026-11-26T12:30:00.000000Z",
  "classification": "INCONCLUSIVE"
}
```

## How it works

SilentDrop uses the OS resolver, verifies TLS certificates, and sends a direct
`HEAD /` request over HTTPS to each selected hostname. The probe ends at the
first response headers. Its result applies to that hostname at the time of
the scan. Redirect destinations, page content and mobile apps are outside
the scope of the probe.

`dataset.py` loads and filters packaged hostnames. `scanner.py` runs bounded
workers through a shared aiohttp session. `classifier.py` interprets the
observed stages and response status. `reporter.py` writes local reports,
`comparison.py` reads their classifications, and `cli.py` and `ui.py`
handle arguments and terminal output.

| Classification | What the probe observed |
| --- | --- |
| `ACCESSIBLE` | HTTP 2xx or 3xx from the original host. |
| `DNS_FAILURE` | The system resolver failed to resolve the hostname. |
| `CONNECTION_TIMEOUT` | The request timed out before HTTP headers arrived. |
| `CONNECTION_REFUSED` | The connection was refused. |
| `TLS_ERROR` | Certificate verification or TLS negotiation failed. |
| `HTTP_RESTRICTED` | HTTP 401, 403, 407 or 511 indicated a denied or authentication-gated request. |
| `SUSPECTED_FILTERING` | HTTP 451 explicitly reported a legal restriction. Its source is unverified. |
| `INCONCLUSIVE` | HTTP 429, an unexpected status, a server error or an ambiguous transport error. |

A restricted HTTP response counts as a failed probe. Suspected filtering counts
as inconclusive.

## Troubleshooting

**A site opens in the browser but returns HTTP 403.** The HTTPS connection
worked and the endpoint denied the probe. Browsers send a different request
and may already have a signed-in session. A 403 alone cannot identify a
network block.

**Several sites fail certificate verification.** Check the certificate store
for the Python installation running SilentDrop. If you installed Python from
python.org on macOS, run `Install Certificates.command` from its folder in
Applications. On a managed network, ask IT which certificate authority Python
should trust.

## Dataset and license

The first dataset contains 129 public service hostnames across ten categories.
Citizen Lab supplies 83 of the hostnames. The rest fill coverage gaps for
current services. The CSV retains the source and original category code for
each adapted row. Review proposed hostname changes individually using the
maintenance steps in the attribution file. [Dataset attribution and maintenance](silentdrop/data/ATTRIBUTION.md)

The application code uses the MIT license. [MIT license](LICENSE)

The bundled data uses Creative Commons Attribution-NonCommercial-ShareAlike 4.0
International. [Dataset license terms](https://creativecommons.org/licenses/by-nc-sa/4.0/)

## Limitations and responsible use

Use SilentDrop where you are authorized to send direct HTTPS probes. DNS
errors, timeouts and TLS errors can have several causes, including resolver
configuration, outages and certificate problems. Reports stay local and
include the tested hostnames, timestamps and probe outcomes.

## Contributing

Install the development extras and run the same checks as CI. Network tests
use mocked resolver errors and loopback HTTPS with temporary certificates.

```sh
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
python -m pytest -q -W error
python -m build
```

For dataset changes, include the hostname, reason for inclusion and its
source in the proposed diff. [Open an issue](https://github.com/akram-jemal/silentdrop/issues)
