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
| [`datahub baas`](baas.md) | BaaS: API keys, usage tracking, billing reports |
| [`datahub mesh`](mesh.md) | Data mesh: domains, topology, policies, compliance |
| [`datahub ml`](ml.md) | ML registry: models, inference, training, serving, A/B tests |
| [`datahub scheduled-export`](scheduled_export.md) | Recurring data exports to external destinations |
| [`datahub scheduled-ingestion`](scheduled_ingestion.md) | Recurring data ingestion from external sources |
| [`datahub transformation`](transformation.md) | Transformation pipelines and wrangling sessions |
| [`datahub virtualization`](virtualization.md) | Virtual datasets, query execution, topology |
| [`datahub phase232-programme`](phase232_programme.md) | Phase 232 compliance programme catalogue and probes |

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

The following API prefixes are gated in MVP mode and CLI access may
return `MVP_FEATURE_GATED` depending on the tenant's plan and feature
flags: `ai`, `integrations`, `social`.

Commands for these prefixes exist in the CLI and are documented above,
but the backend endpoints may reject requests when the corresponding
feature flag is disabled for the tenant.
