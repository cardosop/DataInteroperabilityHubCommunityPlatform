# UC-CM-003: Assign Data Steward

**Persona:** [Marketplace Platform Admin (MPA)](../personas/marketplace-platform-admin/index.md) / [Data Product Owner (DPO)](../personas/data-product-owner/index.md)
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_commands_real_api.py::test_assign_steward`

## Description

A Marketplace Platform Admin or Data Product Owner designates a Data
Steward for a specific domain or collection of assets. The steward
becomes the accountable point of contact for data quality, metadata
accuracy, and lifecycle decisions within that domain, receiving
notifications and escalation rights.

## Preconditions

- The assigning user holds the `MARKETPLACE_ADMIN`, `PLATFORM_ADMIN`,
  or `DATA_PRODUCT_OWNER` role.
- The target user (steward candidate) is an active member of the tenant.
- The domain or asset collection to steward exists and is in an active
  state.

## Steps

1. Admin navigates to the domain settings page or calls
   `POST /api/v1/domains/{domain_id}/stewards` with
   `{ user_id, scope, responsibilities[] }`.
   - **Scope:** `DOMAIN` (all assets in the domain) or `ASSET_GROUP`
     (specific tagged subset).
   - **Responsibilities:** Configurable list such as `QUALITY_REVIEW`,
     `METADATA_MAINTENANCE`, `ACCESS_APPROVAL`, `COMPLIANCE_LIAISON`.
2. The API validates that the user exists and is a tenant member, then
   creates a `StewardAssignment` record. Returns `201 Created`.
3. The designated steward receives an in-app notification and email
   summarizing their new responsibilities and the domain scope.
4. The steward's profile is updated to display the stewardship badge on
   the domain and asset pages.
5. Going forward, DQ alerts, compliance findings, and access requests
   for assets within the steward's scope are routed to them in addition
   to (or instead of) the original asset owner.
6. Admin can review all steward assignments via
   `GET /api/v1/domains/{domain_id}/stewards` and reassign or revoke
   as needed.

## Expected Outcome

- A `StewardAssignment` record links the user to the domain with the
  specified scope and responsibilities.
- The steward appears on the domain detail page and on each asset within
  scope.
- DQ alerts, compliance findings, and access requests within scope are
  routed to the steward.
- An `AUDIT_STEWARD_ASSIGNED` event is recorded in the
  [audit log](../../concepts/audit-events.md).

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| User not a tenant member | `404 Not Found` (user) |
| Domain not found | `404 Not Found` |
| Duplicate assignment | `409 Conflict` |
| Insufficient role to assign | `403 Forbidden` |

## Related

- Concepts: [Users and Roles](../../concepts/users-and-roles.md), [Assets](../../concepts/assets.md), [Governance](../../concepts/governance.md)
- Journeys: [JOURNEY-DPO-003 -- Manage Asset Lifecycle](../journeys/JOURNEY-DPO-003.md)
- Personas: [Marketplace Platform Admin](../personas/marketplace-platform-admin/index.md), [Data Product Owner](../personas/data-product-owner/index.md)
