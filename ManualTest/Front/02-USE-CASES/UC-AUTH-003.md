# UC-AUTH-003: User Resets Password

**Use Case ID**: UC-AUTH-003  
**Title**: User Resets Password  
**Persona**: Visitor, any registered user  
**Priority**: Medium  
**Source**: [docs/USE_CASES.md](../../docs/USE_CASES.md#uc-auth-003-user-resets-password)

---

## Prerequisites

- [ ] User **not authenticated** (or authenticated and changing password)
- [ ] User account exists (e.g. e2e_test@example.com)
- [ ] Password reset feature enabled (email delivery configured)

---

## Main Flow Steps

| # | Action | Expected Result | Pass |
|---|--------|-----------------|------|
| 1 | Navigate to "Forgot password" or equivalent link | Reset request form visible | ☐ |
| 2 | Enter email for account | Field accepts input | ☐ |
| 3 | Submit form | System validates account exists (no disclosure if not) | ☐ |
| 4 | If account exists | System sends reset link/code to registered email | ☐ |
| 5 | Open reset link or enter code | New password form presented | ☐ |
| 6 | Enter new password meeting policy | Field accepts input | ☐ |
| 7 | Submit new password | System invalidates reset token and updates password | ☐ |
| 8 | Log in with new password | User can authenticate (UC-AUTH-002) | ☐ |

---

## Alternate Flows

| Scenario | Action | Expected Result | Pass |
|----------|--------|-----------------|------|
| A1: Reset not enabled | Navigate to forgot-password | 501 or UI shows "Contact administrator" | ☐ |
| A2: Token expired | Use expired reset link | Error; user must request reset again | ☐ |
| A3: New password policy not met | Submit weak password | 400 or validation message | ☐ |

---

## Note

If password reset is not implemented, this use case is **N/A**; users contact administrator or use invite flow (JOURNEY-TA-001).

---

## Traceability

- **Journey**: [JOURNEY-AUTH-003](../03-USER-JOURNEYS/auth/JOURNEY-AUTH-003.md)
- **E2E Spec**: `frontend/e2e/journeys/auth/JOURNEY-AUTH-003.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../docs/TEST_TRACEABILITY.md#uc-auth-003-user-resets-password)
