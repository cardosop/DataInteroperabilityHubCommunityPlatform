# UC-AUTH-007: Tenant Switch

**Persona:** [Data Engineer (DE)](../personas/data-engineer/index.md) / [Data Consumer (DC)](../personas/data-consumer/index.md)
**MVP Tier:** :large_orange_circle: (NET-NEW)
**Phase 216 Test:** `cli/tests/integration/test_commands_real_api.py::test_tenant_switch`

## Description

A user who belongs to multiple tenants switches their active tenant
context without logging out and back in. The platform re-issues a
scoped JWT for the target tenant, and all subsequent API calls operate
within the new tenant's data boundary. This is essential for consultants,
data engineers, and analysts who work across organizational boundaries.

## Preconditions

- The user is authenticated and holds an active JWT for their current
  tenant.
- The user has `TenantMembership` records in at least two tenants.
- Both tenants are in `ACTIVE` status (not suspended or deactivated).

## Steps

1. User opens the tenant selector in the top navigation bar. The UI
   calls `GET /api/v1/users/me/tenants` to list all tenants the user
   belongs to.
2. The API returns an array of
   `{ tenant_id, tenant_name, slug, roles[] }` objects.
3. User selects the target tenant from the list.
4. The front end calls
   `POST /api/v1/auth/switch-tenant` with `{ tenant_id }`.
5. The API verifies the user's membership in the target tenant, checks
   that the tenant is active, and generates a new JWT scoped to the
   target tenant (with the user's roles for that tenant in the `roles`
   claim).
6. The new JWT and a rotated refresh token are returned. The previous
   tenant-scoped tokens remain valid until their natural expiry (the
   user can switch back without re-login).
7. The UI reloads the dashboard, now showing assets, listings, and
   settings belonging to the new tenant.

## Expected Outcome

- The user holds a valid JWT whose `tenant_id` claim matches the
  selected tenant.
- All API calls made with the new token are scoped to the target
  tenant's data partition.
- The user's roles may differ between tenants (e.g., `ADMIN` in one,
  `DATA_CONSUMER` in another). The new token reflects the correct roles.
- An `AUDIT_TENANT_SWITCH` event is recorded in the
  [audit log](../../concepts/audit-events.md), capturing both the
  source and target tenant IDs.

## Security Considerations

- Tenant switching does not extend the original session lifetime; the
  new JWT inherits the same absolute expiry window.
- If the user's membership in the target tenant has been revoked between
  page load and switch request, the API returns `403 Forbidden`.
- Rate limiting applies (max 10 switches per minute) to prevent token
  flooding.

## Related

- Concepts: [Tenants](../../concepts/tenants.md), [Users and Roles](../../concepts/users-and-roles.md)
- Journeys: [JOURNEY-AUTH-002 -- User Logs In](../journeys/JOURNEY-AUTH-002.md)
- Personas: [Data Engineer](../personas/data-engineer/index.md), [Data Consumer](../personas/data-consumer/index.md)
