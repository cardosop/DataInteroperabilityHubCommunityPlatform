# E2E Dual Verification Audit

**Date**: 2026-02-27  
**Purpose**: Audit all frontend E2E assertions for dual verification (backend + frontend) to reduce false positives.  
**Helper**: `assertSuccessfulLoad()` in `frontend/e2e/fixtures/helpers.ts`

---

## Executive Summary

| Category | Count | Status |
|----------|-------|--------|
| **Using assertSuccessfulLoad** | 3 tests | ✅ Dual verification |
| **Success tests with false-positive risk** | ~80+ tests | ⚠️ Need migration |
| **Failure tests** (expect error) | ~40+ tests | ✅ Correct pattern |
| **Edge/redirect tests** | ~50+ tests | ⚠️ Context-dependent |

**Conclusion**: Only **3 of ~642** E2E tests use dual verification. The majority of success tests use `hasContent = success OR error-display`, which **passes when the frontend shows an error** (false positive).

---

## 1. Tests Already Using assertSuccessfulLoad ✅

| File | Test | API Pattern |
|------|------|-------------|
| `journeys/contracts-odps/contracts-odps-routes.spec.ts` | contracts list loads | `/contracts` GET |
| `journeys/contracts-odps/contracts-odps-routes.spec.ts` | odps list loads | `/contracts` GET |
| `journeys/contracts-odps/contracts-odps-routes.spec.ts` | odps upload page loads | (frontend only) |

---

## 2. Success Tests with False-Positive Risk ⚠️

These tests use `hasContent = successSelector OR .error-display OR .empty-state` and `expect(hasContent).toBe(true)`. They **pass when the page shows an error**.

### Route specs (high priority — list/detail loads)

| File | Test(s) | Current Pattern |
|------|---------|-----------------|
| `marketplace-dc/marketplace-dc-routes.spec.ts` | marketplace orders list loads, entitlements list loads | `hasContent = order-list OR error-display OR empty-state` |
| `marketplace-dc/marketplace-dc-routes.spec.ts` | marketplace list loads (discover) | waitForSelector includes error-display |
| `dq-compliance-governance/dq-compliance-governance-routes.spec.ts` | dq list, compliance list, governance page | `hasContent` includes error-display |
| `mesh-virtualization-search-ai/mesh-search-ai-routes.spec.ts` | virtualization list loads | `hasContent` includes error-display |
| `integrations-jobs-webhooks/integrations-jobs-webhooks-routes.spec.ts` | connections list, mappings list, sync-jobs list | `hasContent` includes error-display |
| `admin-audit-settings/admin-audit-settings-routes.spec.ts` | admin, audit, settings sessions, api-keys, etc. | `hasContent` or no API check |

### Journey specs (medium priority)

| File | Test(s) |
|------|---------|
| `dpo/JOURNEY-DPO-003.spec.ts` | assets list loads |
| `dpo/JOURNEY-DPO-004.spec.ts` | DQ list loads |
| `dpo/JOURNEY-DPO-005.spec.ts` | contracts list loads |
| `dpo/JOURNEY-DPO-006.spec.ts` | marketplace listings loads |
| `dc/JOURNEY-DC-001.spec.ts` | marketplace, orders |
| `dc/JOURNEY-DC-003.spec.ts` | purchase flow |
| `dc/JOURNEY-DC-004.spec.ts` | entitlements |
| `dc/JOURNEY-DC-005.spec.ts` | contract view |
| `dc/JOURNEY-DC-010.spec.ts` | governance |
| `dc/JOURNEY-DC-011.spec.ts` | access request |
| `dc/JOURNEY-DC-013.spec.ts` | download |
| `de/JOURNEY-DE-001.spec.ts` | contracts list |
| `de/JOURNEY-DE-002.spec.ts` | ODPS list |
| `de/JOURNEY-DE-009.spec.ts` | sync jobs |
| `de/JOURNEY-DE-013.spec.ts` | mappings |
| `ta/JOURNEY-TA-001.spec.ts` | admin users |
| `ta/JOURNEY-TA-005.spec.ts` | tenants |
| `pa/JOURNEY-PA-001.spec.ts` | platform admin |
| `aud/JOURNEY-AUD-001.spec.ts` | audit list |
| `aud/JOURNEY-AUD-002.spec.ts` | audit filters |
| `aud/JOURNEY-AUD-006.spec.ts` | audit export |
| `cpo/JOURNEY-CPO-001.spec.ts` | compliance list |
| `cpo/JOURNEY-CPO-009.spec.ts` | governance retention |
| `dev/JOURNEY-DEV-001.spec.ts` | developer page |
| `dev/JOURNEY-DEV-004.spec.ts` | webhooks |
| `da/JOURNEY-DA-002.spec.ts` | datasets |
| `da/JOURNEY-DA-003.spec.ts` | analytics |
| `dmo/JOURNEY-DMO-005.spec.ts` | mesh topology |
| `ds/JOURNEY-DS-005.spec.ts` | semantic |
| `dpo/JOURNEY-DPO-013.spec.ts` | ODPS export |
| `marketplace/JOURNEY-MP-004.spec.ts` | listing detail |
| `marketplace/JOURNEY-MP-005.spec.ts` | purchase |
| `marketplace/JOURNEY-MP-006.spec.ts` | entitlements |

### Feature specs

| File | Test(s) |
|------|---------|
| `features/observability.spec.ts` | observability page loads |
| `phase8-hardening.spec.ts` | multiple route load tests |

### Dimension specs (failure/edge scenarios — different semantics)

| File | Test(s) | Note |
|------|---------|------|
| `dimensions/network-failures.spec.ts` | assets list after offline | Tests error handling; `hasContent` includes error intentionally |
| `dimensions/concurrent-operations.spec.ts` | double submit | Tests race; error may be expected |
| `dimensions/timeout-handling.spec.ts` | slow API | Tests timeout; error may be expected |

---

## 3. Failure Tests ✅ (Correct Pattern)

These expect `hasError` or `noSuccessContent` — they are testing failure scenarios and are correct:

- `contracts-odps-routes`: contract edit with non-existent id, odps detail with non-existent id
- `marketplace-dc-routes`: listing detail with non-existent id
- `dq-compliance-governance-routes`: dq run detail, compliance run detail with non-existent id
- `integrations-jobs-webhooks-routes`: connection detail with non-existent id
- `alternate-flows-failure`: asset create with duplicate key
- Various journey failure scenarios (JOURNEY-DPO-014, DC-003, DE-014, etc.)

---

## 4. Edge/Redirect Tests (Context-Dependent)

Tests that expect multiple valid outcomes (login redirect, 403, success) — dual verification applies only when success is the expected path:

- `auth.spec.ts`: public page, login redirect
- `404-403-session.spec.ts`: landing, 404, 403
- `governance-retention-crud.spec.ts`: role-gated (403 or success)
- `JOURNEY-DC-014.spec.ts`: semantic unavailable
- `JOURNEY-CPO-007`, `CPO-010`: audit/governance with/without role

For these, use `assertSuccessfulLoad` only in the success branch when the test expects success.

---

## 5. Migration Priority

### Phase 1 — Route specs (fastest impact)

1. `marketplace-dc-routes.spec.ts` — 3 success tests
2. `dq-compliance-governance-routes.spec.ts` — 3 success tests
3. `mesh-virtualization-search-ai-routes.spec.ts` — success tests
4. `integrations-jobs-webhooks-routes.spec.ts` — 3 success tests
5. `admin-audit-settings-routes.spec.ts` — success tests

### Phase 2 — Journey specs (by batch)

- Batch 3: DPO journeys (JOURNEY-DPO-003, 004, 005, 006, 013)
- Batch 4: DC, DE journeys
- Batch 5: TA, PA, Aud, Dev
- Batch 6: CPO, DS, DMO, DA, CM, Marketplace

### Phase 3 — Features and phase specs

- `features/*.spec.ts` list-load tests
- `phase7.5-features-gap-closure.spec.ts`
- `phase8-hardening.spec.ts`

---

## 6. Migration Pattern

For each success test that loads a list/detail page:

```typescript
// Before (false positive risk)
const hasContent =
  (await page.locator('.contract-list-page').count()) > 0 ||
  (await page.locator('.error-display').count()) > 0 ||
  (await page.locator('.empty-state').count()) > 0;
expect(hasContent).toBe(true);

// After (dual verification)
const apiPromise = page.waitForResponse(
  (r) => r.url().includes('/contracts') && r.request().method() === 'GET',
  { timeout: 60000 }
);
await page.goto('/contracts');
await waitForAppMainReady(page, { ... });
await assertSuccessfulLoad(page, {
  apiResponsePromise: apiPromise,
  successContentSelector: '.contract-list-page, .empty-state',
  rejectErrorDisplay: true,
});
```

For pages that don't trigger a list API (e.g. form pages), use frontend-only verification:

```typescript
await assertSuccessfulLoad(page, {
  successContentSelector: '.odps-upload-page',
  rejectErrorDisplay: true,
});
```

---

## 7. References

- `frontend/e2e/fixtures/helpers.ts` — `assertSuccessfulLoad()` JSDoc
- `frontend/e2e/journeys/contracts-odps/contracts-odps-routes.spec.ts` — reference implementation
- `docs/TEST_EXECUTION_PLAN.md` — dual verification section
- `frontend/e2e/TEST_GENERATION_GUIDE.md` — helper usage
