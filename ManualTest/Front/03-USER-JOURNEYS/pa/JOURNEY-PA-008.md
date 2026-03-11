# JOURNEY-PA-008: Configure External Marketplace Connections

**Journey ID**: JOURNEY-PA-008  
**Title**: Configure External Marketplace Connections  
**Persona**: Platform Admin  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Platform Admin** (e2e_platform@example.com / TestPass123)
- [ ] External marketplace integration capability

---

## What You Will Do

Configure connection to external marketplace (e.g. CKAN). Set credentials. Test sync.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to integrations | Go to **Admin** → **Integrations** → **Marketplace**. | Integrations page | ☐ |
| 2 | Add connection | Add external marketplace (CKAN, etc.). | Connection form | ☐ |
| 3 | Configure | Enter URL, API key. | Config saved | ☐ |
| 4 | Test | Test connection. | Test passes | ☐ |
| 5 | Enable sync | Enable sync if available. | Sync configured | ☐ |

---

## Success Criteria

- Connection configured
- Test passes
- Sync (if available)

---

## Note

If external marketplace is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/pa/JOURNEY-MPA-008.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
