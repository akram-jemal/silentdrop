# Operating guide

SilentDrop measures whether reviewed public hostnames respond to direct HTTPS
probes from the machine running the scan. The CLI uses the operating system's
DNS resolver and Python's default TLS trust configuration. Each probe sends
`HEAD /` and records the outcome through the first response headers, leaving
redirect destinations and page bodies outside the measurement.

Install SilentDrop and run a first scan from the [quick start](../README.md#quick-start).

## Commands

| Command | Behavior |
| --- | --- |
| `silentdrop scan` | Probes all bundled hosts and saves one local report. |
| `silentdrop categories` | Lists category names and host counts offline. |
| `silentdrop dataset info` | Displays the dataset version, source and license offline. |
| `silentdrop compare BEFORE AFTER` | Compares two saved JSON or CSV reports offline. |
| `silentdrop --version` | Prints the application version. |
| `silentdrop --help` | Lists commands and global options. |

## Scan options

| Option | Effect | Default |
| --- | --- | --- |
| `--category NAME` | Scan one category from `silentdrop categories`. | All categories |
| `--failed-only` | Show only failed probes in the terminal table. The summary and report include every checked host. | Show all results |
| `--output PATH` | Save to a path ending in `.json` or `.csv`. A successful write replaces an existing file at that path. | Timestamped file under `reports/` relative to the working directory |
| `--format {json,csv}` | Choose the export format. When used with `--output`, it must match the extension. | Infer from the path, otherwise JSON |
| `--concurrency N` | Set the maximum simultaneous probes, from 1 to 32. | 8 |
| `--timeout SECONDS` | Set the per-probe timeout, from 0.1 to 120 seconds. | 8 seconds |

Pass `--no-color` before the subcommand to disable color. Press **Ctrl+C** to
cancel a scan in progress.

```sh
silentdrop --no-color scan --category messaging --concurrency 4 --timeout 10
```

## Interpret a result

| Report classification | Summary group | What SilentDrop observed |
| --- | --- | --- |
| `ACCESSIBLE` | Accessible | The original hostname returned a 2xx or 3xx response. |
| `DNS_FAILURE` | Failed | The system resolver could not resolve the hostname. |
| `CONNECTION_TIMEOUT` | Failed | The per-probe deadline elapsed before HTTP headers arrived. The report can show which earlier stages succeeded. |
| `CONNECTION_REFUSED` | Failed | The connection attempt was refused. |
| `TLS_ERROR` | Failed | Certificate verification or TLS negotiation failed. The report distinguishes the two. |
| `HTTP_RESTRICTED` | Failed | HTTP 401, 403, 407 or 511 indicated denial or an authentication requirement at the HTTP stage. |
| `SUSPECTED_FILTERING` | Inconclusive | HTTP 451 reported a legal restriction. The source of that restriction is unverified. |
| `INCONCLUSIVE` | Inconclusive | An unexpected status such as 429 or 503, or an ambiguous transport or protocol error. |

An accessible result applies to the probed hostname at the time of the scan.
A redirect may point to a separate endpoint. A failed result describes that
probe, and firewall policy requires separate evidence.

## Troubleshooting

**The website opens in a browser but the probe returns 403.** The endpoint
answered over HTTPS and denied the HEAD request. A browser can make a different
request and may already have a signed-in session. Use the HTTP status and the
report's diagnostic to describe the outcome.

**Certificate verification fails across several unrelated sites.** Check the
trust configuration for the Python installation running SilentDrop. With
python.org builds on macOS, run `Install Certificates.command` from the
corresponding Python folder in Applications. On a managed network, ask IT which
CA that Python installation should trust.

**The browser works through an organization proxy.** SilentDrop uses direct
connections. Browser proxy settings and HTTP proxy environment variables are
outside its connection configuration. Use it where direct HTTPS diagnostics
are permitted.

**A probe keeps timing out.** Open the report and check the DNS, connection and
TLS fields before considering the HTTP stage. For repeat measurements, use the
same timeout and dataset. A repeatable timeout is an observation about the
probe path. Several causes, including a remote outage, can produce it.

**A report is missing or cannot be read.** Check the path printed by the scan
and the current working directory. Use a writable destination with a supported
extension. If comparison rejects a report, check that it is a complete report
with a supported schema version. [Report reference](reports.md)

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | The command completed. A completed scan may contain failed probes. |
| `1` | A file, dataset, or other handled command error occurred. |
| `2` | Command-line arguments were invalid. |
| `130` | The command was interrupted. |

For scripts, use the exit code to check command completion and use
`summary` or `results` in the saved JSON to evaluate probe outcomes.
