# W11.3 — IDOR Probe Coverage Report

Generated: 2026-10-16T20:27:48.563785+00:00 — by `python manage.py check_idor_coverage`.

## Summary

- Tenant-scoped route keys in scope: **588**
- Probed by the generated suite (strict cross-tenant contract): **586**
- Allowlisted with written reasons: **2**
- Coverage: **99.66%** (task threshold 95.0%)

## Probe coverage by app

| App | Probed route keys |
|---|---|
| governance | 70 |
| marketplace | 37 |
| tenants | 29 |
| contracts | 28 |
| mesh | 28 |
| social | 25 |
| dq | 22 |
| transformation | 22 |
| assets | 21 |
| semantic | 20 |
| integrations | 19 |
| compliance | 16 |
| ml | 16 |
| processor_agreements | 16 |
| warehouses | 15 |
| files | 14 |
| scheduled_ingestion | 14 |
| datasets | 13 |
| hub_auth | 13 |
| dpia | 12 |
| gdpr | 12 |
| audit | 11 |
| breach | 11 |
| consent | 11 |
| webhooks | 10 |
| billing | 9 |
| scheduled_export | 9 |
| virtualization | 9 |
| dsar | 8 |
| jobs | 8 |
| ropa | 8 |
| users | 8 |
| baas | 6 |
| data_movement | 6 |
| databricks_admin | 5 |
| notifications | 5 |

## Allowlisted routes (the ≤5% remainder, each with its reason)

| Method | Path | Reason |
|---|---|---|
| POST | `/api/v1/contracts/products/` | The create executes the full ODPS product-creation workflow (schema validation chain + external workflow steps) and the payload carries no tenant-scoped FK reference surface, so neither the create half nor the payload-FK direction is probeable in the DB-only security job.  The tenant boundary for contract creation is pinned by the standard contract-create probe (POST /api/v1/contracts/) and the contracts IDOR suites (tests/security/test_idor_contracts.py). |
| POST | `/api/v1/databricks/workspaces/` | The create runs SSRF host validation with live DNS resolution — a synthetic probe hostname can never pass, and the payload carries no tenant-scoped FK reference surface for the payload-FK direction. The workspace object-level IDOR probes (GET/PATCH/DELETE detail routes) stay probed by the matrix. |

The probe suite, manifest, and scope rule:
`tests/security/test_w113_asvs_v4_access_control.py`, `docs/api-audit/idor-probe-manifest.json`, `docs/security/adversarial-matrices/w113-access-control-matrix.md`.

