# JOURNEY-AUD-003: Review Compliance Audit

**Journey ID**: JOURNEY-AUD-003  
**Title**: Review Compliance Audit  
**Persona**: Auditor  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Auditor** (e2e_auditor@example.com / TestPass123)
- [ ] Compliance runs exist

---

## What You Will Do

View compliance audit trail. Review compliance run history. Check findings.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to audit/compliance | Go to **Audit** → **Compliance** or **Compliance** → **Audit**. | Compliance audit page | ☐ |
| 2 | View runs | Browse compliance run history. | Runs displayed | ☐ |
| 3 | Open run | Click a run. View findings. | Run detail visible | ☐ |
| 4 | Verify | Audit trail complete. | Trail complete | ☐ |

---

## Success Criteria

- Compliance audit accessible
- Run history visible
- Findings reviewable

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/aud/JOURNEY-AUD-003.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
