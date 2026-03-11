# JOURNEY-DE-002: Set Up Scheduled Ingestion

**Journey ID**: JOURNEY-DE-002  
**Title**: Set Up Scheduled Ingestion  
**Persona**: Data Engineer  
**Priority**: High  
**Estimated Duration**: 15 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Data Engineer** (e2e_test@example.com or e2e_admin@example.com / TestPass123)
- [ ] Scheduled ingestion capability enabled (Prefect workers)

---

## What You Will Do

Configure a scheduled ingestion job. Set source, schedule, and target. Verify job runs.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to scheduled ingestions | Go to **Jobs** or **Scheduled Ingestion** (sidebar). | Ingestion page | ☐ |
| 2 | Create ingestion | Click **Create** or **New Ingestion**. | Create form | ☐ |
| 3 | Configure source | Select data source (file, API, DB). | Source configured | ☐ |
| 4 | Configure schedule | Set cron or interval. | Schedule set | ☐ |
| 5 | Configure target | Select asset/dataset. | Target configured | ☐ |
| 6 | Save | Submit. | Ingestion created | ☐ |
| 7 | Verify run | Wait for or trigger run. Check run status. | Run executes | ☐ |

---

## Success Criteria

- Ingestion created
- Schedule configured
- Run executes (or triggers)

---

## Note

If scheduled ingestion is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/de/JOURNEY-DE-002.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
