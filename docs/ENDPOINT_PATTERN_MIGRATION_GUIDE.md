# Endpoint Pattern Migration Guide

This guide documents the migration from legacy flat endpoint patterns to the standardized nested resource patterns.

## What Changed

The API endpoint structure was standardized from flat URL patterns (e.g., `/compliance-runs/`) to nested resource patterns (e.g., `/api/v1/compliance/runs/`). This change affects all API consumers including SDK, CLI, and direct HTTP clients. The new structure groups endpoints by resource (compliance, dq, etc.) under versioned API paths, providing better organization, discoverability, and consistency across the platform.

## Breaking Changes

- **Direct API consumers** — Legacy flat paths like `/compliance-runs/` and `/dq-runs/` no longer work. All requests must use the new nested paths under `/api/v1/`.
- **SDK method signatures** — Old flat method names (e.g., `client.compliance_runs.list()`) are removed. Use nested resource accessors (e.g., `client.compliance.runs.list()`).
- **Hardcoded URLs** — Any hardcoded references to legacy endpoint patterns in scripts, configuration files, or documentation will return 404 errors after migration.

## Old Patterns (deprecated)

| Legacy Pattern | Replacement |
|---|---|
| `/compliance-runs/` | `/api/v1/compliance/runs/` |
| `/dq-runs/` | `/api/v1/dq/runs/` |

## New Patterns (standardized)

| Standardized Pattern | Description |
|---|---|
| `/api/v1/compliance/runs/` | List/create compliance runs |
| `/api/v1/compliance/runs/{id}/` | Get/update a compliance run |
| `/api/v1/compliance/runs/{id}/results/` | Get results for a run |
| `/api/v1/dq/runs/` | List/create DQ runs |
| `/api/v1/dq/runs/{id}/` | Get/update a DQ run |
| `/api/v1/dq/runs/{id}/results/` | Get results for a run |

## Migration Steps

1. **Python SDK** — Update all SDK calls from `client.compliance_runs.list()` to `client.compliance.runs.list()`.
2. **CLI** — The `datahub` CLI automatically translates old patterns; update CLI scripts to use new subcommand structure: `datahub compliance runs list`.
3. **Direct API consumers** — Replace `/compliance-runs/` with `/api/v1/compliance/runs/` in all HTTP clients and curl scripts.

## Verification

After migration, verify:
1. Old endpoints return 404.
2. New endpoints are reachable and return expected data.
3. SDK integration tests pass against the new endpoint patterns.
