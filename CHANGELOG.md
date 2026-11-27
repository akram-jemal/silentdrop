# Changelog

## Unreleased

- Add an interactive terminal app for automatic public checks of 30 social,
  messaging, video, music, and gaming services.
- Search for a service or check the whole catalog, with plain-language results
  in Regular mode and underlying evidence in Nerd mode.
- Add optional Chromium playback checks of curated public clips on YouTube
  and TikTok.
- Add scriptable `silentdrop list` and `silentdrop check` commands. Keep
  `silentdrop doctor` for local TLS and proxy diagnostics.
- Retire the guided action workflow, the broad website scanner, and the
  previous report and comparison commands.

## 1.1.0

- Add `silentdrop doctor` to inspect local Python, TLS trust and proxy settings offline.
- Add `silentdrop doctor --probe` to verify direct HTTPS connectivity to one bundled hostname.
- Add the SilentDrop wordmark and a terminal layout that adapts to narrow windows.
- Explain repeated certificate verification failures and HTTP probe denials in scan output.
- Add operating, report format and contribution guides, along with a real macOS terminal demo.
- Publish release notes, wheels and source distributions through GitHub Releases.

## 1.0.0

- Add the installable `silentdrop` CLI and the `python -m silentdrop` entry point.
- Bundle 129 reviewed hostnames with category filters and upstream attribution.
- Record system DNS, TCP connection, verified TLS and HTTPS status with bounded asynchronous probes.
- Show live progress and category summaries in the terminal and export local JSON or CSV reports.
- Compare accessibility classifications offline, including hosts found in only one report.
- Add local-network tests, wheel installation checks and CI for Python 3.10 and 3.12.
