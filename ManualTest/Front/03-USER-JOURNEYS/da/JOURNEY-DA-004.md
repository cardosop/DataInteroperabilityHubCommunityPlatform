# JOURNEY-DA-004: Execute Federated Query

**Journey ID**: JOURNEY-DA-004  
**Title**: Execute Federated Query  
**Persona**: Data Analyst  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-da-004-execute-federated-query)

---

## Prerequisites

- [ ] Logged in as **Data Analyst** (e2e_consumer@example.com / TestPass123)
- [ ] Federated query capability enabled
- [ ] Federated sources configured

---

## What You Will Do

Build federated query across sources. Execute. Review results. Export.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to federated query | Go to **Virtualization** or **Federated Query**. | Query page | ☐ |
| 2 | Select sources | Choose federated sources. | Sources selected | ☐ |
| 3 | Build query | Write SQL or use builder. | Query built | ☐ |
| 4 | Execute | Run query. | Results returned | ☐ |
| 5 | Export | Export results. | File downloaded | ☐ |

---

## Success Criteria

- Federated query works
- Results returned
- Export works

---

## Note

If federated query is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/da/JOURNEY-DA-004.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
