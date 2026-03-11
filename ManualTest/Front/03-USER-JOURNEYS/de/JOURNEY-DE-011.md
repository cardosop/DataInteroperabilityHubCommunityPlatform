# JOURNEY-DE-011: Set Up Reverse ETL

**Journey ID**: JOURNEY-DE-011  
**Title**: Set Up Reverse ETL  
**Persona**: Data Engineer  
**Priority**: Medium  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-de-011-set-up-reverse-etl-new)

---

## Prerequisites

- [ ] Logged in as **Data Engineer** (e2e_test@example.com or e2e_admin@example.com / TestPass123)
- [ ] Reverse ETL capability enabled

---

## What You Will Do

Select data source. Configure destination (CRM, marketing). Map fields. Set schedule. Test.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to reverse ETL | Go to **Integrations** → **Reverse ETL** or equivalent. | Reverse ETL page | ☐ |
| 2 | Select source | Choose data source (asset, dataset). | Source selected | ☐ |
| 3 | Configure destination | Set destination (CRM, marketing platform). | Destination configured | ☐ |
| 4 | Map fields | Map source fields to destination. | Mapping complete | ☐ |
| 5 | Set schedule | Configure run schedule. | Schedule set | ☐ |
| 6 | Test | Run test. | Test succeeds | ☐ |

---

## Success Criteria

- Reverse ETL configured
- Mapping complete
- Test succeeds

---

## Note

If reverse ETL is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/de/JOURNEY-DE-011.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
