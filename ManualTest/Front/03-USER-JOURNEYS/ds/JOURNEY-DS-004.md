# JOURNEY-DS-004: Tune Recommendation Engine

**Journey ID**: JOURNEY-DS-004  
**Title**: Tune Recommendation Engine  
**Persona**: Data Scientist  
**Priority**: Medium  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-ds-004-tune-recommendation-engine)

---

## Prerequisites

- [ ] Logged in as **Data Scientist** (e2e_test@example.com or e2e_consumer@example.com / TestPass123)
- [ ] Recommendation engine enabled

---

## What You Will Do

Access recommendation tuning. Adjust parameters. Test recommendations.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to recommendations | Go to **ML** → **Recommendations** or **AI** → **Recommendations**. | Tuning page | ☐ |
| 2 | View config | Check current parameters. | Config displayed | ☐ |
| 3 | Tune | Adjust parameters (e.g. diversity, relevance). | Parameters updated | ☐ |
| 4 | Test | Trigger recommendation. | Recommendations returned | ☐ |

---

## Success Criteria

- Tuning accessible
- Parameters adjustable
- Recommendations work

---

## Note

If recommendation tuning is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/ds/JOURNEY-DS-004.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
