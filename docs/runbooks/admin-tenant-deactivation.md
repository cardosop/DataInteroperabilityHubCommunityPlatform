# Runbook — PLATFORM_ADMIN tenant deactivation (soft-delete + 90-day grace + hard-delete)

**Phase 235.3 / 235.6.AUDIT.2** — Operational guide for the
`DELETE /api/v1/admin/tenants/{id}/` capability and the daily
`tenant_hard_delete_sweep` cron.

## When to use this runbook

- A customer has requested account closure and you need to schedule
  the irreversible delete.
- An internal demo / test tenant has reached end-of-life and should be
  removed from the platform.
- A trial expired and the tenant's grace window also elapsed —
  ordinary cleanup.

**When NOT to use:** never call this endpoint to "pause" a tenant.
Use `POST /api/v1/tenants/{id}/suspend/` for reversible holds. The
soft-delete here starts a 90-day clock to IRREVERSIBLE hard-delete.

## The two-phase deletion contract

The endpoint never hard-deletes data inline. It runs in two phases:

1. **Soft-delete (this endpoint)** — flips the tenant to
   `status=DELETED`, stamps `scheduled_for_deletion_at = now()`,
   stamps `deleted_at = now()`, emits a single `TENANT_SOFT_DELETED`
   audit event. The tenant row stays in the database. All data is
   recoverable for 90 days via `Tenant.restore()` (clears both
   timestamps + flips status back to ACTIVE).

2. **Hard-delete (daily cron)** — the
   `tenant_hard_delete_sweep` Kubernetes CronJob runs daily at 04:30
   UTC. It walks tenants whose `scheduled_for_deletion_at` is older
   than 90 days AND re-validates the legal-hold + DSAR-restriction
   blockers under a row lock. Eligible tenants emit
   `TENANT_HARD_DELETED` BEFORE the cascade (the audit row survives
   via `AuditEvent.tenant on_delete=SET_NULL`), then the ORM cascade
   walks the FK graph and deletes the tenant + all `on_delete=CASCADE`
   children.

## Pre-flight checks

1. **You are a PLATFORM_ADMIN.** The endpoint is gated by
   `IsPlatformAdmin`. TENANT_ADMINs cannot delete their own tenant via
   this surface.

2. **The tenant has NO active legal hold.** `Tenant.legal_hold=True`
   blocks BOTH the soft-delete endpoint AND the hard-delete sweep.
   Lift the hold (after legal sign-off) via the platform-admin
   feature-flag flow before deleting:

   ```bash
   curl -X PUT https://meshant-internal.example.com/api/v1/admin/tenants/$TENANT_ID/feature-flags/ \
        -H "Authorization: Bearer $OPERATOR_JWT" \
        -H "Content-Type: application/json" \
        -d '{
              "reason": "Legal hold lifted per memo 2026-05-10 ref MATTER-1234",
              "legal_hold": false
            }'
   ```

   The flag is registered as sensitive, so the flip requires a second
   PLATFORM_ADMIN's approval (see
   [admin-feature-flag-flip.md](admin-feature-flag-flip.md)).

3. **The tenant has NO open RESTRICTION-class DSAR.** A DSAR with
   `request_type=RESTRICTION` and a non-terminal status
   (`UNDER_REVIEW`, `PENDING`) blocks both phases. Resolve the DSAR
   first via the DSAR fulfilment surface.

4. **You have written authorisation.** The audit row's
   `details_json` records `deleted_by = your UUID`. An auditor will
   trace this back to your account; have the customer's authorisation
   ticket or contract clause on file before clicking.

## Soft-deleting a tenant

### From the CLI

```bash
curl -X DELETE https://meshant-internal.example.com/api/v1/admin/tenants/$TENANT_ID/ \
     -H "Authorization: Bearer $OPERATOR_JWT"
```

Response shapes:

- **HTTP 200** — soft-delete succeeded. Body carries
  `scheduled_for_deletion_at` + `hard_delete_after` (90 days later).
  The tenant is now in `status=DELETED`.
- **HTTP 422** + `code=LEGAL_HOLD_ACTIVE` — `Tenant.legal_hold` is
  True. Lift before retrying.
- **HTTP 422** + `code=DSAR_RESTRICTION_ACTIVE` — an open RESTRICTION
  DSAR exists. Resolve before retrying.
- **HTTP 409** + `code=ALREADY_DELETED` — the tenant is already
  soft-deleted. Idempotent — no error, just nothing to do.

### From the SPA

Navigate to `/admin` → Tenants tab → click the red **Deactivate**
button next to the tenant row. The SPA pre-disables the button when
`tenant.legal_hold === true` and surfaces the tooltip "Legal hold
active — lift the hold before deactivating" so you see the precondition
without clicking + getting a 422 toast.

A `ConfirmDialog` then renders with the danger variant + a confirm
button reading **Deactivate (irreversible after 90 days)**. After
confirmation, the SPA calls the DELETE endpoint and refetches the
tenants list.

## Restoring a tenant within the grace window

`Tenant.restore()` clears BOTH `deleted_at` AND
`scheduled_for_deletion_at` together — treat them as a coupled pair.
Clearing only one would leave the sweep with stale grace-window state.

There is currently NO REST endpoint for restore — you restore from a
Django management shell:

```bash
docker compose exec api-service python hub/manage.py shell <<'EOF'
from hub.apps.tenants.models import Tenant
t = Tenant.all_objects.get(slug='customer-slug')
t.restore()
print(f"Restored: status={t.status} deleted_at={t.deleted_at} sched={t.scheduled_for_deletion_at}")
EOF
```

The audit log captures the restore via the standard `TENANT_UPDATED`
audit emission — auditors see the soft-delete row + the restore row in
sequence.

## How the hard-delete sweep behaves

The `tenant_hard_delete_sweep` work function
([`hub/apps/tenants/tenant_hard_delete_sweep.py`](../../hub/apps/tenants/tenant_hard_delete_sweep.py))
walks every tenant whose `scheduled_for_deletion_at < now() - 90 days`.
For each candidate, in one atomic transaction:

1. **Re-lock the row** via `select_for_update(skip_locked=True)` — two
   concurrent sweep instances (e.g. a daily cron + an operator-
   triggered Job) cannot both delete the same tenant. The second
   simply skips with `lock_contention_or_state_drift`.

2. **Re-validate eligibility under the lock**:
   - `scheduled_for_deletion_at` must still be set AND ≥ 90 days old
     (an `unrestore()` between candidate enumeration + lock acquisition
     would have cleared it).
   - `legal_hold` must still be False (a hold acquired DURING the
     grace window — common when discovery is opened post-deletion-
     scheduling — pauses the sweep with `legal_hold_active`).
   - No open DSAR-RESTRICTION targeting the tenant (a subject who
     opens a RESTRICTION DSAR after the soft-delete still gets
     coverage; the sweep skips with `dsar_restriction_active`).

3. **Emit `TENANT_HARD_DELETED`** with full forensic context
   (`tenant_id`, `slug`, `display_name`, `scheduled_for_deletion_at`,
   `hard_deleted_at`, `sweep_run_id`). The audit row survives the
   cascade because `AuditEvent.tenant on_delete=SET_NULL` (Phase 234.1
   contract).

4. **`tenant.delete()` cascades.** The ORM walks every FK with
   `on_delete=CASCADE` — assets, datasets, files, audit-event
   tenant_id columns become NULL, users with `tenant=tenant` cascade.

The sweep summary is recorded on the matching `Job` row:

```json
{
  "evaluated_count": 5,
  "grace_window_days": 90,
  "hard_deleted_count": 3,
  "hard_deleted": [{"tenant_id": "...", "slug": "...", "hard_deleted_at": "..."}, ...],
  "skipped": [{"tenant_id": "...", "reason": "legal_hold_active"}, ...]
}
```

## Forcing an immediate hard-delete (rare)

If a tenant must be hard-deleted BEFORE the 90-day grace elapses
(legal court order, GDPR right-to-erasure that explicitly requires
immediate deletion), the operator triggers the sweep with a back-dated
`scheduled_for_deletion_at`:

```bash
docker compose exec api-service python hub/manage.py shell <<'EOF'
from hub.apps.tenants.models import Tenant
from django.utils import timezone
from datetime import timedelta
t = Tenant.all_objects.get(slug='customer-slug')
# Back-date the soft-delete marker to 91 days ago — the next sweep
# run will pick it up.
t.scheduled_for_deletion_at = timezone.now() - timedelta(days=91)
t.save(update_fields=["scheduled_for_deletion_at", "updated_at"])
EOF

# Then trigger an out-of-band sweep:
docker compose exec api-service python hub/manage.py tenant_hard_delete_sweep
```

The sweep emits the standard `TENANT_HARD_DELETED` event; the
`scheduled_for_deletion_at` in `details_json` is the back-dated value
+ an out-of-band audit note explaining the early deletion is required
to make the forensic trail self-explanatory.

## Common operational scenarios

### Spike in HARD_DELETED rate

Check the [admin-ops Grafana dashboard](../../monitoring/grafana/dashboards/admin-ops.json)
panel "Tenant lifecycle events (rate, 5m)". The hard-delete rate is
expected to be ~0 most days (most tenants soft-delete + restore or are
never deleted). A spike means either:

- A batch cleanup of trial tenants (planned — verify against the
  ops calendar).
- A sweep ran against a back-log of soft-deletes (verify by checking
  the `evaluated_count` on the sweep Job row).
- An unauthorised operator is mass-deleting (verify against the
  audit log's `deleted_by` field).

### "ALREADY_DELETED" on every retry

The tenant is already in `status=DELETED`. Check the audit log for
the matching `TENANT_SOFT_DELETED` event; the `actor_user_id` is who
deleted it. To restore, use the management-shell `restore()` flow
above.

### Sweep skips a tenant repeatedly with "legal_hold_active"

The hold is genuine. The legal team must lift it via the feature-flag
flow before the sweep will proceed. The audit-replay shows EVERY
sweep run's skip + reason, so an auditor can prove the platform
respected the hold throughout.

### Sweep skips with "dsar_restriction_active"

A subject opened a DSAR-RESTRICTION on the tenant during the grace
window. The DSAR fulfilment process must complete (CLOSED_FULFILLED or
CLOSED_REJECTED) before the sweep will hard-delete. The audit-replay
captures both the DSAR row's status changes + the sweep skips.

### A customer disputes that their tenant was deleted

Pull every `TENANT_SOFT_DELETED` and `TENANT_HARD_DELETED` event with
`details_json.tenant_id = <customer-tenant-uuid>`. The
`TENANT_SOFT_DELETED.actor_user_id` is the PLATFORM_ADMIN who
initiated the deletion + the `details_json.scheduled_for_deletion_at`
is when the 90-day clock started. The matching `TENANT_HARD_DELETED`
event 90+ days later confirms the cascade ran; `sweep_run_id`
correlates to the Job row that executed it.

## Observability

- Grafana panel **"Tenant lifecycle events (rate, 5m)"** in
  [admin-ops dashboard](../../monitoring/grafana/dashboards/admin-ops.json)
  graphs `TENANT_CREATED / TENANT_SOFT_DELETED / TENANT_HARD_DELETED`
  rates.
- The cumulative-counts panel shows 24h totals — useful for capacity
  planning and post-incident review.

## Related

- **Spec:** `openspec/changes/preprod01/proposal.md` § Phase 235.3
- **Soft-delete endpoint:** [`hub/apps/tenants/admin_tenant_delete.py`](../../hub/apps/tenants/admin_tenant_delete.py)
- **Hard-delete sweep:** [`hub/apps/tenants/tenant_hard_delete_sweep.py`](../../hub/apps/tenants/tenant_hard_delete_sweep.py)
- **Management command:** [`hub/apps/tenants/management/commands/tenant_hard_delete_sweep.py`](../../hub/apps/tenants/management/commands/tenant_hard_delete_sweep.py)
- **DSAR-restriction blocker helper:** [`hub/apps/governance/dsar_retention_block.py`](../../hub/apps/governance/dsar_retention_block.py)
- **Tests:** [`hub/apps/tenants/tests/test_admin_tenant_delete_phase_235_3.py`](../../hub/apps/tenants/tests/test_admin_tenant_delete_phase_235_3.py)

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
