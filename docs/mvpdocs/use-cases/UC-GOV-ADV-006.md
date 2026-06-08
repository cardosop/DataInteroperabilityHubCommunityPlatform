# UC-GOV-ADV-006: Delegate Approval Authority

**Persona:** [Tenant Admin](../personas/tenant-admin/) / [Compliance & Privacy Officer (CPO)](../personas/compliance-privacy-officer/index.md)
**Phase:** 272 (Governance ABAC + Multi-Step), 278 (UX Activation)
**Phase 278 Task:** `278.I.3`

## Description

A Tenant Admin or Compliance Officer delegates their approval authority
to another user for a defined time window (e.g., out-of-office coverage).
Delegates can approve access requests on behalf of the delegator during
the active window. Delegations are checked at approval time — if the
original approver is unavailable, the delegate can approve. Delegations
can be revoked early at any time.

## Preconditions

- The user holds `TENANT_ADMIN` or `PLATFORM_ADMIN` role.
- The delegate user exists within the same tenant.
- The delegation route (`/governance/delegation`) is registered.

## Steps

1. Admin navigates to `/governance/delegation`.
2. Admin clicks "New Delegation" to open the form.
3. Admin enters the delegate email, start date, end date, and an
   optional reason (e.g., "Annual leave — 2 weeks").
4. Admin clicks "Create Delegation". The form submits to
   `POST /api/v1/governance/delegations/`.
5. The delegation appears in the table with: delegate name/email, date
   range, status (Active/Inactive), reason, and a Revoke button for
   active delegations.
6. During the active window, when an access request is submitted for
   approval, `GovernanceBusinessRules._validate_access_request_approval()`
   checks the `ApprovalDelegation` model. The delegate can approve on
   the delegator's behalf.
7. To end the delegation early, the admin clicks "Revoke" on the
   delegation row. This fires
   `DELETE /api/v1/governance/delegations/{id}/`.

## Expected Outcome

- Active delegations are listed in the table with correct metadata.
- At approval time, the delegate is recognized as a valid approver
  during the delegation window.
- Revoking a delegation immediately removes the delegate's authority.
- `APPROVAL_DELEGATION_CREATED` and `APPROVAL_DELEGATION_REVOKED`
  audit events are emitted.

## Error Handling

| Condition | Expected Response |
|---|---|
| Delegate email not found in tenant | Form error: "Delegate not found" |
| End date before start date | Form validation: "End date must be after start date" |
| Empty email | Form validation: "Delegate email is required" |
| Unauthenticated / wrong role | `403 Forbidden` |

## Related

- Concepts: [Governance](../../concepts/governance.md), [Users and Roles](../../concepts/users-and-roles.md)
- Journeys: [JOURNEY-CPO-011](../journeys/JOURNEY-CPO-011.md) (Approval Inbox Flow)
- Components: `DelegationSettingsPage`, `SearchablePicker`
- Phase 278 tasks: `278.I.3` (Delegation UX)
- Phase 272: `ApprovalDelegation` model (272.6), ABAC evaluation (272.3)
- E2E: `delegation-crud.spec.ts` (278.V.11)
