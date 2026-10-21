# UC-AUTH-005: Invitation Accept

**Persona:** [Data Consumer (DC)](../personas/data-consumer/index.md) / [Data Engineer (DE)](../personas/data-engineer/index.md)
**MVP Tier:** :large_orange_circle: (NET-NEW -- Phase 217.1.4)
**Phase 216 Test:** `cli/tests/integration/test_commands_real_api.py::test_invitation_accept`

## Description

A tenant administrator invites a new or existing user to join their
tenant by email. The invitee receives an email containing a unique
invitation link. Accepting the invitation either registers a new account
and adds it to the tenant or links an existing account to the new
tenant, granting the roles specified in the invitation.

## Preconditions

- The inviter holds the `TENANT_ADMIN` role within the target tenant.
- The tenant has not exceeded its seat limit (see
  [Billing](../../concepts/billing.md)).
- The invitation email service is operational.
- If the invitee already has an account, their email matches the
  invitation address.

## Steps

1. Tenant admin opens the "Members" page in the tenant settings or calls
   `POST /api/v1/tenants/{tenant_id}/invitations` with
   `{ email, roles: ["DATA_ENGINEER"] }`.
2. The API creates an `Invitation` record with `status = PENDING` and a
   one-time token (valid for 72 hours). Returns `201 Created`.
3. Meshant sends an invitation email to the specified address with a
   link containing the token.
4. Invitee clicks the link.
   - **New user:** The link redirects to the registration form with the
     invitation token pre-attached. After completing registration (see
     [UC-AUTH-001](UC-AUTH-001.md)), the token is consumed and the user
     is added to the tenant.
   - **Existing user:** The link redirects to a confirmation page. The
     user logs in (if not already authenticated) and confirms acceptance.
5. The API sets the invitation to `status = ACCEPTED`, creates a
   `TenantMembership` record with the specified roles, and returns
   `200 OK`.
6. The invitee's tenant selector now includes the new tenant.

## Expected Outcome

- The invitee is a member of the target tenant with the roles specified
  in the invitation.
- The invitation record is marked `ACCEPTED` and the token is
  invalidated.
- An `AUDIT_INVITATION_ACCEPTED` event is written to the
  [audit log](../../concepts/audit-events.md).
- The tenant admin can see the new member in the "Members" list.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Expired invitation (>72 h) | `410 Gone` -- admin must re-invite |
| Already-accepted invitation | `409 Conflict` |
| Seat limit reached | `403 Forbidden` with `SEAT_LIMIT_EXCEEDED` code |
| Email mismatch (existing user) | `403 Forbidden` |

## Related

- Concepts: [Users and Roles](../../concepts/users-and-roles.md), [Tenants](../../concepts/tenants.md), [Billing](../../concepts/billing.md)
- Journeys: [JOURNEY-AUTH-001 -- First-Time Visitor Registers](../journeys/JOURNEY-AUTH-001.md)
- Personas: [Data Consumer](../personas/data-consumer/index.md), [Data Engineer](../personas/data-engineer/index.md)
