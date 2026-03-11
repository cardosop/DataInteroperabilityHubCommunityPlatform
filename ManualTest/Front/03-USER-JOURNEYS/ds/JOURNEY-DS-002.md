# JOURNEY-DS-002: Use AI Schema Matching

**Journey ID**: JOURNEY-DS-002  
**Title**: Use AI Schema Matching  
**Persona**: Data Scientist  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-ds-002-use-ai-schema-matching)

---

## Prerequisites

- [ ] Logged in as **Data Scientist** (e2e_test@example.com or e2e_consumer@example.com / TestPass123)
- [ ] AI schema matching capability enabled

---

## What You Will Do

Use AI schema matching to map source schema to target. Review suggestions. Accept mappings.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to schema matching | Go to **AI** → **Schema Matching** or asset/dataset create. | Schema matching UI | ☐ |
| 2 | Provide source schema | Upload file or select dataset. | Schema inferred | ☐ |
| 3 | Run matching | Trigger AI schema matching. | Mappings suggested | ☐ |
| 4 | Review | Check confidence scores. Accept/reject. | Mappings editable | ☐ |
| 5 | Apply | Apply mappings. Generate contract or dataset. | Output generated | ☐ |

---

## Success Criteria

- Schema matching runs
- Mappings suggested
- Output generated

---

## Note

If AI schema matching is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/ds/JOURNEY-DS-002.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
