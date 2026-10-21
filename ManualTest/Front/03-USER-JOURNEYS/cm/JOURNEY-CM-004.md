# JOURNEY-CM-004: Manage Activity Feeds

**Journey ID**: JOURNEY-CM-004  
**Title**: Manage Activity Feeds  
**Persona**: Community Manager  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-cm-004-manage-activity-feeds)

---

## Prerequisites

- [ ] Logged in as **Community Manager** (e2e_test@example.com or e2e_admin@example.com / TestPass123)
- [ ] Activity feed capability enabled

---

## What You Will Do

View activity feed. Configure feed sources. Moderate or filter activities.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to activity | Go to **Social** → **Activity** or **Activity Feed**. | Activity page | ☐ |
| 2 | View feed | Browse activities (reviews, shares, etc.). | Feed displayed | ☐ |
| 3 | Configure | Set feed sources, filters. | Config saved | ☐ |
| 4 | Moderate | Hide or highlight activity if supported. | Moderation works | ☐ |

---

## Success Criteria

- Activity feed visible
- Config works
- Moderation (if available)

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/cm/JOURNEY-CM-004.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
