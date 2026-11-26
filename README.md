# SilentDrop

*Not every connection dies loudly.*

[![CI](https://github.com/akram-jemal/silentdrop/actions/workflows/ci.yml/badge.svg)](https://github.com/akram-jemal/silentdrop/actions/workflows/ci.yml)
[![MIT code license](https://img.shields.io/badge/code-MIT-green)](LICENSE)

SilentDrop checks how a network reaches a curated set of websites. It records
DNS, connection, TLS and HTTP outcomes so you can see where an HTTPS request
stopped. Scan the whole list or a single category, then compare local reports
from two networks.

## Terminal demo

Synthetic results for reserved `.example` hostnames, shown as an excerpt.

```text
+-------------------+
|    SILENTDROP     |
+-------------------+
SilentDrop v1.0.0
Not every connection dies loudly.
Dataset synthetic-1 | Hosts 3 | Gaming

| Domain          | Category | Classification     | HTTP | Latency |
|-----------------+----------+--------------------+------+---------|
| arena.example   | gaming   | ACCESSIBLE         |  200 |   48 ms |
| matches.example | gaming   | CONNECTION_TIMEOUT |    - | 8002 ms |
| scores.example  | gaming   | INCONCLUSIVE       |  429 |   81 ms |

| Category | Tested | Accessible | Failed | Inconclusive |
|----------+--------+------------+--------+--------------|
| gaming   |      3 |          1 |      1 |            1 |

Checks completed 3 | Elapsed 8.0 s
Report reports/lab.json
```

## Install

Python 3.10 or later is required. SilentDrop runs as a regular user.

```sh
git clone https://github.com/akram-jemal/silentdrop.git
cd silentdrop
python -m venv .venv
source .venv/bin/activate
python -m pip install .
```

In Windows PowerShell, activate the environment with `.\.venv\Scripts\Activate.ps1`.
Use `python -m silentdrop` if you prefer the Python entry point.

## Quick start

```sh
silentdrop --help
silentdrop --version
silentdrop categories
silentdrop dataset info
silentdrop scan
```

The default scan checks every bundled hostname and saves a timestamped JSON
report in `reports/`. The category and dataset commands work offline.

```sh
silentdrop scan --category gaming
silentdrop scan --category social
silentdrop scan --failed-only
silentdrop scan --output reports/result.json
silentdrop scan --format csv
silentdrop scan --category education --concurrency 4 --timeout 5
silentdrop --no-color scan --category gaming
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

Run the same category or dataset on each authorized network.

```sh
silentdrop scan --output reports/home.json
silentdrop scan --output reports/lab.json
silentdrop compare reports/home.json reports/lab.json
```

Comparison runs offline. It matches hostnames, shows classification changes
and identifies hosts present in only one report. You can mix JSON and CSV. Use
the bundled synthetic examples to try the command without sending any probes.

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
`HEAD /` request over HTTPS to each selected hostname. It measures through
the first response headers. Redirect destinations, page bodies, and embedded
resources are outside the scope of the probe. A rate-limit status is recorded
as received.

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

The summary groups results into accessible, failed and inconclusive requests.
An HTTP restriction counts as failed. Suspected filtering counts as inconclusive.

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

Use SilentDrop only on networks and endpoints you are authorized to test and
where direct HTTPS diagnostics are permitted. The scan records observations
for the requesting machine at a specific time. A 403 can come from a site or
CDN policy. DNS errors, timeouts and TLS errors can also result from resolver
configuration, outages or certificate problems. A 2xx or 3xx result covers
the responding HTTPS endpoint. Mobile apps may use other hosts and protocols.

The shortlist covers mainstream service endpoints. The content hosted by a
service can change. Reports stay local and contain hostnames and observations
required for analysis, without IP addresses, request credentials or cookies.

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

## Author

[Akram Jemal on GitHub](https://github.com/akram-jemal)
