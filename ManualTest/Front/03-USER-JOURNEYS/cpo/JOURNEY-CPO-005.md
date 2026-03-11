# JOURNEY-CPO-005: Generate Compliance Report

**Journey ID**: JOURNEY-CPO-005  
**Title**: Generate Compliance Report  
**Persona**: Compliance Officer  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Compliance Officer** (e2e_cpo@example.com / TestPass123)
- [ ] Compliance runs exist

---

## What You Will Do

Generate compliance report. Export or download. Review report content.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to compliance | Go to **Compliance** (sidebar). | Compliance page | ☐ |
| 2 | Generate report | Click **Generate Report** or **Export**. Select scope (asset, date range). | Report generated | ☐ |
| 3 | Download | Download report (PDF, CSV, etc.). | File downloaded | ☐ |
| 4 | Review | Open report. Verify content. | Report contains expected data | ☐ |

---

## Success Criteria

- Report generated
- File downloadable
- Content valid

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/cpo/JOURNEY-CPO-005.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
