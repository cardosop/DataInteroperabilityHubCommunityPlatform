# JOURNEY-DPO-011: Assign Data Stewards

**Journey ID**: JOURNEY-DPO-011  
**Title**: Assign Data Stewards  
**Persona**: Data Product Owner  
**Priority**: Medium  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dpo-011-assign-data-stewards-new)

---

## Prerequisites

- [ ] Logged in as **Data Product Owner** (e2e_test@example.com / TestPass123)
- [ ] At least one asset
- [ ] Social/stewardship capability enabled

---

## What You Will Do

Assign data stewards to owned assets. Configure steward permissions.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to asset | Go to **Assets** → select asset. | Asset detail | ☐ |
| 2 | Open stewardship section | Find **Stewards** or **Data Stewards** section. | Stewardship UI | ☐ |
| 3 | Assign steward | Add user as steward (email or select). | Steward assigned | ☐ |
| 4 | Configure permissions | Set steward role/permissions. | Permissions saved | ☐ |
| 5 | Verify | Steward appears in list. | Assignment visible | ☐ |

---

## Success Criteria

- Steward assigned
- Permissions configured
- Assignment visible

---

## Note

If stewardship feature is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dpo/JOURNEY-DPO-011.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
