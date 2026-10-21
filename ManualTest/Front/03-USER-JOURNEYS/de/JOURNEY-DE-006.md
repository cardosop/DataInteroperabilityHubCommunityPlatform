# JOURNEY-DE-006: Monitor Data Pipeline Health

**Journey ID**: JOURNEY-DE-006  
**Title**: Monitor Data Pipeline Health  
**Persona**: Data Engineer  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Data Engineer** (e2e_test@example.com or e2e_admin@example.com / TestPass123)
- [ ] At least one job/pipeline (ingestion, sync, DQ)

---

## What You Will Do

View job/pipeline status. Monitor health. Review run history.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to jobs | Go to **Jobs** or **Pipelines** (sidebar). | Jobs list | ☐ |
| 2 | View job status | Check status of jobs (running, completed, failed). | Status visible | ☐ |
| 3 | Open job detail | Click a job. | Job detail: config, runs | ☐ |
| 4 | View run history | Browse run history. | Runs listed | ☐ |
| 5 | Open run detail | Click a run. View logs, duration. | Run detail visible | ☐ |

---

## Success Criteria

- Jobs visible
- Status accurate
- Run history accessible

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/de/JOURNEY-DE-006.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
