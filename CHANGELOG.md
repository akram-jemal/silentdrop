# Changelog

## Unreleased

- Add the SilentDrop wordmark and a terminal layout that adapts to narrow windows.
- Explain repeated certificate verification failures and HTTP probe denials in scan output.
- Add operating, report format and contribution guides.

## 1.0.0

- Add the installable `silentdrop` CLI and the `python -m silentdrop` entry point.
- Bundle 129 reviewed hostnames with category filters and upstream attribution.
- Record system DNS, TCP connection, verified TLS and HTTPS status with bounded asynchronous probes.
- Show live progress and category summaries in the terminal and export local JSON or CSV reports.
- Compare accessibility classifications offline, including hosts found in only one report.
- Add local-network tests, wheel installation checks and CI for Python 3.10 and 3.12.
