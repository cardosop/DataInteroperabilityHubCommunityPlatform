# UC-AUTH-005: User Switches Active Tenant

**Use Case ID**: UC-AUTH-005  
**Title**: User Switches Active Tenant  
**Persona**: Any authenticated user with multiple tenants  
**Priority**: High  
**Source**: [docs/USE_CASES.md](../../docs/USE_CASES.md#uc-auth-005-user-switches-active-tenant)

---

## Before You Start

1. Complete [00-PREREQUISITES.md](../00-PREREQUISITES.md)
2. User must have membership in at least two tenants (e.g. personal + org via invitation)
3. `FEATURE_TENANT_SWITCH_ENABLED` must be true (default)

---

## Prerequisites

- [ ] User **authenticated** (JWT or session)
- [ ] User has membership in at least two tenants (UserTenantMembership)
- [ ] Tenant switch feature enabled (`FEATURE_TENANT_SWITCH_ENABLED=true`)

---

## Main Flow Steps

| # | Action | Expected Result | Pass |
|---|--------|-----------------|------|
| 1 | Log in with user who has multiple tenants | User authenticated | ☐ |
| 2 | Open tenant switcher in header (dropdown) | Tenant switcher visible; list loads | ☐ |
| 3 | Call GET /auth/me/tenants/ | Returns list of tenants with id, name, slug | ☐ |
| 4 | Select target tenant from dropdown | Switch action triggered | ☐ |
| 5 | Call POST /auth/switch-tenant/ with tenant_id | 200 OK; response includes tenant_id overridden | ☐ |
| 6 | Verify subsequent requests send X-Tenant-Id | Header present on API requests | ☐ |
| 7 | Navigate to assets list | Assets scoped to switched tenant | ☐ |

---

## Alternate Flows

| Scenario | Action | Expected Result | Pass |
|----------|--------|-----------------|------|
| A1: Feature disabled | Call GET /auth/me/tenants/ | 403 Forbidden; tenant switcher hidden in UI | ☐ |
| A2: No membership in target tenant | POST /auth/switch-tenant/ with non-member tenant_id | 403 Forbidden | ☐ |
| A3: Invalid tenant_id | POST /auth/switch-tenant/ with "not-a-uuid" | 400 Bad Request | ☐ |

---

## Traceability

- **Journey**: [JOURNEY-AUTH-005](../03-USER-JOURNEYS/auth/JOURNEY-AUTH-005.md)
- **E2E Spec**: `frontend/e2e/use-cases/auth/tenant-switch.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../docs/TEST_TRACEABILITY.md#uc-auth-005-user-switches-active-tenant)
