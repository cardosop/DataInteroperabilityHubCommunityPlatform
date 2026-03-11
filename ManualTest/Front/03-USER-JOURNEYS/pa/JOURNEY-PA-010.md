# JOURNEY-PA-010: Manage ODPS Products

**Journey ID**: JOURNEY-PA-010  
**Title**: Manage ODPS Products  
**Persona**: Platform Admin  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-pa-010-manage-odps-products-new)

---

## Prerequisites

- [ ] Logged in as **Platform Admin** (e2e_platform@example.com / TestPass123)
- [ ] ODPS products in platform

---

## What You Will Do

View, approve, or manage ODPS products. Platform-level ODPS management.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to ODPS | Go to **Admin** → **ODPS** or **Contracts**. | ODPS list | ☐ |
| 2 | View products | Browse ODPS products. | Products displayed | ☐ |
| 3 | Filter | Filter by tenant, status. | Filter works | ☐ |
| 4 | Manage | Approve, publish, or take action. | Action works | ☐ |

---

## Success Criteria

- ODPS products visible
- Management actions work

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/pa/JOURNEY-PA-010.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
