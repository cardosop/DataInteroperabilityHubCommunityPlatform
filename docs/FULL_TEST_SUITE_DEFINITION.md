# Full Test Suite Definition

**Document Version**: 1.0.0  
**Last Updated**: 2026-02-12  
**Status**: Active  
**Purpose**: Single canonical place that defines the full test suite, recommended run order, commands per step, and which steps run in CI vs nightly/manual. Aligns CI, scripts, and runbooks per [GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md](GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md) Phase 5 and [openspec/changes/testsfix1](../openspec/changes/testsfix1/) task 5.3b.

**Related**: [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md), [GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md](GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md), [RUNBOOKS.md](RUNBOOKS.md).

---

## Table of Contents

1. [Overview](#overview)
2. [Test Types (Backend and Frontend)](#test-types-backend-and-frontend)
3. [Recommended Run Order](#recommended-run-order)
4. [Commands and Scripts per Step](#commands-and-scripts-per-step)
5. [CI vs Nightly vs Manual](#ci-vs-nightly-vs-manual)
6. [Optional / Extended Suites (Nightly or Manual)](#optional--extended-suites-nightly-or-manual)

---

## Overview

The **full suite** is the ordered set of test steps that together validate the platform. The same order is used by:

- **Local / runbook**: `scripts/run_phase_12a_full_suites.sh` (backend, smoke, frontend, 12A.3).
- **CI**: `ci.yml` runs the canonical gate (smoke, unit, integration, e2e, security); see [CI vs Nightly vs Manual](#ci-vs-nightly-vs-manual).
- **Nightly**: `phase-12a-nightly.yml` runs full Phase 12A (including security, performance, concurrency, regression).
- **Release**: `phase-12a-release.yml` runs full Phase 12A and retains evidence for sign-off.

No mocks/stubs; root-cause fixes only; evidence under `test_reports_comprehensive/{date}/` per [EVIDENCE_COLLECTION_PLAN.md](EVIDENCE_COLLECTION_PLAN.md).

---

## Test Types (Backend and Frontend)

| # | Type | Scope | Typical duration |
|---|------|--------|-------------------|
| 1 | Smoke | API and microservice health | 1–2 min |
| 2 | Backend unit | `hub/apps/`, `tests/unit/` (excl. integration/e2e by marker) | 5–15 min |
| 3 | Backend integration | `tests/integration/` | 15–40 min |
| 4 | Backend E2E | `tests/e2e/` | 20–60 min |
| 5 | Security | `tests/security/` | 5–15 min |
| 6 | Regression | `tests/regression/` | 10–30 min |
| 7 | Concurrency | `tests/concurrency/` | 5–20 min |
| 8 | Performance | `tests/performance/` | 5–60 min |
| 9 | Chaos | `tests/chaos/` | 5–20 min |
| 10 | UAT | `tests/uat/` | 5–15 min |
| 11 | SDK (Python) | `tests/sdk_python/` | 5–15 min |
| 12 | Scripts | `tests/scripts/` | 5–15 min |
| 13 | Frontend unit | Vitest (frontend/) | 2–10 min |
| 14 | Frontend component | Component tests (if configured) | 2–5 min |
| 15 | Frontend a11y | Accessibility tests (if configured) | 2–5 min |
| 16 | Frontend coverage check | Coverage threshold | &lt; 1 min |
| 17 | Frontend E2E | Playwright | 10–30 min |

---

## Recommended Run Order

Canonical order used by Phase 12A and referenced by runbooks:

| Step | Name | When / note |
|------|------|-------------|
| 1 | Smoke | After API and services are up |
| 2 | Backend unit | hub/apps/ + tests/unit/, exclude integration/e2e |
| 3 | Backend integration | tests/integration/ with --docker-compose-runtime |
| 4 | Backend E2E | tests/e2e/ with --docker-compose-runtime |
| 5 | Security | tests/security/ |
| 6 | Regression | tests/regression/ (can be last batch or nightly) |
| 7 | Concurrency | tests/concurrency/ |
| 8 | Performance | tests/performance/ |
| 9 | Chaos | tests/chaos/ (nightly or manual) |
| 10 | UAT | tests/uat/ (nightly or manual) |
| 11 | SDK Python | tests/sdk_python/ (nightly or manual) |
| 12 | Scripts | tests/scripts/ (nightly or manual) |
| 13 | Frontend unit | cd frontend && npm run test:run |
| 14 | Frontend component | cd frontend && npm run test:component (if present) |
| 15 | Frontend a11y | cd frontend && npm run test:a11y (if present) |
| 16 | Frontend coverage check | cd frontend && npm run test:coverage:check (if present) |
| 17 | Frontend E2E | cd frontend && npm run test:e2e |

Steps 1–5 and 13–17 are the **CI gate** (or equivalent). Steps 6–8 run in **nightly** and **release**. Steps 9–12 run **nightly or manual** only (see [Optional / Extended Suites](#optional--extended-suites-nightly-or-manual)).

---

## Commands and Scripts per Step

| Step | Command or script | Artifact path (Phase 12A) |
|------|-------------------|----------------------------|
| 1 Smoke | `pytest tests/smoke/ -v --tb=short --junit-xml=...` or via full script | `test_reports_comprehensive/{date}/smoke/` |
| 2 Backend unit | `pytest hub/apps/ tests/unit/ -v -m "not integration and not e2e" ...` or `run_phase_12a_backend_suites.sh` (step 12A.1.1) | `.../unit/` |
| 3 Backend integration | `pytest tests/integration/ -v --docker-compose-runtime ...` or 12A.1.2 | `.../integration/` |
| 4 Backend E2E | `pytest tests/e2e/ -v --docker-compose-runtime ...` or 12A.1.3 | `.../e2e/` |
| 5 Security | `pytest tests/security/ -v --tb=short --junit-xml=...` or 12A.3.1 | `.../security/` |
| 6 Regression | `pytest tests/regression/ -v -m regression ...` or 12A.3.4 | `.../regression/` |
| 7 Concurrency | `pytest tests/concurrency/ -v ...` or 12A.3.3 | `.../concurrency/` |
| 8 Performance | `pytest tests/performance/ ...` or `tests/performance/run_performance_tests.sh` or 12A.3.2 | `.../performance/` |
| 9 Chaos | `pytest tests/chaos/ -v --tb=short` (manual or nightly) | Optional: `.../chaos/` |
| 10 UAT | `pytest tests/uat/ -v --tb=short` (manual or nightly) | Optional: `.../uat/` |
| 11 SDK Python | `pytest tests/sdk_python/ -v --tb=short` (manual or nightly) | Optional: `.../sdk_python/` |
| 12 Scripts | `pytest tests/scripts/ -v --tb=short` (manual or nightly) | Optional: `.../scripts/` |
| 13 Frontend unit | `cd frontend && npm run test:run` or 12A.2.1 | `.../frontend-unit/` |
| 14 Frontend component | `cd frontend && npm run test:component` (if present) | As configured |
| 15 Frontend a11y | `cd frontend && npm run test:a11y` (if present) | As configured |
| 16 Frontend coverage | `cd frontend && npm run test:coverage:check` (if present) | — |
| 17 Frontend E2E | `cd frontend && npm run test:e2e` or 12A.2.2 | `.../frontend-e2e/` |

**Full-suite script**: `scripts/run_phase_12a_full_suites.sh` runs backend (steps 2–4: unit, integration, e2e), then smoke (step 1), then frontend (steps 13, 17), then 12A.3 (steps 5–8: security, performance, concurrency, regression). It does **not** run chaos, UAT, SDK, or scripts; those are documented here as nightly or manual.

---

## CI vs Nightly vs Manual

| Where | Steps included | Workflow / trigger |
|-------|----------------|--------------------|
| **CI (ci.yml)** | Canonical gate: smoke (after API up), unit (app + root), integration, e2e, security (`tests/security/` in separate job). Same logical order as this document. | Push/PR to main, develop |
| **E2E workflow (e2e.yml)** | Dedicated E2E run: `tests/e2e/` plus scheduled ingestion/export E2E with Prefect. See [TEST_EXECUTION_PLAN — E2E in CI vs e2e.yml](TEST_EXECUTION_PLAN.md#e2e-in-ci-vs-e2e-workflow-gap-11). | Push/PR, workflow_dispatch |
| **Nightly (phase-12a-nightly.yml)** | Full Phase 12A: backend (unit, integration, e2e), smoke, frontend, security, performance, concurrency, regression. | Schedule 02:00 UTC, workflow_dispatch |
| **Release (phase-12a-release.yml)** | Same as nightly; evidence retained for sign-off. | Tags v*, workflow_dispatch |
| **Manual / local** | Any subset or full suite via `run_phase_12a_full_suites.sh` or `run_phase_12a_batched.sh`; chaos, UAT, SDK, scripts per commands below. | Runbooks |

Performance, regression, and concurrency are **optional for the PR gate**; they run in nightly or release so main CI stays fast. Regression can be the last batch in batched execution or run in nightly.

---

## Optional / Extended Suites (Nightly or Manual)

These suites are **not** part of `run_phase_12a_full_suites.sh`. Run them nightly or manually when needed. Exact commands:

| Suite | Command | When |
|-------|---------|------|
| **Chaos** | `pytest tests/chaos/ -v --tb=short` (stack must be up; may require services) | Nightly or manual |
| **UAT** | `pytest tests/uat/ -v --tb=short` | Nightly or manual (e.g. compatibility) |
| **SDK Python** | `pytest tests/sdk_python/ -v --tb=short` (API and env as for integration) | Nightly or manual |
| **Scripts** | `pytest tests/scripts/ -v --tb=short` | Nightly or manual |

To run with the same stack as Phase 12A:

```bash
# Ensure test stack is up
docker compose -f docker-compose.test.yml up -d
# Then, from repo root:
PYTHONPATH=. DJANGO_SETTINGS_MODULE=hub.settings pytest tests/chaos/ -v --tb=short
PYTHONPATH=. DJANGO_SETTINGS_MODULE=hub.settings pytest tests/uat/ -v --tb=short
PYTHONPATH=. DJANGO_SETTINGS_MODULE=hub.settings pytest tests/sdk_python/ -v --tb=short
PYTHONPATH=. DJANGO_SETTINGS_MODULE=hub.settings pytest tests/scripts/ -v --tb=short
```

Artifacts: if you want them under `test_reports_comprehensive/{date}/`, run and redirect manually (e.g. `--junit-xml=test_reports_comprehensive/$(date +%Y-%m-%d)/chaos/junit.xml`) or add a small wrapper script.

---

*This document is the canonical definition of the full suite and run order. CI and scripts should align with it; see [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md) and [GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md](GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md) for detailed commands and evidence layout.*
