# E2E Test Semantics

**Last Updated**: 2026-02-19
**Task**: Phase 7.1.1 — Canonical definition of test semantics for E2E tests
**Related**: [E2E_ENVIRONMENT_REQUIREMENTS.md](E2E_ENVIRONMENT_REQUIREMENTS.md), [TEST_ASSERTION_CONVENTIONS.md](TEST_ASSERTION_CONVENTIONS.md), [frontend/e2e/E2E_TEST_SKIP_DOCUMENTATION.md](../frontend/e2e/E2E_TEST_SKIP_DOCUMENTATION.md)

---

## Overview

This document defines the canonical semantics for E2E tests across backend (pytest) and frontend (Playwright). All E2E tests fall into one of three categories: **strict**, **environment-dependent**, or **deferred**. These rules ensure tests fail when they should and skip only when justified.

---

## 1. Strict Tests (Single Expected Outcome)

**Definition**: Tests that have exactly one expected outcome. The test must **fail** if the actual outcome differs.

### Rules

- Use `assertEqual` (or equivalent) for single expected values.
- Do **not** use `assertIn` with multiple allowed values unless the API contract explicitly allows multiple statuses (see [TEST_ASSERTION_CONVENTIONS.md](TEST_ASSERTION_CONVENTIONS.md)).
- Security tests (e.g., unauthenticated access to protected endpoints) must assert the single expected status (e.g., `401`).
- Validation tests must assert the single expected status (e.g., `400` for invalid input); never accept `500` as valid for validation errors.
- When a required precondition fails (e.g., API unreachable, DB down), the test must **fail** (throw/re-raise), not skip.

### Examples

```python
# Backend: strict — single expected outcome
self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

# Backend: validation error — only 400 is valid
self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
```

```typescript
// Frontend: strict — single expected outcome
expect(response.status()).toBe(401);
```

---

## 2. Environment-Dependent Tests (Skip Only When Required Service Unavailable)

**Definition**: Tests that require an optional service (Prefect, MailHog, AI/ML, etc.). Skip **only** when the required service is demonstrably unavailable, with a clear, actionable reason.

### Rules

- Skip **only** when the required service is unavailable (connection refused, timeout, health check fails).
- The skip reason must include:
  - Which service is missing
  - How to start it (e.g., `docker compose -f docker-compose.test.yml up -d prefect-db-test prefect-server-test ...`)
  - A reference to [E2E_ENVIRONMENT_REQUIREMENTS.md](E2E_ENVIRONMENT_REQUIREMENTS.md) if applicable
- Do **not** skip for:
  - Precondition failures that indicate a bug (e.g., `createAssetViaApi` returns no assets due to API/tenant mismatch)
  - Wrong URL, malformed response, or other non-transient errors
- Use `test.skip(condition, reason)` at **describe level** when the entire spec depends on an optional service and the service is checked once at the start.
- For transient errors only (ConnectionRefused, Timeout, ConnectTimeout): skip with a clear reason. For other exceptions (wrong URL, malformed response): re-raise.

### Examples

```typescript
// Frontend: environment-dependent — skip when Prefect unavailable
test.beforeEach(async () => {
  const healthRes = await fetch(`${PREFECT_INTEGRATION_URL}/health`);
  if (!healthRes.ok) {
    test.skip(
      true,
      `Prefect integration service unhealthy (${healthRes.status}). Start: docker compose -f docker-compose.test.yml up -d prefect-db-test prefect-server-test prefect-worker-test prefect-integration-service-test`
    );
  }
});
```

```python
# Backend: environment-dependent — skip when MinIO unavailable
if not minio_available:
    pytest.skip("MinIO service not available - skipping file upload test. Start: docker compose -f docker-compose.test.yml up -d minio-test")
```

### Precondition Failures → Fail, Not Skip

When a **required** precondition fails (e.g., API should be up, assets should exist after `createAssetViaApi`), the test must **fail** (throw), not skip. Skipping hides real bugs.

| Scenario | Action | Rationale |
|----------|--------|-----------|
| `createAssetViaApi` returns no assets (API/tenant mismatch) | **Fail** (throw) | Indicates setup or API bug |
| Prefect for scheduled ingestion/export journeys | **Fail** (throw) | Required for that journey; fail when unreachable (Phase 7.4.3) |
| Prefect for other optional flows | **Skip** (with reason) | Optional service unavailable |
| MailHog not reachable for password reset | **Skip** (with reason) | Optional service for that flow |
| Login redirect when roles not set up | **Fail** (throw) | Required setup missing; run `ensure_e2e_user_roles` |
| File in API but not visible in UI after retries | **Skip** (with reason) | Timing/cache; optional to verify |

---

## 3. Deferred Tests (test.skip for Intentionally Unimplemented Features)

**Definition**: Tests for features that are **intentionally not yet implemented** (backlog, deferred). Use `test.skip` or `test.describe.skip` with a documented reason.

### Rules

- Use `test.skip('reason')` or `test.describe.skip('reason')` for deferred journeys/features.
- The skip reason must include:
  - UC ID and/or JOURNEY ID
  - Short description of what is missing
  - Reference to backlog/spec (e.g., `docs/BACKLOG_TRANSFORMATION_PIPELINE.md`)
- Deferred tests are **never** run until the feature is implemented; they are placeholders for traceability.
- Do **not** use `test.skip(true, reason)` for deferred tests — use `test.skip(reason)` (condition = always skip).

### Examples

```typescript
// Frontend: deferred — transformation pipeline not implemented
test.skip('JOURNEY-DPO-008: Create Transformation Pipeline for Asset', async ({ page }) => {
  // Deferred: Transformation pipeline backend not implemented.
  // See: docs/USER_JOURNEYS.md, docs/BACKLOG_TRANSFORMATION_PIPELINE.md
});
```

```typescript
// Frontend: deferred — entire spec
test.describe.skip('JOURNEY-DPO-008: Create Transformation Pipeline for Asset', () => {
  // Deferred: UC-TRANS-001, JOURNEY-DPO-008 — Transformation pipeline not implemented.
  // Backlog: docs/BACKLOG_TRANSFORMATION_PIPELINE.md
});
```

---

## 4. Summary Table

| Test Type | When to Use | Skip Allowed? | Fail When |
|-----------|-------------|---------------|-----------|
| **Strict** | Single expected outcome | No | Actual ≠ expected; required precondition fails |
| **Environment-dependent** | Optional service required | Yes, only when service unavailable | Wrong URL, malformed response, non-transient errors |
| **Deferred** | Feature not implemented | Always skipped | N/A (never runs) |

---

## 5. Anti-Patterns (Do Not Use)

| Anti-Pattern | Correct Approach |
|--------------|------------------|
| `test.skip(true, 'No assets after createAssetViaApi')` for precondition failure | **Fail** (throw) with clear error; fix root cause |
| `assertIn(response.status_code, [200, 401])` for auth test | Use `assertEqual(401)` — auth bypass is a bug |
| `assertIn(response.status_code, [400, 500])` for validation test | Use `assertEqual(400)` — 500 indicates server bug |
| `except: pytest.skip(...)` for any exception | Only skip on ConnectionRefused, Timeout, ConnectTimeout; re-raise others |
| S3 fallback to mock when MinIO fails | When real S3 required: re-raise; no silent fallback |
| `.catch(() => false)` or `.catch(() => null)` hiding failures | Propagate failures; handle optional steps explicitly |

---

## 6. When Multiple Status Codes Are Valid

When the API contract allows multiple valid statuses (e.g. 200/202 for async, 200/503 for health), document the case in [TEST_ASSERTION_CONVENTIONS.md](TEST_ASSERTION_CONVENTIONS.md) Section 2 and add a one-line comment at the assertion. See [TEST_ASSERTION_CONVENTIONS.md](TEST_ASSERTION_CONVENTIONS.md) for the full list of intentional multi-status cases.

---

## 7. References

- [E2E_ENVIRONMENT_REQUIREMENTS.md](E2E_ENVIRONMENT_REQUIREMENTS.md) — Services per test group, health checks
- [TEST_ASSERTION_CONVENTIONS.md](TEST_ASSERTION_CONVENTIONS.md) — assertIn vs assertEqual, multi-status cases
- [frontend/e2e/E2E_TEST_SKIP_DOCUMENTATION.md](../frontend/e2e/E2E_TEST_SKIP_DOCUMENTATION.md) — Skip conventions, deferred journeys
- [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md) — Test execution order, CI integration
