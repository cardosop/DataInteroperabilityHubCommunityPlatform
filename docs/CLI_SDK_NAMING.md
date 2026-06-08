# CLI / SDK Naming Conventions

**Status**: Authoritative — CLI and SDK naming MUST follow these conventions.
**Phase**: 278.AA.16
**Updated**: 2026-05-14

## Overview

This document defines the naming conventions for every DataHub CLI command group
and SDK API module, mapped to the backend API URL prefix they target. It is the
single source of truth for checking consistency across the three surfaces.

## Naming rules

1. **CLI command groups** are hyphenated nouns (e.g., `scheduled-ingestion`,
   `datahub assets`). The CLI name matches the API URL prefix where possible.
2. **SDK API modules** are `snake_case` Python files accessed as attributes on
   the `DataHubClient` instance (e.g., `client.assets`, `client.scheduled_ingestion`).
3. **API URL prefixes** are hyphenated in URLs, Django-routed via
   `hub/apps/api/urls.py`.
4. **Divergence is intentional**: the SDK exposes both coarse-grained modules
   (e.g., `marketplace.py`) and fine-grained sub-modules (e.g.,
   `marketplace_listings.py`). The CLI consolidates sub-groups (e.g.,
   `marketplace listings` is a subcommand, not a top-level group).

## Complete mapping table

| API Prefix | CLI Command | SDK Module(s) | Coverage |
|---|---|---|---|
| `ai/` | — | `client.ai` | SDK only |
| `assets/` | `datahub assets` | `client.assets` | CLI + SDK |
| `audit/` | `datahub audit` | `client.audit` | CLI + SDK |
| `auth/` | — | `client.auth` | SDK only |
| `baas/` | `datahub baas` | `client.baas` | CLI + SDK |
| `billing/` | `datahub billing` | `client.billing` | CLI + SDK |
| `compliance/` | `datahub compliance` | `client.compliance` | CLI + SDK |
| `config/` | `datahub config` | — | CLI only |
| `contracts/` | `datahub contracts` | `client.contracts` | CLI + SDK |
| `datasets/` | `datahub datasets` | `client.datasets` | CLI + SDK |
| `developer/` | — | — | Backend only |
| `dpia/` | — | — | Backend only |
| `dq/` | `datahub dq` | `client.dq` | CLI + SDK |
| `events/` | — | — | Backend only |
| `files/` | `datahub files` | `client.files` | CLI + SDK |
| `gdpr/` | `datahub gdpr` | `client.gdpr` | CLI + SDK |
| `governance/` | `datahub governance` | `client.governance` | CLI + SDK |
| `health/` | `datahub health` | `client.check_health()` | CLI + SDK |
| `jobs/` | `datahub jobs` | `client.jobs` | CLI + SDK |
| `lineage/` | `datahub lineage` | `client.lineage` | CLI + SDK |
| `marketplace/` | `datahub marketplace` | `client.marketplace`, `client.marketplace_listings` | CLI + SDK |
| `mesh/` | `datahub mesh` | `client.mesh` | CLI + SDK |
| `ml/` | `datahub ml` | `client.ml`, `client.model_serving`, `client.ai` | CLI + SDK |
| `observability/` | `datahub observability` | `client.observability` | CLI + SDK |
| `phase232/` | `datahub phase232` | `client.phase232` | CLI + SDK |
| `quality/` | — | — | Deprecated |
| `ropa/` | — | — | Backend only |
| `scheduled-exports/` | `datahub scheduled-export` | `client.scheduled_export` | CLI + SDK |
| `scheduled-ingestions/` | `datahub scheduled-ingestion` | `client.scheduled_ingestion` | CLI + SDK |
| `search/` | `datahub search` | `client.search` | CLI + SDK |
| `security/` | — | — | Backend only |
| `semantic/` | `datahub semantic` | `client.semantic` | CLI + SDK |
| `social/` | — | `client.social` | SDK only |
| `tenants/` | `datahub tenants` | `client.tenants` | CLI + SDK |
| `transformation/` | `datahub transformation` | `client.transformation` | CLI + SDK |
| `users/` | `datahub users` | `client.users` | CLI + SDK |
| `versioning/` | — | `client.versioning` | SDK only |
| `virtualization/` | `datahub virtualization` | `client.virtualization` | CLI + SDK |
| `webhooks/` | `datahub webhooks` | `client.webhooks` | CLI + SDK |
| `workflows/` | — | `client.workflows` | SDK only |

**Total**: 46 API prefixes. 29 with CLI coverage. 33 with SDK coverage.
4 backend-only (developer, dpia, ropa, security/quality deprecated).
4 SDK-only (ai, auth, social, versioning, workflows — internal/auth surfaces).

## CLI command format

Every CLI subcommand supports `--format json|table` for machine-readable output.

```bash
datahub <group> <action> [--format json|table] [filters...]
```

Examples:
```bash
datahub assets list --status ACTIVE --format table
datahub tenants get acme-corp
datahub observability freshness --format json
```

## SDK access pattern

```python
from datahub_interoperability import DataHubClient, DataHubClientConfig

config = DataHubClientConfig(base_url="https://api.example.com/api/v1", api_token="...")
async with DataHubClient(config) as client:
    # Top-level module
    assets = await client.assets.list_assets()
    # Sub-module
    listings = await client.marketplace_listings.list_listings()
    # Method on client
    health = await client.check_health()
```

## Maintenance

- **Owner**: Developer Experience
- **Last reviewed**: 2026-05-14
- **Next review**: When a new API prefix, CLI command group, or SDK module is added.
