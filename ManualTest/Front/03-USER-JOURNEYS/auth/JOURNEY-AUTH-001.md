# JOURNEY-AUTH-001: First-Time Visitor Registers

**Journey ID**: JOURNEY-AUTH-001  
**Title**: First-Time Visitor Registers  
**Persona**: Visitor, Prospect  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-auth-001-first-time-visitor-registers)

---

## Prerequisites

- [ ] User **not authenticated**
- [ ] Registration feature enabled (when deployment supports self-signup)
- [ ] Valid email and password meeting policy (uppercase, lowercase, number)

**Note**: Steps 9–10 verify post-login: no tenant_id → personal tenant; tenant_id provided → user's tenant.

---

## Steps

| # | Action | Expected Result | Pass |
|---|--------|-----------------|------|
| 1 | Land on application (or redirect to login) | Login or landing page visible | ☐ |
| 2 | Navigate to registration page (or `/register`) | Registration form visible; or link "Create an account" on login | ☐ |
| 3 | Enter email, password, optional display name | Fields accept input | ☐ |
| 4 | Submit form | System validates email format and password policy | ☐ |
| 5 | If validation passes | System checks email is not already registered | ☐ |
| 6 | If email unique (no tenant_id) | System creates personal tenant, assigns DATA_PROVIDER and DATA_CONSUMER; if tenant_id provided, user associated with that tenant | ☐ |
| 7 | On success | User receives confirmation (success message or redirect) | ☐ |
| 8 | Log in with new credentials | User can authenticate (JOURNEY-AUTH-002) | ☐ |
| 9 | Call GET /auth/me/ | Response includes tenant_id | ☐ |
| 10 | Create asset in user's tenant | Asset created successfully | ☐ |

---

## Success Criteria

- Registration endpoint/page available (when feature enabled)
- User account created
- User has tenant (personal or provided) and can create/consume data
- User can authenticate

---

## Error Scenarios

| Scenario | Expected Result | Pass |
|----------|-----------------|------|
| Registration disabled | 403 or UI shows "Contact administrator" | ☐ |
| Email already exists | 400 Bad Request or error message | ☐ |
| Password policy not met | 400 Bad Request or validation message | ☐ |

---

## Traceability

- **Use Case**: [UC-AUTH-001](../../02-USE-CASES/UC-AUTH-001.md)
- **E2E Spec**: `frontend/e2e/journeys/auth/JOURNEY-AUTH-001.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md#journey-auth-001-first-time-visitor-registers)
