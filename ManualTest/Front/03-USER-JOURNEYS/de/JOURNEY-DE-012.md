# JOURNEY-DE-012: Create Custom Plugin

**Journey ID**: JOURNEY-DE-012  
**Title**: Create Custom Plugin  
**Persona**: Data Engineer  
**Priority**: Medium  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-de-012-create-custom-plugin-new)

---

## Prerequisites

- [ ] Logged in as **Data Engineer** (e2e_test@example.com or e2e_admin@example.com / TestPass123)
- [ ] Plugin system enabled

---

## What You Will Do

Design plugin (connector, transformation, quality). Implement interface. Test and deploy.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to plugins | Go to **Plugins** or **Developer** → **Plugins**. | Plugin page | ☐ |
| 2 | Create plugin | Click **Create Plugin**. Select type. | Plugin form | ☐ |
| 3 | Implement | Configure plugin (code, config). | Plugin configured | ☐ |
| 4 | Test | Run plugin test. | Test passes | ☐ |
| 5 | Deploy | Publish plugin. | Plugin deployed | ☐ |

---

## Success Criteria

- Plugin created
- Test passes
- Plugin deployed

---

## Note

If plugin system is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/de/JOURNEY-DE-012.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
