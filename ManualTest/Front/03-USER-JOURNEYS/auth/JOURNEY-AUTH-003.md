# JOURNEY-AUTH-003: User Resets Password

**Journey ID**: JOURNEY-AUTH-003  
**Title**: User Resets Password  
**Persona**: Visitor, any registered user  
**Priority**: Medium  
**Estimated Duration**: 15 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-auth-003-user-resets-password)

---

## Prerequisites

- [ ] User **not authenticated**
- [ ] User account exists (e.g. e2e_test@example.com)
- [ ] Password reset feature enabled (email delivery configured)
- [ ] Email delivery configured (e.g. MailHog for local dev). If not configured, mark this journey N/A.

---

## Steps

| # | Action | Expected Result | Pass |
|---|--------|-----------------|------|
| 1 | Navigate to "Forgot password" or equivalent | Reset request form visible | ☐ |
| 2 | Enter email for account | Field accepts input | ☐ |
| 3 | Submit form | System validates account exists (no disclosure if not) | ☐ |
| 4 | If account exists | System sends reset link/code to registered email | ☐ |
| 5 | Open reset link or enter code | New password form presented | ☐ |
| 6 | Enter new password meeting policy | Field accepts input | ☐ |
| 7 | Submit new password | System invalidates reset token and updates password | ☐ |
| 8 | Log in with new password | User can authenticate (JOURNEY-AUTH-002) | ☐ |

---

## Success Criteria

- Reset request accepted
- Reset link/code sent (if account exists)
- Password updated
- User can log in with new password

---

## Error Scenarios

| Scenario | Expected Result | Pass |
|----------|-----------------|------|
| Reset not enabled | 501 or UI shows "Contact administrator" | ☐ |
| Token expired or invalid | User must request reset again | ☐ |
| New password policy not met | 400 or validation message | ☐ |

---

## Note

If password reset is not implemented, this journey is **N/A**; users contact administrator or use invite flow (JOURNEY-TA-001).

---

## Traceability

- **Use Case**: [UC-AUTH-003](../../02-USE-CASES/UC-AUTH-003.md)
- **E2E Spec**: `frontend/e2e/journeys/auth/JOURNEY-AUTH-003.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md#journey-auth-003-user-resets-password)
