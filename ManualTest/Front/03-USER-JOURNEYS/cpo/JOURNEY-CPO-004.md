# JOURNEY-CPO-004: Run Compliance Scan

**Journey ID**: JOURNEY-CPO-004  
**Title**: Run Compliance Scan  
**Persona**: Compliance Officer  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Compliance Officer** (e2e_cpo@example.com / TestPass123)
- [ ] At least one asset to scan

---

## What You Will Do

Run a compliance scan on an asset. Monitor the run and review results.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to compliance | Go to **Compliance** (sidebar). | Compliance page loads | ☐ |
| 2 | Start scan | Click **Run Scan** or **New Scan**. Select asset/dataset/file via **AssetPicker**, **DatasetPicker**, **FilePicker** (searchable dropdowns; cascading). | Scan starts; run created | ☐ |
| 3 | Monitor progress | View run status (pending, running, completed). | Status updates | ☐ |
| 4 | Review results | Open run detail when complete. View pass/fail, findings. | Results displayed | ☐ |

---

## Success Criteria

- Scan starts successfully
- Run completes (or fails with clear error)
- Results visible

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/cpo/JOURNEY-CPO-004.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
