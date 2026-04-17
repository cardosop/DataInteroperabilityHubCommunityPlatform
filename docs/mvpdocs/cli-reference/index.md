# CLI Reference

Complete reference for the **datahub** CLI (MVP release).

## Installation

```bash
pip install datahub-cli           # From PyPI
cd cli && pip install -e .        # From source (development)
```

## Authentication

```bash
# Interactive login (email/password)
datahub login

# API key authentication
datahub config set api_key YOUR_API_KEY

# Verify connectivity
datahub health check

# Logout
datahub logout
```

## Quick Start

```bash
# Upload a file and create an asset
datahub files upload /path/to/data.csv
datahub assets create --name "Sales Data" --key "sales-data"

# Create and validate a contract
datahub contracts create --file contract.yaml --spec-type ODPS
datahub contracts validate <contract-id>

# Monitor a background job
datahub jobs watch <job-id>
```

## Command Groups

| Group | Description |
|-------|-------------|
| [`datahub assets`](assets.md) | Manage data assets (datasets, files, schemas) |
| [`datahub contracts`](contracts.md) | Manage and validate data contracts (ODCS/SLA) |
| [`datahub lineage`](lineage.md) | Explore data lineage and dependency graphs |
| [`datahub files`](files.md) | Upload, download and manage files attached to assets |
| [`datahub jobs`](jobs.md) | Monitor and control background jobs and tasks |
| [`datahub config`](config.md) | Read and write CLI and tenant configuration |
| [`datahub dq`](dq.md) | Run data-quality checks and review results |
| [`datahub compliance`](compliance.md) | Scan assets for compliance violations and review results |
| [`datahub governance`](governance.md) | Manage governance policies, retention rules and consent |
| [`datahub marketplace`](marketplace.md) | Browse listings, place orders and manage entitlements |
| [`datahub webhooks`](webhooks.md) | Register, test and manage webhook endpoints |
| [`datahub audit`](audit.md) | Query and export the audit log |
| [`datahub health`](health.md) | Check platform health and run diagnostics |
| [`datahub billing`](billing.md) | View usage, invoices, quotas and plan details |
| [`datahub tenants`](tenants.md) | Manage tenants, switch context and list members |
| [`datahub gdpr`](gdpr.md) | GDPR data-subject requests: export, erase, consent |
| [`datahub search`](search.md) | Full-text and faceted search across the catalogue |
| [`datahub semantic`](semantic.md) | Semantic layer: resolve terms, SPARQL queries, browse |

## Global Options

These flags are available on every command:

| Flag | Description |
|------|-------------|
| `--format json\|table\|yaml` | Output format (default: table) |
| `--tenant <slug>` | Tenant context override |
| `-v, --verbose` | Verbose output |
| `--no-color` | Disable coloured output |
| `--timeout <seconds>` | Request timeout (default: 30) |
| `--version` | Show CLI version and exit |
| `--help` | Show help and exit |

## Post-MVP (Gated) Features

The following API prefixes are gated in MVP mode and not yet exposed
through the CLI: `ai`, `baas`, `integrations`, `mesh`, `ml`, `scheduled-exports`, `scheduled-ingestions`, `social`, `transformation`, `virtualization`.

These will be enabled in a future release. Attempting to reach a gated
endpoint returns error code `MVP_FEATURE_GATED`.
