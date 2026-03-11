# JOURNEY-DPO-016: Link ODPS to ODCS Contract (Technical-First Flow)

**Journey ID**: JOURNEY-DPO-016  
**Title**: Link ODPS to ODCS Contract (Technical-First Flow)  
**Persona**: Data Product Owner  
**Priority**: High  
**Estimated Duration**: 15 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dpo-016-link-odps-to-odcs-contract-technical-first-flow-new)

---

## Prerequisites

- [ ] Logged in as **Data Product Owner** (e2e_test@example.com / TestPass123)
- [ ] An existing **ODCS contract** (create via JOURNEY-DPO-005 or JOURNEY-DPO-015)
- [ ] An existing **ODPS contract** (create via JOURNEY-DPO-015, or use ODPS with `contractURL` only)

---

## What You Will Do

Link an existing ODCS contract to an ODPS contract. The system establishes a bidirectional link: ODPS → ODCS and ODCS → ODPS.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Open ODCS contract | Go to **Contracts** → select an ODCS contract (or from ODPS workflow, use the ODCS contract ID). | Contract detail page | ☐ |
| 2 | Navigate to Link ODPS | On contract detail, find **Link ODPS** or **Link ODPS Contract** button/link. Click it. | Navigate to `/contracts/:id/link-odps` | ☐ |
| 3 | Select ODPS contract | Use **ContractPicker** (searchable dropdown; specType=ODPS) to select existing ODPS contract, or create new: upload ODPS document from `05-SUPPORT-MATERIAL/contracts/odps-with-contracturl-only.json` (has `contractURL` only). | ODPS contract selected or created | ☐ |
| 4 | Submit link | Click **Link** or **Create Link**. | Link established; success message | ☐ |
| 5 | Verify ODCS → ODPS link | On ODCS contract detail, verify `odps_link` or linked ODPS contract is shown. | ODPS link visible | ☐ |
| 6 | Verify ODPS → ODCS link | Open ODPS contract detail. Verify `odcs_link` or linked ODCS contract is shown. | ODCS link visible | ☐ |

---

## Success Criteria

- ODCS contract identified
- ODPS contract selected or created
- Bidirectional link established
- Link visible on both contract detail pages

---

## Notes

- If the UI does not expose "Link ODPS" from ODCS contract, the flow may be available from ODPS contract (link to ODCS) or via API.
- ODPS with `contractURL` only (no embedded ODCS) is typically used for linking: create ODCS first, then create ODPS with `contractURL` pointing to that ODCS, or use the link-odps endpoint.

---

## Traceability

- **Use Case**: UC-ODPS-002 (Technical-first flow)
- **E2E Spec**: `frontend/e2e/journeys/dpo/JOURNEY-DPO-016.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
