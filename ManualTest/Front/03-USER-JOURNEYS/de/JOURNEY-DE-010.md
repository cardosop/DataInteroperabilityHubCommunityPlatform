# JOURNEY-DE-010: Configure Connector for Data Source

**Journey ID**: JOURNEY-DE-010  
**Title**: Configure Connector for Data Source  
**Persona**: Data Engineer  
**Priority**: High  
**Estimated Duration**: 15 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-de-010-configure-connector-for-data-source-new)

---

## Prerequisites

- [ ] Logged in as **Data Engineer** (e2e_test@example.com or e2e_admin@example.com / TestPass123)
- [ ] Connector marketplace or custom connector capability

---

## What You Will Do

Browse connectors. Install and configure connector. Test connection. Deploy.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to connectors | Go to **Integrations** → **Connectors**. | Connector list | ☐ |
| 2 | Select connector | Choose pre-built or create custom. | Connector selected | ☐ |
| 3 | Install | Install connector if needed. | Connector installed | ☐ |
| 4 | Configure | Set credentials, URL, settings. | Configuration saved | ☐ |
| 5 | Test | Test connection. | Test passes | ☐ |
| 6 | Deploy | Activate connector. | Connector deployed | ☐ |

---

## Success Criteria

- Connector configured
- Test passes
- Connector deployed

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/de/JOURNEY-DE-010.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
