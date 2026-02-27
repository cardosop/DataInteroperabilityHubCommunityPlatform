# UC-AUTH-001: User Registers (Self-Service Sign-Up)

**Use Case ID**: UC-AUTH-001  
**Title**: User Registers (Self-Service Sign-Up)  
**Persona**: Visitor, Prospect  
**Priority**: High  
**Source**: [docs/USE_CASES.md](../../docs/USE_CASES.md#uc-auth-001-user-registers-self-service-sign-up)

---

## Prerequisites

- [ ] User **not authenticated**
- [ ] Registration feature enabled (if deployment supports self-signup)
- [ ] Valid email and password meeting policy (uppercase, lowercase, number)

---

## Main Flow Steps

| # | Action | Expected Result | Pass |
|---|--------|-----------------|------|
| 1 | Navigate to registration page (or `/register`) | Registration form visible; or link "Create an account" on login page | ☐ |
| 2 | Enter email, password, optional display name | Fields accept input | ☐ |
| 3 | Submit form | System validates email format and password policy | ☐ |
| 4 | If validation passes | System checks email is not already registered | ☐ |
| 5 | If email unique | System creates user in default tenant | ☐ |
| 6 | On success | User receives confirmation (success message or redirect) | ☐ |
| 7 | Log in with new credentials | User can authenticate (UC-AUTH-002) | ☐ |

---

## Alternate Flows

| Scenario | Action | Expected Result | Pass |
|----------|--------|-----------------|------|
| A1: Registration disabled | Navigate to `/register` | 403 or UI shows "Contact administrator" | ☐ |
| A2: Email already exists | Submit with existing email | 400 or error message "Email already registered" | ☐ |
| A3: Password policy not met | Submit weak password | 400 or validation message describing policy | ☐ |

---

## Traceability

- **Journey**: [JOURNEY-AUTH-001](../03-USER-JOURNEYS/auth/JOURNEY-AUTH-001.md)
- **E2E Spec**: `frontend/e2e/journeys/auth/JOURNEY-AUTH-001.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../docs/TEST_TRACEABILITY.md#uc-auth-001-user-registers-self-service-sign-up)
