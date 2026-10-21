# JOURNEY-DPO-002: Publish Asset to Marketplace

**Journey ID**: JOURNEY-DPO-002  
**Title**: Publish Asset to Marketplace  
**Persona**: Data Product Owner  
**Priority**: High  
**Estimated Duration**: 15 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dpo-002-publish-asset-to-marketplace)

---

## Prerequisites

- [ ] Logged in as **Data Product Owner** (e2e_test@example.com / TestPass123)
- [ ] An **ACTIVE** asset exists (complete JOURNEY-DPO-001 first, or use existing asset)
- [ ] Asset has a contract linked (optional but recommended)

---

## What You Will Do

Publish an active asset to the marketplace. You will verify asset status, check eligibility, create a marketplace listing, configure pricing (if applicable), and publish.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Verify asset is active | Go to **Assets** → select your asset. Check status badge. | Status = **ACTIVE** | ☐ |
| 2 | Navigate to publish | Go to **Marketplace** → **Publish** (or use "Publish to Marketplace" from asset detail if available). | Publish page loads | ☐ |
| 3 | Select asset | Choose the asset to publish from the list or dropdown. | Asset selected; eligibility checked | ☐ |
| 4 | Configure listing | Fill listing details: title, description, pricing (if required). If ODPS contract exists, pricing/access may be pre-filled. | Form accepts input; no validation errors | ☐ |
| 5 | Create listing | Click **Create Listing** or **Publish**. | Listing created; status may show DRAFT or PUBLISHED | ☐ |
| 6 | Publish listing | If listing is DRAFT, click **Publish** to make it live. | Listing status = **PUBLISHED** | ☐ |

---

## Success Criteria

- Asset is in ACTIVE status
- Asset passes eligibility checks (or reason for failure is clear)
- Listing created successfully
- Listing published (status = PUBLISHED)

---

## Error Scenarios

| Scenario | Expected Result | Pass |
|----------|-----------------|------|
| Asset not ACTIVE | Message indicating asset must be active to publish | ☐ |
| No subscription | 403 or message about subscription required | ☐ |
| Validation error | Clear error message; form highlights invalid fields | ☐ |

---

## Traceability

- **Use Case**: UC-DPO-002 (Marketplace publishing)
- **E2E Spec**: `frontend/e2e/journeys/dpo/JOURNEY-DPO-002.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
