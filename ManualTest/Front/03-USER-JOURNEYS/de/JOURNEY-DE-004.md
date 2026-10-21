# JOURNEY-DE-004: Set Up Compliance Scanning

**Journey ID**: JOURNEY-DE-004  
**Title**: Set Up Compliance Scanning  
**Persona**: Data Engineer  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Data Engineer** (e2e_test@example.com or e2e_admin@example.com / TestPass123)
- [ ] At least one asset to scan

---

## What You Will Do

Configure compliance scanning for assets. Run scan and review results.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to compliance | Go to **Compliance** (sidebar). | Compliance page | ☐ |
| 2 | Configure scan | Select asset(s), set scan rules or profile. | Scan configured | ☐ |
| 3 | Run scan | Start compliance run. | Run starts | ☐ |
| 4 | Monitor | View run status. | Status updates | ☐ |
| 5 | Review results | Open run detail. View pass/fail, findings. | Results displayed | ☐ |

---

## Success Criteria

- Scan configured
- Run executes
- Results visible

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/de/JOURNEY-DE-004.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
