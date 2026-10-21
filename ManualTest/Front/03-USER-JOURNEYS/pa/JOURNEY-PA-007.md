# JOURNEY-PA-007: Manage ODPS Products (Platform)

**Journey ID**: JOURNEY-PA-007  
**Title**: Manage ODPS Products (Platform)  
**Persona**: Platform Admin  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **Platform Admin** (e2e_platform@example.com / TestPass123)
- [ ] ODPS products exist (from tenants)

---

## What You Will Do

View ODPS products across tenants. Approve, reject, or manage. Platform-level visibility.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to ODPS admin | Go to **Admin** → **ODPS** or **Contracts** (platform view). | ODPS list | ☐ |
| 2 | View products | Browse ODPS products. Filter by tenant. | Products displayed | ☐ |
| 3 | Open product | Click product. View detail. | Detail visible | ☐ |
| 4 | Manage | Approve, reject, or take action if workflow exists. | Action works | ☐ |

---

## Success Criteria

- ODPS products visible
- Cross-tenant view works
- Management actions (if available)

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/pa/JOURNEY-MPA-007.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
