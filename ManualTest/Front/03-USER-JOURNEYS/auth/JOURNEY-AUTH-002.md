# JOURNEY-AUTH-002: User Logs In

**Journey ID**: JOURNEY-AUTH-002  
**Title**: User Logs In  
**Persona**: Visitor (becomes authenticated), any registered persona  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-auth-002-user-logs-in)

---

## Prerequisites

- [ ] User has valid credentials (see [test-users.md](../../05-SUPPORT-MATERIAL/test-users.md))
- [ ] Backend and frontend running

---

## Steps

| # | Action | Expected Result | Pass |
|---|--------|-----------------|------|
| 1 | Navigate to login page (or `/login`) | Login form visible | ☐ |
| 2 | Enter email and password | Fields accept input | ☐ |
| 3 | Submit form | System validates credentials | ☐ |
| 4 | If valid | System returns access token; client stores it | ☐ |
| 5 | On success | User redirected to home or requested resource | ☐ |
| 6 | Navigate to protected route (e.g. `/assets`) | User can access protected resources | ☐ |

---

## Success Criteria

- Credentials validated
- Token/session issued
- User can access protected resources

---

## Error Scenarios

| Scenario | Expected Result | Pass |
|----------|-----------------|------|
| Invalid credentials | 401 Unauthorized or error message | ☐ |
| Account disabled/locked | 403 Forbidden or appropriate message | ☐ |

---

## Traceability

- **Use Case**: [UC-AUTH-002](../../02-USE-CASES/UC-AUTH-002.md)
- **E2E Spec**: `frontend/e2e/journeys/auth/JOURNEY-AUTH-002.spec.ts`, `frontend/e2e/login-app-shell.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md#journey-auth-002-user-logs-in)
