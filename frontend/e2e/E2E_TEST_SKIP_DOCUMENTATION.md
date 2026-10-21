# E2E Test Skip Documentation

**Last Updated**: 2026-02-19
**Task**: 6.10.1.4, Phase 7.1.4 — Document `test.skip()` for deferred journeys; align with E2E_TEST_SEMANTICS
**Related**: [docs/E2E_TEST_SEMANTICS.md](../../docs/E2E_TEST_SEMANTICS.md), [docs/E2E_ENVIRONMENT_REQUIREMENTS.md](../../docs/E2E_ENVIRONMENT_REQUIREMENTS.md)

---

## Overview

When a journey or use case is **deferred** (backend not implemented) or **blocked** by a known gap, E2E tests should use `test.skip()` with a reason that references the UC/JOURNEY ID. This ensures traceability and prevents false failures.

**Critical rule (Phase 7.1.4)**: **Precondition failures → fail (throw), not skip.** Only use `test.skip()` for (a) deferred features, or (b) optional service unavailable. See [E2E_TEST_SEMANTICS.md](../../docs/E2E_TEST_SEMANTICS.md) for the canonical definition.

---

## When to Skip vs Fail

| Scenario | Action | Rationale |
|----------|--------|------------|
| **Deferred feature** (backend not implemented) | `test.skip(reason)` | Placeholder for traceability; never runs until implemented |
| **Optional service unavailable** (MailHog for password reset) | `test.skip(condition, reason)` | Service not started; skip with clear "how to start" message |
| **Prefect for scheduled ingestion/export** | **Fail** (throw) | Required for that journey; fail when unreachable (Phase 7.4.3) |
| **Precondition failure** (e.g. `createAssetViaApi` returns no assets) | **Fail** (throw) | Indicates setup/API bug; do not hide with skip |
| **Required service down** (API, Postgres, Redis, MinIO) | **Fail** (throw) | Core stack must be up; do not run E2E without it |
| **Login redirect when roles not set up** | **Fail** (throw) | Run `ensure_e2e_user_roles`; not a skip case |

**Anti-pattern**: `test.skip(true, 'No assets after createAssetViaApi')` — this hides a bug. Instead, throw with a clear error so the root cause can be fixed.

---

## Skip Convention

```typescript
test.skip('JOURNEY-DPO-008: Create Transformation Pipeline for Asset', async ({ page }) => {
  // Deferred: Transformation pipeline backend not implemented.
  // See: docs/USER_JOURNEYS.md, docs/BACKLOG_TRANSFORMATION_PIPELINE.md
});
```

Or with `test.describe.skip` for entire spec files:

```typescript
// JOURNEY-DPO-008.spec.ts
test.describe.skip('JOURNEY-DPO-008: Create Transformation Pipeline for Asset', () => {
  // Deferred: UC-TRANS-001, JOURNEY-DPO-008 — Transformation pipeline not implemented.
  // Backlog: docs/BACKLOG_TRANSFORMATION_PIPELINE.md
});
```

---

## Deferred Journeys (Transformation Pipeline)

| Journey ID | Description | Skip Reason |
|------------|-------------|-------------|
| **JOURNEY-DPO-008** | Create Transformation Pipeline for Asset | Deferred: Transformation pipeline backend not implemented. UC-TRANS-001, BACKLOG_TRANSFORMATION_PIPELINE.md |
| **JOURNEY-DE-007** | Create Transformation Pipeline | Deferred: Transformation pipeline backend not implemented. UC-TRANS-001, BACKLOG_TRANSFORMATION_PIPELINE.md |
| **JOURNEY-DC-007** | Create Transformation Pipeline for Data | Deferred: Transformation pipeline backend not implemented. UC-TRANS-001, BACKLOG_TRANSFORMATION_PIPELINE.md |
| **JOURNEY-DEV-006** | Integrate Transformation Pipeline API | Deferred: Transformation pipeline backend not implemented. UC-TRANS-001, BACKLOG_TRANSFORMATION_PIPELINE.md |
| **JOURNEY-AUD-005** | Audit Transformation Pipelines | Deferred: Transformation pipeline backend not implemented. UC-TRANS-001, BACKLOG_TRANSFORMATION_PIPELINE.md |
| **JOURNEY-DA-001** | Create Transformation Pipeline | Deferred: Transformation pipeline backend not implemented. UC-TRANS-001, BACKLOG_TRANSFORMATION_PIPELINE.md |

**Related deferred journeys** (same root cause): JOURNEY-DC-007, JOURNEY-DEV-006, JOURNEY-AUD-005, JOURNEY-DA-001 (each has dedicated skip spec).

**References**:
- [USER_JOURNEYS.md](../../docs/USER_JOURNEYS.md) — Deferred journeys section
- [BACKLOG_TRANSFORMATION_PIPELINE.md](../../docs/BACKLOG_TRANSFORMATION_PIPELINE.md)
- [USE_CASES.md](../../docs/USE_CASES.md) — UC-TRANS-001

---

## Backend-Not-Implemented Flows

When a flow depends on an API or feature that does not exist:

```typescript
test.skip('Feature X — backend endpoint /api/v1/feature-x not implemented', async () => {
  // UC-XXX-001, JOURNEY-YYY-NNN
});
```

Always include:
1. **UC ID** (use case) if applicable
2. **JOURNEY ID** if applicable
3. **Short description** of what is missing

---

## When to Use `test.skip` vs `test.fixme`

- **`test.skip`**: Deferred or permanently out-of-scope; skip reason documents the gap.
- **`test.fixme`**: Known flake or temporary issue; test will run but not fail the suite. Prefer fixing root cause over `test.fixme`.

---

## Optional Services (Tests May Skip If Unavailable)

Some E2E tests require additional services. If unavailable, tests skip with a clear reason. See [E2E_ENVIRONMENT_REQUIREMENTS.md](../../docs/E2E_ENVIRONMENT_REQUIREMENTS.md) for full details.

| Service | Port | Used By | How to Start |
|---------|------|---------|--------------|
| **MailHog** | 8025 | JOURNEY-AUTH-003 (password reset) | `docker compose -f docker-compose.test.yml up -d mailhog-test` |
| **Prefect** (server, db, worker, integration) | 4202, 8114 | Scheduled ingestion/export journeys | `docker compose -f docker-compose.test.yml up -d prefect-db-test prefect-server-test prefect-worker-test prefect-integration-service-test` |

**CI**: The Playwright E2E workflow starts MailHog and Prefect services. If they fail to start, tests that depend on them will skip.

**Skip reason format**: When skipping due to optional service unavailable, include the service name and the exact `docker compose` command to start it (see [E2E_TEST_SEMANTICS.md](../../docs/E2E_TEST_SEMANTICS.md) Section 2).

---

## Test Projects and Spec Coverage

| Project | Runs | Excluded (testIgnore) |
|---------|------|------------------------|
| **setup-auth** | `setup/auth-storage.spec.ts` only | — |
| **chromium** | All specs except setup-auth, dimensions/*, personas/* | setup/auth-storage.spec.ts, dimensions/*, personas/* |
| **visible** | Same as chromium (headed mode) | Same |
| **chromium-routes** | Same as chromium | Same |

**Specs that may not appear in default runs** (e.g. when using `--grep` or path filters):
- `phase3-quality-gates.spec.ts`, `phase4-marketplace-journey.spec.ts`, `phase5-odps-journey.spec.ts` — Long-running journeys (5–15 min); run with path filter if needed.
- `auth-visitor-journeys.spec.ts` — Skips when MailHog unreachable.
- `scheduled-ingestion-journey.spec.ts`, `scheduled-export-journey.spec.ts` — Skips when Prefect unavailable (503/404).

**Rate-limit reset**: `npm run test:e2e` invokes `scripts/e2e-detect-api.sh`, which runs `reset_e2e_auth_rate_limits` before Playwright. This reduces 8.0m/2.0m timeouts from login retries.

---

## References

- [docs/E2E_TEST_SEMANTICS.md](../../docs/E2E_TEST_SEMANTICS.md) — Canonical test semantics: strict, environment-dependent, deferred
- [docs/E2E_ENVIRONMENT_REQUIREMENTS.md](../../docs/E2E_ENVIRONMENT_REQUIREMENTS.md) — Services per test group, health checks
- [docs/TEST_ASSERTION_CONVENTIONS.md](../../docs/TEST_ASSERTION_CONVENTIONS.md) — assertIn vs assertEqual

---

## Acceptance Criteria (6.10.1.4, Phase 7.1.4)

- [x] Skip reason references UC/JOURNEY ID
- [x] Deferred journeys (JOURNEY-DPO-008, JOURNEY-DE-007) documented
- [x] Convention documented for backend-not-implemented flows
- [x] Precondition failures → fail (throw), not skip (Phase 7.1.4)
- [x] Only deferred features and optional-service-unavailable use `test.skip()` (Phase 7.1.4)
