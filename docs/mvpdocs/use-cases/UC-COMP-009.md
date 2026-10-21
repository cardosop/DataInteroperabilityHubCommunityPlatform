# UC-COMP-009: Manage RoPA Lifecycle (Edit and Retire)

**ID:** UC-COMP-009
**Title:** Manage Record of Processing Activities Lifecycle (Edit and Retire)
**Persona:** Compliance & Privacy Officer (CPO)
**Priority:** Medium
**Phase:** 276.B.104 (GA)
**Feature Flag:** `compliance_ropa_enabled` (ON by default for new tenants)

## Summary

The DPO manages the lifecycle of generated RoPA records: annotate a record
with review notes (edit step) and retire superseded or erroneous records
(delete step), keeping the tenant's Article 30 inventory accurate.

## Preconditions

- Tenant has `compliance_ropa_enabled = True`
- At least one RoPA generation record exists
- User has DPO, CPO, TENANT_ADMIN, or LEGAL_ADMIN role (IsRopaHandler)

## Main Flow

1. DPO navigates to `/settings/ropa`
2. DPO clicks **Add note** / **Edit note** on a record and saves a review note
   (persisted into the record's `summary_json.notes` via
   `PATCH /api/v1/ropa/generations/{id}/update/`)
3. DPO clicks **Retire** on a superseded record and confirms
   (`DELETE /api/v1/ropa/generations/{id}/delete/`, audited as
   `ROPA_DELETED`); the record disappears from the list

## Alternative Flows

- RoPA disabled for the tenant → API returns 403 `ROPA_DISABLED`
- Non-handler user → 403 (RBAC)
- Cross-tenant record id → 404 (tenant isolation)

## Acceptance Criteria

- Note edits persist and render after refetch
- Retired records are removed from the list and the API returns 404
- Delete emits a `ROPA_DELETED` audit event
