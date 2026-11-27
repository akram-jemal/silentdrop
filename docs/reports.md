# Report reference

## App check records

`silentdrop app` saves a separate JSON record under `reports/apps/`. It
contains the app, the action, the outcome you entered, the UTC time, and an
optional network label. Records have `report_type` set to `app_check` and
`source` set to `user_observation`. In Nerd mode, `website_probe` contains
the separate web check. In Regular mode that field is `null`.

The existing `silentdrop compare` command takes the website scan reports
described below.

## Website scan reports

SilentDrop writes reports to local files. Use `--output` to choose the path
and file extension. Each successful scan writes one report for the selected
dataset and category, even when the terminal displays only failed probes.

```sh
silentdrop scan --category messaging --output reports/messaging.json
silentdrop scan --category messaging --output reports/messaging.csv
```

## JSON schema version 1

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer format version. The current value is `1`. |
| `application_version` | SilentDrop version that generated the report. |
| `dataset_version` | Identifier of the bundled hostname list used for the scan. |
| `scan_timestamp` | UTC scan start in ISO 8601 format. |
| `summary` | Overall `total`, `accessible`, `failed` and `inconclusive` counts. |
| `categories` | The same counts grouped by category key. |
| `limitations` | Statements about the scope of the observation. |
| `results` | One record per probed hostname, in dataset order. |

Each result has a `domain`, `category`, and `classification`. The `dns`,
`connection` and `tls` fields use `ok`, `failed` or `unknown`. An
`unknown` stage has no recorded outcome. The `http_status` is an integer
when available and `null` otherwise. The `latency_ms` measures elapsed
probe time in milliseconds, including DNS, connection and TLS when those
stages are reached. The `timestamp` records probe start in UTC. The `error`
contains a diagnostic description or `null`.

The report records hostnames, timing and diagnostic observations. Source
network labels, local IP addresses, credentials, cookies and response bodies
are outside the report schema. Use filenames to distinguish networks.
[Full synthetic report](../examples/synthetic-lab.json)

## CSV layout

CSV holds one row per result. Scan metadata and overall counts are repeated
on every row. The `category_total`, `category_accessible`,
`category_failed` and `category_inconclusive` columns describe the row's
category. An empty cell represents a missing HTTP status or diagnostic.

## Compare two scans

Use the same category, dataset version and probe settings on each network.
In this sequence, run the first scan before switching networks and run the
second scan after switching.

```sh
silentdrop scan --category messaging --output reports/baseline.json
silentdrop scan --category messaging --output reports/current.csv
silentdrop compare reports/baseline.json reports/current.csv
```

Comparison matches reports by hostname and shows classification changes and
hosts present in only one report. Dataset versions are displayed for context.
HTTP status and latency differences are visible in the source reports.

To try comparison offline with files from the repository, run:

```sh
silentdrop compare examples/synthetic-home.json examples/synthetic-lab.json
```
