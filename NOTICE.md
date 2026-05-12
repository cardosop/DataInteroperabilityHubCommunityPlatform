# NOTICE — Third-Party Attributions (Phase 275.E.3n)

Meshant uses the following Apache 2.0 and MIT licensed third-party
libraries. This file satisfies Apache 2.0 §4(d) requirements.

## Phase 275 — Warehouse Connectivity SDKs

| Library | License | Version |
|---------|---------|---------|
| `snowflake-connector-python` | Apache 2.0 | >=3.0 |
| `google-cloud-bigquery` | Apache 2.0 | >=3.0 |
| `databricks-sql-connector` | Apache 2.0 | >=3.0,<4.0 |
| `pyathena` | MIT | >=3.0,<4.0 |
| `dlt` (data load tool) | Apache 2.0 | >=1.0,<2.0 |
| `delta-sharing` | Apache 2.0 | >=1.0,<2.0 |

## Existing Dependencies

Full dependency list with licenses is maintained in:
- `requirements.txt` (Python)
- `package.json` (Node.js / frontend)

For complete license information, run:
```bash
pip-licenses --format=markdown
npx license-checker --summary
```
