# JOURNEY-AUTH-005: User Switches Active Tenant

**Journey ID**: JOURNEY-AUTH-005  
**Title**: User Switches Active Tenant  
**Persona**: Any authenticated user with multiple tenants  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-auth-005-user-switches-active-tenant)

---

## Prerequisites

- [ ] User **authenticated** (JWT or session)
- [ ] User has membership in at least two tenants (e.g. personal + org via invitation)
- [ ] Tenant switch feature enabled (`FEATURE_TENANT_SWITCH_ENABLED=true`)

---

## Steps

| # | Action | Expected Result | Pass |
|---|--------|-----------------|------|
| 1 | Log in with user who has multiple tenants | User authenticated | ☐ |
| 2 | Open tenant switcher in header (dropdown) | Tenant switcher visible; list loads via GET /auth/me/tenants/ | ☐ |
| 3 | Verify tenant list displays | Shows id, name, slug for each tenant | ☐ |
| 4 | Select target tenant from dropdown | Switch action triggered | ☐ |
| 5 | Call POST /auth/switch-tenant/ with tenant_id | 200 OK; response includes tenant_id overridden | ☐ |
| 6 | Verify subsequent requests send X-Tenant-Id | Header present on API requests | ☐ |
| 7 | Navigate to assets list | Assets scoped to switched tenant | ☐ |

---

## Success Criteria

- Tenant list displayed
- Switch completes without error
- Subsequent API requests use X-Tenant-Id
- Assets/listings reflect switched tenant

---

## Error Scenarios

| Scenario | Expected Result | Pass |
|----------|-----------------|------|
| Feature disabled | 403 on GET /auth/me/tenants/ and POST /auth/switch-tenant/; tenant switcher hidden | ☐ |
| No membership in target tenant | 403 Forbidden on POST /auth/switch-tenant/ | ☐ |
| Invalid tenant_id | 400 Bad Request | ☐ |

---

## Traceability

- **Use Case**: [UC-AUTH-005](../../02-USE-CASES/UC-AUTH-005.md)
- **E2E Spec**: `frontend/e2e/use-cases/auth/tenant-switch.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md#journey-auth-005-user-switches-active-tenant)
