# JOURNEY-DC-008: Rate and Review Asset

**Journey ID**: JOURNEY-DC-008  
**Title**: Rate and Review Asset  
**Persona**: Data Consumer  
**Priority**: Medium  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dc-008-rate-and-review-asset-new)

---

## Prerequisites

- [ ] Logged in as **Data Consumer** (e2e_consumer@example.com / TestPass123)
- [ ] Entitlement to asset (purchased)
- [ ] Social/ratings capability enabled

---

## What You Will Do

Rate asset (1-5 stars). Write review. Submit. View status.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to asset | Go to purchased asset detail. | Asset detail | ☐ |
| 2 | Open ratings section | Find **Rate** or **Reviews** section. | Ratings UI | ☐ |
| 3 | Rate | Select 1-5 stars. | Rating selected | ☐ |
| 4 | Write review | Enter review text. | Review entered | ☐ |
| 5 | Submit | Click **Submit**. | Review submitted | ☐ |
| 6 | Verify | Review appears (pending or published). | Review visible | ☐ |

---

## Success Criteria

- Rating submitted
- Review submitted
- Review visible

---

## Note

If ratings feature is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dc/JOURNEY-DC-008.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
