# UC-AUTH-008: Platform Admin Impersonates a User

**Persona:** [Marketplace Platform Admin (MPA)](../personas/platform-admin/index.md)
**MVP Tier:** :large_orange_circle: (NET-NEW)
**Phase 235.4 Test:** `hub/apps/tenants/tests/test_admin_impersonate_phase_235_4.py::TestImpersonateStartHappyPath`
**E2E:** `frontend/e2e/journeys/pa/JOURNEY-MPA-010.spec.ts`

## Description

A platform admin opens a time-boxed impersonation session against a
support target's user account. The SPA swaps its bearer token to the
short-lived impersonation JWT (minted as the target, stamped with the
`impersonation_session_id` claim), persists it in sessionStorage so a
reload does not silently revert the identity, and shows a red banner for
the whole session. Every action taken while impersonating runs AS the
target and is forensically linked to the session in the audit trail.
Exit (or logout) ends the session and clears the local state.

## Preconditions

- The operator is authenticated and holds the PLATFORM_ADMIN role.
- The target user is ACTIVE, is NOT a PLATFORM_ADMIN, and belongs to a
  tenant with `impersonation_allowed=True`.
- The operator supplies a justification (10–2000 characters).

## Steps

1. Operator opens the target user's edit page (`/admin/users/:id/edit`)
   and clicks **Impersonate user**.
2. The dialog collects the justification + the session duration
   (5–240 minutes, default 60).
3. `POST /api/v1/admin/impersonate/` returns the session metadata +
   the short-lived impersonation JWT.
4. The SPA persists the bearer (sessionStorage), attaches it to every
   subsequent request (replacing the operator's bearer), and scopes
   `X-Tenant-ID` to the impersonated tenant. The red
   **IMPERSONATING** banner renders at the top of every page.
5. All actions run as the target; audit rows carry the
   `impersonation_session_id`.
6. **Exit** calls `POST /api/v1/admin/impersonate/exit/` with the
   session id, ends the session server-side, clears the local state,
   and reloads the SPA as the operator. Logout clears the state too.

## Acceptance Criteria

- Starting a session shows the red banner and swaps the identity:
  `/auth/me/` under the SPA's bearer reports the TARGET.
- A page reload keeps the impersonation active (sessionStorage).
- The audit trail contains `IMPERSONATION_STARTED` (and `ENDED` after
  exit) rows for the session.
- Exit and logout remove the stored bearer; the banner unmounts.
