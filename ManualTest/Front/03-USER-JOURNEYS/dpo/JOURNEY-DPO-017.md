# JOURNEY-DPO-017: Export ODPS Product

**Journey ID**: JOURNEY-DPO-017  
**Title**: Export ODPS Product  
**Persona**: Data Product Owner  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dpo-017-export-odps-product-new)

---

## Prerequisites

- [ ] Logged in as **Data Product Owner** (e2e_test@example.com / TestPass123)
- [ ] At least one ODPS contract (from JOURNEY-DPO-015 or existing)

---

## What You Will Do

Export an ODPS contract to JSON or YAML. Download the exported file.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to ODPS contract | Go to **ODPS** or **Contracts** → select ODPS contract. | ODPS detail page | ☐ |
| 2 | Click Export | Find **Export** button. Click it. | Export options or format selector | ☐ |
| 3 | Select format | Choose JSON or YAML. | Format selected | ☐ |
| 4 | Download | Export/download file. | File downloaded (.odps.json or .odps.yaml) | ☐ |
| 5 | Verify content | Open file. Verify ODPS structure (schema, version, product). | Valid ODPS document | ☐ |

---

## Success Criteria

- Export completes
- File downloaded
- Exported content is valid ODPS

---

## API Alternative

`GET /api/v1/contracts/{id}/export/?format=odps&output_format=json` or `.../download/`

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dpo/JOURNEY-DPO-017.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
