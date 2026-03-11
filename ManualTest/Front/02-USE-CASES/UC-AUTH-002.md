# UC-AUTH-002: User Logs In

**Use Case ID**: UC-AUTH-002  
**Title**: User Logs In  
**Persona**: Visitor (becomes authenticated), any registered persona  
**Priority**: High  
**Source**: [docs/USE_CASES.md](../../docs/USE_CASES.md#uc-auth-002-user-logs-in)

---

## Before You Start

1. Complete [00-PREREQUISITES.md](../00-PREREQUISITES.md)
2. Credentials: [test-users.md](../05-SUPPORT-MATERIAL/test-users.md) (e.g. e2e_test@example.com / TestPass123)
3. Frontend: http://localhost:3010

---

## Prerequisites

- [ ] User has valid credentials (see [test-users.md](../05-SUPPORT-MATERIAL/test-users.md))
- [ ] Backend and frontend running

---

## Main Flow Steps

| # | Action | Expected Result | Pass |
|---|--------|-----------------|------|
| 1 | Navigate to login page (or `/login`) | Login form visible | ☐ |
| 2 | Enter email and password | Fields accept input | ☐ |
| 3 | Submit form | System validates credentials | ☐ |
| 4 | If valid | System returns access token; client stores it | ☐ |
| 5 | On success | User redirected to home or requested resource | ☐ |
| 6 | Navigate to protected route (e.g. `/assets`) | User can access protected resources | ☐ |

---

## Alternate Flows

| Scenario | Action | Expected Result | Pass |
|----------|--------|-----------------|------|
| A1: Invalid credentials | Submit wrong password | 401 Unauthorized or error message | ☐ |
| A2: Account disabled | Submit credentials for disabled account | 403 Forbidden or appropriate message | ☐ |

---

## Traceability

- **Journey**: [JOURNEY-AUTH-002](../03-USER-JOURNEYS/auth/JOURNEY-AUTH-002.md)
- **E2E Spec**: `frontend/e2e/journeys/auth/JOURNEY-AUTH-002.spec.ts`, `frontend/e2e/login-app-shell.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../docs/TEST_TRACEABILITY.md#uc-auth-002-user-logs-in)
