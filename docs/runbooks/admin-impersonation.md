# Runbook — PLATFORM_ADMIN impersonation

**Phase 235.4 / 235.6.4** — Operational guide for the
`POST /api/v1/admin/impersonate/` capability.

## When to use this runbook

- A customer reports a bug you cannot reproduce from your own tenant.
- A support ticket requires inspecting a customer's view (e.g. "I can't
  see asset X" — you need to see exactly what their session sees, with
  their roles and their tenant context).
- An incident requires verifying a remediation landed correctly for a
  specific user.

**When NOT to use:** never use impersonation to mutate data on a
customer's behalf without their written authorisation. Impersonation
is a read-and-debug capability; mutations are recorded under BOTH the
operator's identity AND the impersonated user's identity in the audit
log, but the consent model places the customer's agreement front and
centre. If a customer wants you to act on their behalf, they should
flip a delegated permission, not invite impersonation.

## Pre-flight checks

1. **Tenant has opted in.** The feature is per-tenant gated by
   `Tenant.impersonation_allowed` (default `False`). If the flag is
   `False`, the start endpoint returns:

   ```
   HTTP 403 { "code": "IMPERSONATION_NOT_ENABLED", ... }
   ```

   Customer authorisation typically comes via a BAA / DPA addendum.
   Flip the flag via:

   ```bash
   # Via the tenants admin API:
   curl -X PUT https://meshant-internal.example.com/api/v1/admin/tenants/$TENANT_ID/feature-flags/ \
        -H "Authorization: Bearer $OPERATOR_JWT" \
        -H "Content-Type: application/json" \
        -d '{
              "reason": "BAA addendum signed 2026-05-10 ref TICKET-1234",
              "impersonation_allowed": true
            }'
   ```

   `impersonation_allowed` is registered as a sensitive flag (see
   [admin-feature-flag-flip.md](admin-feature-flag-flip.md)) so the
   flip awaits a second PLATFORM_ADMIN's approval.

2. **You are NOT impersonating a PLATFORM_ADMIN.** The endpoint rejects
   with `TARGET_IS_PLATFORM_ADMIN` if the target user carries the
   PLATFORM_ADMIN role. The role transcends tenant boundaries; an
   admin-on-admin impersonation would blur the actor / effective_user
   audit trail.

3. **The target user is ACTIVE.** DISABLED / INVITED users cannot
   themselves log in, so impersonating them would let you perform
   actions they could not legitimately perform. The endpoint rejects
   with `TARGET_INACTIVE`.

## Starting a session

### From the SPA (preferred)

1. Navigate to `/admin/users/<user-uuid>/edit` for the target user.
2. Click the red `🛡 Impersonate user` button.
3. Enter a justification (≥ 10 characters — pinned in the audit log)
   and select a duration in minutes (5–240, defaults to the tenant's
   `impersonation_default_max_minutes`).
4. Click `Start session`. The SPA swaps the JWT, persists it via
   `localStorage["impersonation_access_token"]`, and reloads — you'll
   see the red top banner indicating you are now viewing the platform
   as the impersonated user.

### From the CLI

```bash
curl -X POST https://meshant-internal.example.com/api/v1/admin/impersonate/ \
     -H "Authorization: Bearer $OPERATOR_JWT" \
     -H "Content-Type: application/json" \
     -d '{
           "user_id": "<target-user-uuid>",
           "reason": "Ticket #1234 — reproducing schema-drift bug",
           "max_minutes": 60
         }'
```

Response carries an `access_token` (short-lived JWT, TTL = max_minutes
× 60 seconds) you can use for subsequent requests. Send it as
`Authorization: Bearer <token>` and you'll be authenticated as the
impersonated user with `impersonation_session_id` tagged on the
request for the duration of the session.

## What the audit log captures

The start endpoint emits TWO `IMPERSONATION_STARTED` audit rows:

- One under the **target tenant's** context (auditor-facing — appears
  in the customer's audit feed when they review their tenant).
- One under the **impersonator's home tenant's** context
  (security-team-facing — appears in the platform's audit feed).

Both rows carry the same `impersonation_session_id` in `details_json`,
so audit-replay queries can correlate the two views.

While the session is ACTIVE, every audit row written under the
impersonation JWT carries `request.impersonation_session_id` (set by
`ImpersonationMiddleware`). Audit emitters use this to stamp
`actor=impersonator, effective_user=impersonated, session_id` into
`details_json` — turning every action the operator takes into a
forensically-linked row.

## Ending a session

### Operator-driven (manual exit — preferred)

Click the `Exit` button on the red top banner. The SPA calls
`POST /api/v1/admin/impersonate/exit/` with the session UUID; the
backend ends the session (`status=ENDED, end_reason=manual_exit`),
emits `IMPERSONATION_ENDED`, and the SPA reloads back to your operator
identity.

### Automatic expiration (cron-driven)

The `expire_impersonation_sessions` management command runs every
5 minutes and ends every ACTIVE session whose `expires_at` has
elapsed. Stamps `end_reason="expired"`. The JWT itself ALSO becomes
invalid at its natural `exp` — defence-in-depth.

### Force-end someone else's session

A different PLATFORM_ADMIN can force-end your session — useful when
an operator's shift ends and the next shift discovers a session
left open. The `IsPlatformAdminOrActiveImpersonator` permission
accepts both:

- Authenticated PLATFORM_ADMIN (cookie/Bearer session) — force-ender.
- The original impersonator (using the impersonation JWT itself).

`details_json.ended_by_user_id` records who actually clicked Exit,
distinct from `impersonator_user_id` (who started the session).

## Common operational scenarios

### A session won't end ("ALREADY_ENDED" on every retry)

The session has already transitioned to ENDED — either by the cron,
another operator's force-end, or your own previous exit click that
succeeded silently. Check the audit feed for the matching
`IMPERSONATION_ENDED` event and the `end_reason` field. Nothing to
do — the JWT is already invalid.

### The Exit button always 403s

Check that `Tenant.impersonation_allowed=True` for the target tenant.
If the tenant flag was flipped to `False` between start and exit, the
backend won't reject the exit (the permission depends on the live
session, not the tenant flag), but a 403 there suggests the session
itself was already ended and the JWT no longer carries a valid
`impersonation_session_id` claim. Inspect via the audit feed.

### Cache-poisoned impersonation persists across log-out

Logout calls `apiClient.clearTokens()` which also clears
`_impersonationToken` + `localStorage["impersonation_access_token"]`
(per Phase 235.4 audit-fix Gap 1). If you observe a persistent
impersonation banner after logout, hard-refresh the browser
(`Ctrl+Shift+R`) and re-login — the local storage entry should be
gone. Report any persistent occurrence as a bug.

### A customer disputes that you impersonated them

Pull every `IMPERSONATION_STARTED` and `IMPERSONATION_ENDED` row
keyed by `tenant_id = customer's tenant`. The audit trail is the
source of truth — every session has a start row in their tenant +
an end row. The `actor_user_id` on those rows is your operator
identity; the `details_json.reason` is your stated justification.

## Observability

- Grafana panel **"Impersonation lifecycle events (rate, 5m)"** in
  [admin-ops dashboard](../../monitoring/grafana/dashboards/admin-ops.json)
  shows `IMPERSONATION_STARTED / ENDED / REJECTED` rates.
- Non-zero `IMPERSONATION_REJECTED` is a security signal — investigate
  whose `actor_user_id` is generating the rejections. Three rejection
  codes (`details_json.code`):
  - `IMPERSONATION_NOT_ENABLED` — tenant has not opted in (likely a
    misconfigured operator script).
  - `TARGET_IS_PLATFORM_ADMIN` — someone tried to impersonate another
    operator (suspicious; investigate).
  - `TARGET_INACTIVE` — someone tried to impersonate a DISABLED user
    (likely an operator script that didn't validate state first).

## Related

- **Spec:** `openspec/changes/preprod01/proposal.md` § Phase 235.4
- **Backend:** [`hub/apps/tenants/admin_impersonate.py`](../../hub/apps/tenants/admin_impersonate.py)
- **Frontend:** [`frontend/src/features/admin/impersonation/`](../../frontend/src/features/admin/impersonation/)
- **Tests:** [`hub/apps/tenants/tests/test_admin_impersonate_phase_235_4.py`](../../hub/apps/tenants/tests/test_admin_impersonate_phase_235_4.py)

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
