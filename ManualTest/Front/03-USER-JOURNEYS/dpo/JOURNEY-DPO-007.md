# JOURNEY-DPO-007: Use AI Schema Matching for Asset Creation

**Journey ID**: JOURNEY-DPO-007  
**Title**: Use AI Schema Matching for Asset Creation  
**Persona**: Data Product Owner  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dpo-007-use-ai-schema-matching-for-asset-creation-new)

---

## Prerequisites

- [ ] Logged in as **Data Product Owner** (e2e_test@example.com / TestPass123)
- [ ] AI schema matching capability enabled
- [ ] Support material: `05-SUPPORT-MATERIAL/data/sample-upload.csv`

---

## What You Will Do

Upload file, use AI schema matching to suggest field mappings, review and accept, generate contract draft, validate and activate.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Upload file | Create dataset or asset; upload `sample-upload.csv`. | Schema inferred | ☐ |
| 2 | Trigger AI schema matching | If UI offers "AI Schema Matching" or similar, trigger it. | Mappings suggested with confidence scores | ☐ |
| 3 | Review mappings | Accept, reject, or modify suggested mappings. | Mappings editable | ☐ |
| 4 | Generate contract | Use "Generate Contract" from mappings. | Contract draft created | ☐ |
| 5 | Validate and activate | Validate contract, link to asset, activate. | Asset activated | ☐ |

---

## Success Criteria

- AI schema matching runs (if capability enabled)
- Mappings suggested
- Contract draft generated
- Asset activated

---

## Note

If AI schema matching is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dpo/JOURNEY-DPO-007.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
