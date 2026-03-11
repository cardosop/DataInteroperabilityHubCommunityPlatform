# JOURNEY-CM-001: Manage Data Community

**Journey ID**: JOURNEY-CM-001  
**Title**: Manage Data Community  
**Persona**: Community Manager  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-cm-001-manage-data-community)

---

## Prerequisites

- [ ] Logged in as **Community Manager** (e2e_test@example.com or e2e_admin@example.com / TestPass123)
- [ ] Social/community capability enabled

---

## What You Will Do

Create or manage a data community. Configure settings, add members, manage content.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to communities | Go to **Social** or **Communities** (sidebar). | Communities page | ☐ |
| 2 | Create community (if available) | Click **Create Community**. Name, description. | Community created | ☐ |
| 3 | Configure | Set visibility, rules, allowed assets. | Settings saved | ☐ |
| 4 | Add members | Invite or add members. | Members added | ☐ |
| 5 | Manage content | Add assets, discussions. | Content visible | ☐ |

---

## Success Criteria

- Community section accessible
- Create/configure works (if available)
- Content manageable

---

## Note

If community feature is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/cm/JOURNEY-CM-001.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
