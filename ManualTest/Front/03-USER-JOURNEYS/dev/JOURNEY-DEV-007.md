# JOURNEY-DEV-007: Build Custom Connector

**Journey ID**: JOURNEY-DEV-007  
**Title**: Build Custom Connector  
**Persona**: External Developer  
**Priority**: Medium  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dev-007-build-custom-connector-new)

---

## Prerequisites

- [ ] Logged in as **External Developer** (e2e_developer@example.com / TestPass123)
- [ ] Custom connector capability enabled

---

## What You Will Do

Create custom connector. Implement interface. Test. Deploy.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to connectors | Go to **Integrations** → **Connectors**. | Connectors page | ☐ |
| 2 | Create custom | Click **Create Custom Connector**. | Create form | ☐ |
| 3 | Configure | Define connector (type, config schema). | Connector configured | ☐ |
| 4 | Test | Test connector. | Test passes | ☐ |
| 5 | Deploy | Publish connector. | Connector deployed | ☐ |

---

## Success Criteria

- Connector created
- Test passes
- Connector deployed

---

## Note

If custom connector is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dev/JOURNEY-DEV-007.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
