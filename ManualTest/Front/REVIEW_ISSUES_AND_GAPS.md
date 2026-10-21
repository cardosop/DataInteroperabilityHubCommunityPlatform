# Manual Test Tutorial — Review: Issues and Gaps

**Review Date**: 2026-02-17  
**Status**: Fixes applied where indicated below.

---

## Summary

| Category | Count |
|----------|-------|
| Issues (fixed) | 5 |
| Gaps (addressed) | 3 |
| Minor / optional | 3 |

---

## Issues (Should Fix)

### 1. **05-SUPPORT-MATERIAL/README.md — Incorrect paths**

Paths use `../../tests/` which resolves to `ManualTest/tests/` (nonexistent). Tests live at repo root.

**Fix**: ✅ Applied — Use repo-root-relative paths: `tests/fixtures/odps/v4.1/valid/` (consistent with 00-PREREQUISITES.md).

---

### 2. **DPO persona — Wrong E2E spec for JOURNEY-DPO-002**

JOURNEY-DPO-002 "Publish Asset to Marketplace" is mapped to `asset-activation-flow.spec.ts`, but there is a dedicated `JOURNEY-DPO-002.spec.ts`. `asset-activation-flow` is for activation within DPO-001.

**Fix**: ✅ Applied — Map JOURNEY-DPO-002 to `journeys/dpo/JOURNEY-DPO-002.spec.ts`.

---

### 3. **DPO persona — Missing E2E specs for DPO-004 and DPO-006**

DPO-004 and DPO-006 are marked "—" but `JOURNEY-DPO-004.spec.ts` and `JOURNEY-DPO-006.spec.ts` exist.

**Fix**: ✅ Applied — Add `journeys/dpo/JOURNEY-DPO-004.spec.ts` and `journeys/dpo/JOURNEY-DPO-006.spec.ts`.

---

### 4. **07-TRACEABILITY — UC-AUTH-002 E2E spec**

UC-AUTH-002 and JOURNEY-AUTH-002 reference `JOURNEY-AUTH-001.spec.ts` for login. A dedicated `JOURNEY-AUTH-002.spec.ts` exists.

**Fix**: ✅ Applied — Add `journeys/auth/JOURNEY-AUTH-002.spec.ts` to the E2E spec list for UC-AUTH-002 and JOURNEY-AUTH-002.

---

### 5. **alternate-flows.md — E2E spec path**

Traceability line says `frontend/e2e/cross-cutting/404-403-session.spec.ts`. Path is correct; consider adding "from repo root" for clarity.

---

### 6. **ensure_e2e_subscription — Developer and DMO users**

`ensure_e2e_subscription` does not include `e2e_developer@example.com` or `e2e_dmo@example.com`. If DEV/DMO personas create assets or perform subscription-gated actions, they may hit 403.

**Fix**: ✅ Applied — Document in test-users.md that e2e_developer and e2e_dmo are not in ensure_e2e_subscription and may hit 403 for asset creation.

---

## Gaps (To Address)

### 1. **Coverage summary is misleading**

README says "~109 use cases" and "96 journeys" in 02-USE-CASES/ and 03-USER-JOURNEYS/, but only 4 auth use cases and 4 auth journeys have dedicated scripts. The rest are covered via persona scripts.

**Fix**: ✅ Applied — Clarify in README and 02/03 READMEs: "4 auth use cases have dedicated scripts; remaining ~105 covered via persona scripts" and "4 auth journeys have dedicated scripts; remaining 92 covered via persona scripts".

---

### 2. **Visitor vs main script execution order**

- **01-TEST-EXECUTION-SCRIPT**: AUTH-001 → 002 → 003 → 004
- **visitor.md**: AUTH-004 → 001 → 002 → 003 (public first, then register, login, reset)

**Fix**: ✅ Applied — Main script now matches visitor: AUTH-004 first (public resources), then 001, 002, 003.

---

### 3. **No standalone journey scripts for role-based journeys**

Only auth journeys (001–004) have standalone scripts in 03-USER-JOURNEYS/. Role-based journeys (DPO-001, DC-001, etc.) are only referenced from persona scripts. Manual testers cannot run a single journey without opening a persona script.

**Fix**: Optional — add 03-USER-JOURNEYS/dpo/, dc/, etc. with condensed journey scripts, or document that persona scripts are the entry point for role-based journeys.

---

### 4. **Password reset (JOURNEY-AUTH-003) — Mail/email dependency**

UC-AUTH-003 and JOURNEY-AUTH-003 require email delivery for reset links. If MailHog or similar is not configured, the journey cannot be completed.

**Fix**: ✅ Applied — Add note in JOURNEY-AUTH-003 prerequisites: "Email delivery configured (e.g. MailHog). If not configured, mark N/A."

---

### 5. **Doc links — Anchor verification**

Some links to docs (e.g. `TEST_TRACEABILITY.md#uc-auth-003-user-resets-password`) may not match exact anchors. TEST_TRACEABILITY uses `#### UC-AUTH-001` etc.; GitHub/Markdown anchors are typically lowercase with hyphens.

**Fix**: Spot-check anchors; most appear correct.

---

## Minor / Optional

### 1. **00-PREREQUISITES — Path context**

Support material paths (`tests/fixtures/...`) are repo-root-relative. Add: "Paths are relative to project root."

### 2. **Persona scripts — Incomplete doc links**

Some persona journey links use `[USER_JOURNEYS](../../docs/USER_JOURNEYS.md)` without a specific anchor. Adding anchors (e.g. `#journey-dpo-003-manage-asset-lifecycle`) would improve navigation.

### 3. **Release sign-off — Extended personas**

Release checklist only requires "Core Personas". Consider adding a note that extended personas (DEV, AUD, DS, DA, CM, DMO) can be run for full coverage.

---

## Recommended Fixes (Priority)

1. Fix 05-SUPPORT-MATERIAL paths (Issue 1)
2. Fix DPO persona E2E mappings (Issues 2, 3)
3. Update coverage summary in READMEs (Gap 1)
4. Document ensure_e2e_subscription scope for DEV/DMO (Issue 6)
5. Add password reset / MailHog note (Gap 4)
