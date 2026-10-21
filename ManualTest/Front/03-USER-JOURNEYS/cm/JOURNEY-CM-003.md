# JOURNEY-CM-003: Assign Data Stewards

**Journey ID**: JOURNEY-CM-003  
**Title**: Assign Data Stewards  
**Persona**: Community Manager  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-cm-003-assign-data-stewards)

---

## Prerequisites

- [ ] Logged in as **Community Manager** (e2e_test@example.com or e2e_admin@example.com / TestPass123)
- [ ] At least one asset or community
- [ ] Stewardship capability enabled

---

## What You Will Do

Assign data stewards to asset or community. Set permissions. Notify stewards.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to stewardship | Go to **Social** → **Stewards** or asset → **Stewards**. | Stewardship page | ☐ |
| 2 | Assign steward | Add user as steward. | Steward assigned | ☐ |
| 3 | Set permissions | Configure steward role. | Permissions set | ☐ |
| 4 | Notify | Send notification if available. | Steward notified | ☐ |

---

## Success Criteria

- Steward assigned
- Permissions set
- Assignment visible

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/cm/JOURNEY-CM-003.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
