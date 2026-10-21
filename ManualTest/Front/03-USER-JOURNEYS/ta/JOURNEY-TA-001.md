# JOURNEY-TA-001: Onboard New User

**Journey ID**: JOURNEY-TA-001  
**Title**: Onboard New User  
**Persona**: Tenant Admin  
**Priority**: High  
**Estimated Duration**: 15 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-ta-001-onboard-new-user)

---

## Prerequisites

- [ ] Logged in as **Tenant Admin** (e2e_admin@example.com / TestPass123)
- [ ] Invitation feature enabled (if deployment supports it)

---

## What You Will Do

Invite a new user to the tenant. Enter email, select role, send invitation. Optionally verify user accepts and activates.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to user management | Go to **Admin** or **Settings** → **Users** (or equivalent). | User management page | ☐ |
| 2 | Invite user | Click **Invite User** or **Add User**. | Invite form or modal | ☐ |
| 3 | Enter details | Email (use a new/test email), select role (e.g. DATA_CONSUMER). | Form accepts input | ☐ |
| 4 | Send invitation | Click **Send** or **Invite**. | Invitation sent; success message | ☐ |
| 5 | Verify (optional) | If email configured: user receives email. User accepts via link. | User activated in tenant | ☐ |

---

## Success Criteria

- Invitation sent
- User appears in list (pending or active)
- User can log in after accepting (if flow supported)

---

## Error Scenarios

| Scenario | Expected Result | Pass |
|----------|-----------------|------|
| Email already in tenant | Error or message | ☐ |
| Invalid email | Validation error | ☐ |

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/ta/JOURNEY-TA-001.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
