# Runbook — PLATFORM_ADMIN per-tenant feature-flag flip

**Phase 235.1 / 235.6.5** — Operational guide for the
`PUT /api/v1/admin/tenants/{id}/feature-flags/` capability.

## When to use this runbook

- A customer requests a feature (e.g. `federated_import_enabled`,
  `impersonation_allowed`) be enabled on their tenant.
- A capacity / security event requires disabling a feature on one or
  more tenants (e.g. flipping `federated_import_enabled` to `False`
  on every tenant during a marketplace-connector incident).
- An incident requires reverting an ill-advised flag flip.

## Pre-flight checks

1. **You are a PLATFORM_ADMIN.** TENANT_ADMINs cannot use this
   endpoint; they have their own `PATCH /api/v1/tenants/me/feature-flags/`
   for the customer-controllable subset.

2. **You have the flag name from the registry.** All flippable flags
   live in [`hub/apps/tenants/feature_flag_registry.py`](../../hub/apps/tenants/feature_flag_registry.py).
   Each entry carries:
   - `name` — the column on `Tenant` (e.g. `federated_import_enabled`).
   - `sensitive: bool` — whether the flip requires a second PLATFORM_ADMIN's approval.
   - `default_existing_tenants` / `default_new_tenants` — the rollout default.
   - `description` + `related_phase` — operator-facing context.

3. **You have a justification.** The API requires a `reason` field
   ≥ 10 characters. It lands in the `TENANT_FEATURE_FLAG_CHANGED`
   audit-row's `details_json.reason`, so phrase it like an incident
   tag: `"Ticket #1234 — customer enabled federated import after DPA review"`.

## Flipping a non-sensitive flag

Direct flip — no second-admin approval required. Lands immediately
inside one atomic transaction and emits `TENANT_FEATURE_FLAG_CHANGED`.

```bash
curl -X PUT https://meshant-internal.example.com/api/v1/admin/tenants/$TENANT_ID/feature-flags/ \
     -H "Authorization: Bearer $OPERATOR_JWT" \
     -H "Content-Type: application/json" \
     -d '{
           "reason": "Ticket #1234 — enabling datasets API per customer request",
           "datasets_enabled": true
         }'
```

Response: HTTP 200 with `applied[]` listing the flip(s) that landed
+ an empty `pending_approvals[]`.

## Flipping a sensitive flag — two-person rule

Sensitive flags (e.g. `impersonation_allowed`, `data_quality_enabled`)
require a SECOND PLATFORM_ADMIN's approval before the flip lands. The
flow:

1. **First admin opens the request.** Same endpoint call as
   non-sensitive flip; the response is HTTP 202 with
   `pending_approvals[]` carrying the new `FeatureFlagFlipApproval`
   row's UUID. Emits `FEATURE_FLAG_FLIP_APPROVAL_REQUESTED` audit.
   No flag change yet.

   ```bash
   curl -X PUT https://meshant-internal.example.com/api/v1/admin/tenants/$TENANT_ID/feature-flags/ \
        -H "Authorization: Bearer $FIRST_ADMIN_JWT" \
        -H "Content-Type: application/json" \
        -d '{
              "reason": "Ticket #1234 — BAA addendum signed 2026-05-10",
              "impersonation_allowed": true
            }'
   ```

2. **Second admin reviews.** The pending request is queryable via
   `GET /api/v1/admin/tenants/$TENANT_ID/feature-flags/` — every flag's
   row carries any pending approval IDs targeting it.

3. **Second admin approves.** A DIFFERENT PLATFORM_ADMIN posts to
   the approval endpoint:

   ```bash
   curl -X POST https://meshant-internal.example.com/api/v1/admin/feature-flag-approvals/$APPROVAL_ID/approve/ \
        -H "Authorization: Bearer $SECOND_ADMIN_JWT"
   ```

   Inside ONE atomic transaction the backend:
   - Marks the approval row as `APPROVED` (status, approved_by, approved_at).
   - Flips the flag on the tenant.
   - Emits BOTH `FEATURE_FLAG_FLIP_APPROVED` AND `TENANT_FEATURE_FLAG_CHANGED`
     events linked by `approval_id`.

   Self-approval is rejected at TWO layers (defence in depth) — model
   guard + API permission — with HTTP 403 `SELF_APPROVAL_FORBIDDEN`.

## Rate limits

`PUT /api/v1/admin/tenants/{id}/feature-flags/` is rate-limited to
**60 flip requests per admin per hour** (REQ-ADMIN-FF-002). A
misconfigured ops script burning through flags burns up its own
budget — the limit is per-admin not per-tenant.

Exceeding returns HTTP 429 with `rate_limit_observed` reflecting the
current bucket count. Wait for the bucket to roll over or contact
another PLATFORM_ADMIN to share the workload.

## What the audit log captures

Three audit constants land per flip:

- **`TENANT_FEATURE_FLAG_CHANGED`** — fires when the flag value
  actually changes. `details_json` carries `flag`, `old_value`,
  `new_value`, `reason`, `requested_by`, `approver` (= requested_by
  for non-sensitive flips; the second admin for sensitive flips that
  traversed the two-person rule).
- **`FEATURE_FLAG_FLIP_APPROVAL_REQUESTED`** — only on the FIRST step
  of a sensitive flip. `details_json` carries `flag`, `requested_value`,
  `reason`, `requested_by`, `approval_id`, `tenant_id`.
- **`FEATURE_FLAG_FLIP_APPROVED`** — only on the SECOND step of a
  sensitive flip. Same `details_json` shape as the change event plus
  `approver` and `approval_id` so audit-replay can join the two
  events.

All three events use `result="SUCCESS"`; rejection paths (unknown flag,
short reason, rate-limit exceeded, self-approval forbidden) return
4xx BEFORE any audit emission would have fired.

## Common operational scenarios

### A flip was approved but the flag still reads False on the tenant

Look for an exception in `FEATURE_FLAG_FLIP_APPROVED` log lines. The
approval-and-flip are wrapped in `transaction.atomic(using="admin")`
so a model save failure rolls BOTH events back. If you see
`FEATURE_FLAG_FLIP_APPROVED` but no matching
`TENANT_FEATURE_FLAG_CHANGED`, that's a real bug — file a P1.

### Two pending approvals for the same flag

Cannot happen — there's a partial unique constraint on
`(tenant, flag)` with `status='PENDING'`. The SECOND request would
have 409'd with `APPROVAL_ALREADY_PENDING`. Inspect the database
directly:

```sql
SELECT id, flag, status, requested_at
FROM feature_flag_flip_approvals
WHERE tenant_id = '<tenant-uuid>' AND status = 'PENDING';
```

### An approval is stuck PENDING for days

There's no automatic expiry yet — the model carries the `EXPIRED`
status for future use. Ask the original requester to either chase a
second admin OR close the request via direct DB update (logged via
manual audit):

```sql
UPDATE feature_flag_flip_approvals
SET status = 'REJECTED', updated_at = now()
WHERE id = '<approval-uuid>';
```

After closing, the requester can open a fresh request.

### Self-approval shows up as a 403

Working as intended. The two-person rule is the load-bearing
security invariant. The same admin who opened the request cannot
approve it. If you absolutely need to flip a flag and no second
PLATFORM_ADMIN is online, escalate to the on-call rotation —
NEVER work around the two-person rule via direct DB mutation
without a follow-up audit row explaining why.

## Observability

- Grafana panel **"Feature-flag flip events (rate, 5m)"** in
  [admin-ops dashboard](../../monitoring/grafana/dashboards/admin-ops.json)
  graphs `TENANT_FEATURE_FLAG_CHANGED / FEATURE_FLAG_FLIP_APPROVAL_REQUESTED
  / FEATURE_FLAG_FLIP_APPROVED` rates.
- A gap between `REQUESTED` and `APPROVED` rates sustained for hours
  indicates approval-queue backlog — surface to ops leadership.
- A burst of `result=FAILURE` on the `feature-flag-approvals/.../approve/`
  endpoint (visible via the admin audit-failure panel) flags repeated
  self-approval attempts — likely a misconfigured ops script.

## Related

- **Spec:** `openspec/changes/preprod01/proposal.md` § Phase 235.1
- **Backend:** [`hub/apps/tenants/admin_feature_flag_views.py`](../../hub/apps/tenants/admin_feature_flag_views.py)
- **Registry:** [`hub/apps/tenants/feature_flag_registry.py`](../../hub/apps/tenants/feature_flag_registry.py)
- **Approval model:** [`hub/apps/tenants/models.py`](../../hub/apps/tenants/models.py) (`FeatureFlagFlipApproval`)
- **Frontend:** [`frontend/src/features/admin/components/TenantFeatureFlagsAdminPage.tsx`](../../frontend/src/features/admin/components/TenantFeatureFlagsAdminPage.tsx)

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
