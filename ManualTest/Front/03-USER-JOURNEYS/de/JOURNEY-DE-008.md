# JOURNEY-DE-008: Integrate AI Schema Matching into Workflow

**Journey ID**: JOURNEY-DE-008  
**Title**: Integrate AI Schema Matching into Workflow  
**Persona**: Data Engineer  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-de-008-integrate-ai-schema-matching-into-workflow-new)

---

## Prerequisites

- [ ] Logged in as **Data Engineer** (e2e_test@example.com or e2e_admin@example.com / TestPass123)
- [ ] AI schema matching capability enabled

---

## What You Will Do

Configure AI schema matching in workflow. Test schema matching API. Deploy and monitor.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to workflow/config | Go to **Integrations** or **AI** configuration. | Config page | ☐ |
| 2 | Configure AI service | Set AI service connection (endpoint, key). | Service configured | ☐ |
| 3 | Test schema matching | Trigger schema matching with sample schema. | Mappings returned | ☐ |
| 4 | Configure acceptance rules | Set mapping acceptance thresholds. | Rules saved | ☐ |
| 5 | Deploy | Save and deploy. | Configuration active | ☐ |

---

## Success Criteria

- AI service connected
- Schema matching works
- Configuration deployed

---

## Note

If AI schema matching is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/de/JOURNEY-DE-008.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
