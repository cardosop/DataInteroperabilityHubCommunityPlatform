# JOURNEY-AUD-002: Export Audit Report

**Journey ID**: JOURNEY-AUD-002  
**Title**: Export Audit Report  
**Persona**: Auditor  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Auditor** (e2e_auditor@example.com / TestPass123)
- [ ] Audit logs exist

---

## What You Will Do

Export audit report. Select date range, format. Download.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to audit | Go to **Audit** (sidebar). | Audit page | ☐ |
| 2 | Export | Click **Export** or **Generate Report**. | Export options | ☐ |
| 3 | Select range | Choose date range. Select format (CSV, PDF). | Options selected | ☐ |
| 4 | Download | Export. | File downloaded | ☐ |
| 5 | Verify | Open file. Verify content. | Content valid | ☐ |

---

## Success Criteria

- Export works
- File downloaded
- Content valid

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/aud/JOURNEY-AUD-002.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
