# JOURNEY-DE-005: Integrate External Data Source

**Journey ID**: JOURNEY-DE-005  
**Title**: Integrate External Data Source  
**Persona**: Data Engineer  
**Priority**: High  
**Estimated Duration**: 15 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Data Engineer** (e2e_test@example.com or e2e_admin@example.com / TestPass123)
- [ ] Integrations/connectors capability enabled

---

## What You Will Do

Configure connection to external data source. Test connection. Create sync or ingestion from source.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to integrations | Go to **Integrations** → **Connections** or **Connectors**. | Integrations page | ☐ |
| 2 | Create connection | Click **Add Connection**. Select connector type. | Connection form | ☐ |
| 3 | Configure credentials | Enter URL, credentials, settings. | Credentials configured | ☐ |
| 4 | Test connection | Click **Test**. | Connection succeeds | ☐ |
| 5 | Save | Submit. | Connection created | ☐ |
| 6 | Create sync (if available) | Create sync job or ingestion from connection. | Sync configured | ☐ |

---

## Success Criteria

- Connection created
- Test passes
- Sync/ingestion configurable (if available)

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/de/JOURNEY-DE-005.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
