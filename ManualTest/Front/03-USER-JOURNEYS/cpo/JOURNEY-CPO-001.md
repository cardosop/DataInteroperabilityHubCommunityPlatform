# JOURNEY-CPO-001: Review Compliance for Asset

**Journey ID**: JOURNEY-CPO-001  
**Title**: Review Compliance for Asset  
**Persona**: Compliance Officer  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-cpo-001-review-compliance-for-asset)

---

## Prerequisites

- [ ] Logged in as **Compliance Officer** (e2e_cpo@example.com / TestPass123)
- [ ] At least one asset with compliance runs (run DPO-001 or compliance scan first)

---

## What You Will Do

Review compliance status and details for an asset. View compliance section, status, and optionally generate a report.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to asset | Go to **Assets** → select an asset. | Asset detail page | ☐ |
| 2 | Open compliance section | Find **Compliance** tab or section on asset detail. | Compliance section visible | ☐ |
| 3 | Review status | View compliance status (pass/fail/pending). | Status displayed | ☐ |
| 4 | Review details | Expand or view compliance run details (rules, findings). | Details visible | ☐ |
| 5 | Generate report (if available) | Click **Generate Report** or export. | Report generated or downloaded | ☐ |

---

## Success Criteria

- Compliance section accessible
- Status and details visible
- Report generation works (if available)

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/cpo/JOURNEY-CPO-001.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
