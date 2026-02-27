# Frontend Integration API Migration Plan

**Task**: 7.10 — Replace axios mocks in frontend unit tests with real API integration tests  
**Last Updated**: 2026-02-19  
**Related**: [TEST_ASSERTION_CONVENTIONS.md](TEST_ASSERTION_CONVENTIONS.md), [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md)

---

## 1. Overview

Critical frontend flows (auth, assets, contracts, marketplace) currently use axios mocks in unit tests. This plan migrates those tests to **real API integration tests** that run against a live backend. No mocks or stubs; root-cause validation only.

---

## 2. Migration Order (by Criticality)

| Priority | Flow       | Current State                                      | Target State                                      |
|----------|------------|----------------------------------------------------|---------------------------------------------------|
| 1        | **Auth**   | `authService.test.ts`, `LoginPage.test.tsx` — axios mocks | Real API integration tests (`auth.integration.test.ts`) |
| 2        | **Assets** | `assetService.test.ts`, `useAssets.test.tsx` — axios mocks | Real API integration tests (`assets.integration.test.ts`) |
| 3        | **Contracts** | `contractService.test.ts`, `useContracts.test.tsx` — axios mocks | Real API integration tests (`contracts.integration.test.ts`) |
| 4        | **Marketplace** | No unit tests; services exist (`listingService`, `orderService`, `entitlementService`) | Real API integration tests (`marketplace.integration.test.ts`) |

**Removed (replaced by integration tests)**: `authService.test.ts`, `assetService.test.ts`, `contractService.test.ts`, `useAssets.test.tsx`, `useContracts.test.tsx`, `LoginPage.test.tsx` — all used axios mocks; coverage now via `src/integration/*.integration.test.ts` and E2E.

---

## 3. How to Run

### 3.1 Prerequisites

- Backend running (API at port 8000 or 8001)
- E2E test user: `e2e_test@example.com` / `TestPass123` (created by `ensure_e2e_user_roles` or `ensure_e2e_subscription`)
- Run `docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles` (or equivalent for dev stack) before first run

### 3.2 Commands

| Command | Description |
|---------|-------------|
| `cd frontend && npm run test:integration:api` | Auto-detect backend (8000/8001), set `VITE_API_BASE_URL`, run integration tests |
| `VITE_API_BASE_URL=http://localhost:8001/api/v1 npx vitest run --config vitest.integration.config.ts` | Explicit API URL (e.g. for CI) |

### 3.3 Script Behavior

`scripts/run-integration-api-tests.sh`:

1. Detects backend at port 8000 (dev) or 8001 (test)
2. Sets `VITE_API_BASE_URL` and exports for Vitest
3. Optionally runs `ensure_e2e_user_roles` when using test stack
4. Runs `vitest --run` with `src/integration/**/*.integration.test.ts`
5. Exits 1 if backend not found or tests fail

---

## 4. Environment Requirements

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_BASE_URL` | No (auto-detected) | `http://localhost:8000/api/v1` or `http://localhost:8001/api/v1` | Full API base URL |
| Backend | Yes | — | `docker compose up` (dev or test) |
| E2E users | Yes | — | `ensure_e2e_user_roles` run once per stack |

---

## 5. Test File Layout

```
frontend/src/integration/
├── auth.integration.test.ts        # Auth: login, logout, refresh, me
├── assets.integration.test.ts     # Assets: list, get, create, update, delete
├── contracts.integration.test.ts  # Contracts: list, get, create, validate
└── marketplace.integration.test.ts # Marketplace: listings, orders (if endpoints exist)
```

---

## 6. What Stays as Unit Tests

- Pure logic (no HTTP): error handling, data transformation, validation helpers
- Components that only need store/context (no API): keep unit tests with store mocks only where necessary
- Tests that assert UI behavior without API: keep if they don't mock axios

---

## 7. References

- [TEST_ASSERTION_CONVENTIONS.md](TEST_ASSERTION_CONVENTIONS.md) — Section 6: Frontend real-API integration tests
- [E2E_ENVIRONMENT_REQUIREMENTS.md](E2E_ENVIRONMENT_REQUIREMENTS.md) — Service availability
- [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md) — Phase 12A.2.1, 12A.2.2
