# JOURNEY-TA-008: Configure Integration Ecosystem

**Journey ID**: JOURNEY-TA-008  
**Title**: Configure Integration Ecosystem  
**Persona**: Tenant Admin  
**Priority**: High  
**Estimated Duration**: 15 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-ta-008-configure-integration-ecosystem-new)

---

## Prerequisites

- [ ] Logged in as **Tenant Admin** (e2e_admin@example.com / TestPass123)
- [ ] Integrations capability enabled

---

## What You Will Do

Install connectors. Configure connections. Create sync jobs. Test integrations.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to integrations | Go to **Integrations** (sidebar). | Integrations page | ☐ |
| 2 | Install connector | Browse connectors. Install one. | Connector installed | ☐ |
| 3 | Configure connection | Set credentials, URL. Test. | Connection configured | ☐ |
| 4 | Create sync job | Create sync job from connection. | Sync job created | ☐ |
| 5 | Test | Run sync. | Sync executes | ☐ |
| 6 | Monitor | View integration health. | Health visible | ☐ |

---

## Success Criteria

- Connector installed
- Connection configured
- Sync job works

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/ta/JOURNEY-TA-008.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
