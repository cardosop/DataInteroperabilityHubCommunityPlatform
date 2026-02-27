# Test Assertion Conventions

**Last Updated**: 2026-02-19
**Task**: Phase 7.1.3 — When assertIn vs assertEqual is acceptable; intentional multi-status cases
**Related**: [E2E_TEST_SEMANTICS.md](E2E_TEST_SEMANTICS.md), [E2E_ENVIRONMENT_REQUIREMENTS.md](E2E_ENVIRONMENT_REQUIREMENTS.md)

---

## Overview

This document defines when to use `assertEqual` vs `assertIn` (or equivalent) in tests, and documents intentional multi-status cases where multiple HTTP status codes are valid. Following these conventions prevents loose assertions that mask bugs.

---

## 1. assertEqual vs assertIn

### 1.1 Prefer assertEqual (Single Expected Outcome)

Use `assertEqual` (or `expect(x).toBe(y)`) when the API contract or behavior has **exactly one** expected outcome.

| Scenario | Assertion | Rationale |
|----------|-----------|-----------|
| Unauthenticated access to protected endpoint | `assertEqual(401)` | Auth bypass is a bug; 200 must fail |
| Validation error (invalid input) | `assertEqual(400)` | 500 indicates server bug; must fail |
| Successful creation | `assertEqual(201)` | Single success status |
| Not found | `assertEqual(404)` | Single error status |
| Forbidden (no permission) | `assertEqual(403)` | Single error status |

**Examples**:

```python
# Backend: strict — single expected
self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
```

```typescript
// Frontend: strict — single expected
expect(response.status()).toBe(401);
expect(response.status()).toBe(400);
```

### 1.2 When assertIn Is Acceptable

Use `assertIn` (or `expect([a,b]).toContain(x)`) **only** when the API contract or specification explicitly allows multiple valid outcomes. Each multi-status case must be documented (see Section 2).

**Rule**: If you use `assertIn`, add a one-line comment explaining why each status is valid, and reference this document or the specific section.

---

## 2. Intentional Multi-Status Cases

These are the documented cases where multiple HTTP status codes are valid. All other cases should use `assertEqual`.

### 2.1 Async / Long-Running Operations (200 vs 202)

| Scenario | Valid Statuses | Rationale |
|----------|----------------|-----------|
| Async job creation / trigger | 200, 202 | 200 = synchronous completion; 202 = accepted, processing async |
| Workflow trigger | 200, 202 | Same as above |

**Example**:

```python
# Async trigger: 200 = immediate; 202 = accepted for async processing
self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_202_ACCEPTED])
```

### 2.2 Health Endpoints (200 vs 503)

| Scenario | Valid Statuses | Rationale |
|----------|----------------|-----------|
| Main health `/health/` | 200, 503 | 200 = healthy; 503 = unhealthy (e.g. DB/Redis down) |
| Circuit breakers `/health/circuit-breakers/` | 200, 404, 500 | 200 = healthy; 404 = endpoint not implemented; 500 = error fetching downstream |

**Example**:

```python
# Health: 200 = healthy, 503 = unhealthy (dependency down)
self.assertIn(response.status_code, [200, 503])
```

### 2.3 Auth / Existence Checks (200 vs 401 vs 403)

| Scenario | Valid Statuses | Rationale |
|----------|----------------|-----------|
| API root / tenants / assets (may be public or protected) | 200, 401, 403 | Depends on endpoint configuration; 200 if public, 401/403 if protected |
| Login with empty body | 400, 401 | 400 = validation; 401 = auth rejection |

**Example**:

```python
# Endpoint may require auth or be public
self.assertIn(response.status_code, [200, 401, 403])
```

### 2.4 Validation / Business Logic (400 vs 404 vs 409)

| Scenario | Valid Statuses | Rationale |
|----------|----------------|-----------|
| Create with duplicate / conflict | 201, 400, 409 | 201 = created; 400 = validation; 409 = conflict |
| Update with invalid reference | 200, 400, 404 | 200 = success; 400 = validation; 404 = resource not found |
| Delete non-existent | 204, 404 | 204 = deleted; 404 = already gone |

**Example**:

```python
# Create: 201 = success, 400 = validation error
self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])
```

### 2.5 Optional / External Service Integration (200 vs 404 vs 503 vs 500)

| Scenario | Valid Statuses | Rationale |
|----------|----------------|-----------|
| Circuit breaker / downstream health | 200, 404, 500 | 200 = healthy; 404 = not implemented; 500 = downstream error |
| DQ/Compliance run when service down | 400, 503 | 400 = validation (e.g. invalid asset); 503 = service unavailable |
| ML/ODH inference (optional service) | 200, 400, 404, 405, 503, 500 | Service may be down (503), not implemented (404), or return validation (400) |

**Note**: For ML/ODH, 500 is acceptable only when the test explicitly documents that circuit breakers or downstream failures can return 500. See [test_health_integration.py](../tests/integration/test_health_integration.py) and [test_odh_integration_comprehensive_validation.py](../hub/apps/ml/tests/test_odh_integration_comprehensive_validation.py) for existing patterns.

### 2.6 File Storage (init, download, delete)

| Scenario | Valid Statuses | Rationale |
|----------|----------------|-----------|
| Init upload (POST /api/v1/files/init/) | 201, 400, 500, 503 | 201 = success; 400 = validation; 503 = S3 unavailable; 500 = internal error |
| Download (file exists, ACTIVE) | 200, 404, 500, 503 | 200 = success; 404 = tenant isolation; 503 = S3 unavailable; 500 = internal |
| Download (deleted file) | 400 | can_download() = False → 400 |
| Delete | 200, 204, 404 | 200/204 = success; 404 = not found |
| Unauthorized | 401 | Single expected |

See [test_file_storage_operations_comprehensive.py](../tests/integration/test_file_storage_operations_comprehensive.py) for implementation.

---

## 3. Anti-Patterns (Do Not Use)

| Anti-Pattern | Problem | Correct Approach |
|--------------|---------|------------------|
| `assertIn(status, [200, 401])` for auth test | Masks auth bypass (200 when 401 expected) | `assertEqual(401)` |
| `assertIn(status, [400, 500])` for validation test | Masks server bug (500) | `assertEqual(400)` |
| `assertIn(status, [200, 403])` for permission test | Masks wrong behavior | Use `assertEqual` for the expected case |
| Multi-status without comment | Future readers cannot verify | Add comment: `# 200/202: async; see TEST_ASSERTION_CONVENTIONS` |
| Broad assertIn (e.g. [200, 201, 400, 404, 500, 503]) | Hides real failures | Narrow to documented valid set; fail on unexpected |

---

## 4. Adding New Multi-Status Cases

When introducing a new `assertIn` with multiple statuses:

1. Add a row to Section 2 (Intentional Multi-Status Cases) with scenario, valid statuses, and rationale.
2. Add a one-line comment at the assertion site: `# 200/202: async; see docs/TEST_ASSERTION_CONVENTIONS.md`.
3. Ensure the rationale is defensible (API contract or spec allows it).

---

## 5. References

- [E2E_TEST_SEMANTICS.md](E2E_TEST_SEMANTICS.md) — Strict vs environment-dependent vs deferred
- [E2E_ENVIRONMENT_REQUIREMENTS.md](E2E_ENVIRONMENT_REQUIREMENTS.md) — Service availability
- [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md) — Test execution

---

## 6. Frontend Real-API Integration Tests (Task 7.10)

### 6.1 Decision and Rationale

**Decision**: Critical frontend flows (auth, assets, contracts, marketplace) use **real API integration tests** instead of axios mocks. Tests run against a live backend (docker compose up).

**Rationale**:

- Axios mocks hide integration bugs (wrong URLs, auth headers, error handling).
- Real API tests validate end-to-end behavior: client → API → backend.
- Aligns with project rule: no mocks/stubs; fix root cause.
- E2E tests already use real backend; integration tests extend that coverage at the service/hook level.

### 6.2 How to Run

```bash
cd frontend && npm run test:integration:api
```

**Prerequisites**: Backend running (`docker compose -f docker-compose.test.yml up -d` or dev stack). E2E users: `docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`.

### 6.3 Script and Conventions

- **Script**: `test:integration:api` invokes `scripts/run-integration-api-tests.sh`, which auto-detects API port (8000/8001), sets `VITE_API_BASE_URL`, and runs `vitest --run src/integration/`.
- **Test files**: `frontend/src/integration/*.integration.test.ts`.
- **Assertions**: Use `expect(response.status).toBe(200)` (or appropriate status) per Section 1; avoid broad `assertIn` for auth/validation.

### 6.4 Migration Plan

See [FRONTEND_INTEGRATION_API_MIGRATION_PLAN.md](FRONTEND_INTEGRATION_API_MIGRATION_PLAN.md) for order (auth → assets → contracts → marketplace), environment requirements, and layout.
