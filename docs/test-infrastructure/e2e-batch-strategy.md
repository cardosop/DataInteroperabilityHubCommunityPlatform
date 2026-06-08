# E2E Batch Strategy

**Date:** 2026-05-22
**Phase:** 312.8.3 — Frontend Test Infrastructure
**Script:** `frontend/scripts/e2e-batches.sh`

---

## Overview

The E2E test suite (~2,140 tests across 8 CI batches) is partitioned into batches to:
1. **Control memory pressure** — 4+ parallel workers cause OOM kills on CI runners
2. **Reduce rate-limit cascades** — parallel login cycles saturate auth endpoints
3. **Enable targeted iteration** — developers run one batch instead of full suite
4. **Isolate persona-specific tests** — each batch targets a coherent user role set

---

## Batch Definitions

| Batch | Tests (est.) | Workers | Contents |
|---|---|---|---|
| 1 | ~100 | 1 | Auth, setup, cross-cutting, design-system, tenant onboarding, security, a11y |
| 2 | ~120 | auto | Route-level smoke: contracts, marketplace, DQ, mesh, integrations, admin |
| 3 | ~275 | 2 | DPO journeys + asset/contract/ODPS use cases |
| 4 | ~385 | 2 | Auth journeys + DC/DE journeys + integrations use cases |
| 5 | ~375 | 2 | TA, PA, Dev, Aud, cross-persona journeys + webhook use cases |
| 6 | ~400 | 2 | CPO, DS, DMO, DA, CM, Marketplace journeys + compliance/DQ/marketplace use cases |
| 7 | ~250 | 2 | Feature smoke, phase7.5, phase8, governance, onboarding, scheduled |
| 8 | ~25 | auto | UX flows: pickers, asset-dataset, files-upload, dataset-edit, ODPS link |
| 9 | ~210 | — | Deprecated phase specs (manual regression only — not in CI) |

---

## Batch Contents Detail

### Batch 1 — Foundation (~100 tests, workers=1)
```
e2e/auth-visitor-journeys.spec.ts     — Login, registration, visitor flow
e2e/login-app-shell.spec.ts           — App shell post-login
e2e/features/auth.spec.ts             — Auth feature specs
e2e/cross-cutting/                    — Alternate flows, error states
e2e/setup/                            — Test environment setup
e2e/a11y/                             — Authenticated a11y scans (10 routes)
e2e/design-system/                    — Component library tests
e2e/use-cases/auth/                   — Auth use-case flows
e2e/journeys/tenant/                  — Tenant management
e2e/security/                         — Security header validation
```

**Why workers=1:** Every test requires a full login cycle. 4 workers saturate backend login/capabilities endpoints, causing PostgreSQL statement timeouts (500) and rate-limit cascades (429) that fail 15+ tests.

### Batch 2 — Route Smoke (~120 tests, workers=auto)
```
e2e/journeys/core-data-routes/        — Core data endpoints
e2e/journeys/contracts-odps/          — Contract + ODPS routes
e2e/journeys/marketplace-dc/          — Marketplace + DataContract routes
e2e/journeys/dq-compliance-governance/— DQ + Compliance + Governance routes
e2e/journeys/mesh-virtualization-search-ai/ — Mesh, Virtualization, Search, AI routes
e2e/journeys/integrations-jobs-webhooks/   — Integrations + Jobs + Webhooks routes
e2e/journeys/admin-audit-settings/    — Admin + Audit + Settings routes
```

### Batch 3 — DPO Journeys (~275 tests, workers=2)
```
e2e/journeys/dpo/                     — Data Product Owner full journey
e2e/use-cases/assets/                 — Asset creation, management
e2e/use-cases/contracts/              — Contract lifecycle
e2e/use-cases/odps/                   — ODPS schema management
```

### Batch 4 — Auth + DC/DE Journeys (~385 tests, workers=2)
```
e2e/journeys/auth/                    — Authentication flows
e2e/journeys/dc/                      — Data Consumer journeys
e2e/journeys/de/                      — Data Engineer journeys
e2e/use-cases/integrations/           — External integrations
```

### Batch 5 — TA/PA/Dev/Aud Journeys (~375 tests, workers=2)
```
e2e/journeys/ta/                      — Tenant Admin operations
e2e/journeys/pa/                      — Platform Admin operations
e2e/journeys/dev/                     — Developer journeys
e2e/journeys/aud/                     — Auditor read-only RBAC
e2e/journeys/cross-persona/           — Cross-role value-chain tests
e2e/use-cases/webhooks/               — Webhook configuration
```

### Batch 6 — CPO/DS/DMO/DA/CM Journeys (~400 tests, workers=2)
```
e2e/journeys/cpo/                     — Compliance/Privacy Officer
e2e/journeys/ds/                      — Data Scientist
e2e/journeys/dmo/                     — Data Mesh Operator
e2e/journeys/da/                      — Data Analyst
e2e/journeys/cm/                      — Compliance Manager
e2e/journeys/marketplace/             — Marketplace operations
e2e/use-cases/compliance/             — Compliance workflows
e2e/use-cases/dq/                     — Data Quality workflows
e2e/use-cases/marketplace/            — Marketplace purchase flows
```

### Batch 7 — Feature Smoke + Governance (~250 tests, workers=2)
```
e2e/features/                         — Feature smoke tests
e2e/phase7.5-features-gap-closure.spec.ts
e2e/phase8-hardening.spec.ts
e2e/journeys/governance/              — Approval inbox, bulk ops, delegation
e2e/journeys/governance-retention/    — Retention policy management
e2e/journeys/onboarding/              — Product tour, getting started
e2e/journeys/scheduled-export/        — Scheduled export workflows
e2e/journeys/scheduled-ingestion/     — Scheduled ingestion workflows
```

### Batch 8 — UX Flows (~25 tests, workers=auto)
```
e2e/use-cases/ux/                     — Resource pickers, asset-dataset flows,
                                         files upload, dataset edit, ODPS link
```

### Batch 9 — Deprecated (Manual Only, ~210 tests)
```
e2e/phase2-catalog-journey.spec.ts
e2e/phase3-quality-gates.spec.ts
e2e/phase4-marketplace-journey.spec.ts
e2e/phase5-odps-journey.spec.ts
e2e/phase6-mesh-virtualization.spec.ts
e2e/phase7-social-ai-developer-baas-ml.spec.ts
```

---

## Memory & Parallelism Rationale

### Worker Limitations

| Batch | Workers | Rationale |
|---|---|---|
| 1 | 1 | Full login per test → auth endpoint saturation at >1 worker |
| 3-7 | 2 | 4 workers → 12 Chrome instances → OOM kills on 61GiB host at test ~150-200 |
| 8 | auto | Small batch, fast tests — worker count irrelevant |

### Memory Profile

- **Single worker:** ~4 Chrome instances (setup + test + fallback), ~2GB
- **2 workers:** ~6 Chrome instances, ~3.5GB
- **4 workers:** ~12 Chrome instances, ~7GB → OOM on 61GiB runners when Fuseki + API also consume memory

### Rate Limiting

Parallel workers share a single test tenant. At 4 workers:
- Login endpoint: 4 simultaneous requests → 429 cascade
- Capabilities endpoint: 4 simultaneous requests → PostgreSQL statement timeouts

The `RATE_LIMIT_E2E_RELAX=true` flag in docker-compose.test.yml mitigates this but doesn't eliminate it entirely.

---

## How to Run

### Individual Batches
```bash
npm run test:e2e:batch1    # Batch 1
npm run test:e2e:batch2    # Batch 2
# ... through batch 8
npm run test:e2e:batches:list  # List all batch definitions
```

### With Options
```bash
E2E_PROJECT=chromium npm run test:e2e:batch1     # Single project (faster)
E2E_SKIP_API_RESTART=1 npm run test:e2e:batch3   # Skip API restart
E2E_VISIBLE=1 npm run test:e2e:batch1             # Headed mode
```

### CI Execution
The `playwright-e2e.yml` workflow runs batches via the npm scripts against the docker-compose.test.yml backend.

---

## Intentionally Excluded (Manual Only)

| Directory | Reason |
|---|---|
| `e2e/dimensions/` | Network-failure, rate-limit, timeout, concurrent tests — flaky by design |
| `e2e/personas/` | Full persona journey suites — very long-running |

Run these manually when investigating specific issues:
```bash
npx playwright test e2e/dimensions/ --project=chromium
npx playwright test e2e/personas/ --project=chromium
```
