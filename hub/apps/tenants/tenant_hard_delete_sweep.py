"""
Phase 235.3 — Tenant hard-delete sweep (90-day grace cron).

After the Phase 235.3 PLATFORM_ADMIN tenant-soft-delete endpoint stamps
``Tenant.scheduled_for_deletion_at = now()``, this daily cron hard-deletes
the tenant 90 days later — provided ``legal_hold=False`` AND no open
RESTRICTION-class DSAR is targeting the tenant.

Re-check contract
=================

The sweep re-checks ``legal_hold`` AND DSAR-restriction at sweep time
(NOT at soft-delete time). Two scenarios make this load-bearing:

* A tenant soft-deleted on day 0 with ``legal_hold=False`` and no
  DSARs. On day 45, legal acquires a hold (sets ``legal_hold=True``).
  The sweep MUST skip this tenant on day 91 — the operator's
  earlier intent to delete is overridden by the later regulatory
  hold.
* A tenant soft-deleted on day 0. On day 60, a subject opens a
  RESTRICTION DSAR. The sweep MUST skip on day 91 until the DSAR
  resolves.

Audit trail
===========

* ``TENANT_HARD_DELETED`` emitted ONCE per hard-deleted tenant,
  BEFORE the cascade. Survives the cascade via
  ``AuditEvent.tenant.on_delete=SET_NULL`` (Phase 234.1 contract);
  the tenant_id column nulls but the row stays as system-level audit
  history.
* The matching Job row carries the sweep summary (counts, skipped
  reasons) for ops dashboards.

Idempotency
===========

Re-running the sweep on the same day is a no-op: the first run
hard-deletes eligible tenants, leaving none for the second run.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from hub.apps.audit import event_types as _audit_et
from hub.apps.audit.utils import create_audit_event
from hub.apps.governance.dsar_retention_block import (
    tenant_blocked_by_open_dsar_restriction,
)

from .models import Tenant

logger = logging.getLogger(__name__)

GRACE_WINDOW_DAYS: int = 90


def _pre_sweep_tenant(tenant_id_str: str) -> dict[str, Any]:
    """W4.3 (R2-B6/E1-E3) - itemized pre-sweep of rows that would block
    the tenant hard-delete cascade or survive it as garbage.

    Runs INSIDE ``tenant_context(tenant_id)`` — mandatory for the
    provider estate tables (strict RLS policy + FORCE ROW LEVEL
    SECURITY: an unarmed DELETE matches zero rows) and correct per the
    CLAUDE.md worker contract for every tenant-scoped model touched.

    Order matters:

    1.  registered provider offboarding sweepers (the Delta Sharing
        estate — ``on_delete=PROTECT`` rows),
    2.  PROTECT/RESTRICT referrer rows of the tenant's users (feature-
        flag approvals, impersonation sessions, plan-price approvals —
        they PROTECT the users, so users cannot be deleted first),
    3.  the tenant's users (``User.tenant`` is RESTRICT — the R2-B6
        blocker for every real tenant),
    4.  bare-UUID tenant references that no FK cascade would remove
        (event bus rows, idempotency keys, request-dedup rows, BaaS
        usage records) — E3 hygiene so no tenant UUID garbage survives.

    The tenant row itself is deleted by the caller AFTER the pre-sweep,
    outside ``tenant_context`` (the Django cascade collector must not be
    RLS-constrained while it walks SET_NULL/CASCADE children).

    Returns the itemized counts for the ``TENANT_HARD_DELETED`` audit.
    """
    # baas is the paid layer — guarded for both core-only absence forms
    # (W7.1); when absent its usage rows cannot exist, so the itemized
    # count degrades to zero (the offboarding sweepers cover the rest).
    try:
        from hub.apps.baas.models import BaaSUsageRecord
    except (RuntimeError, ModuleNotFoundError):
        BaaSUsageRecord = None  # type: ignore[assignment]
    from hub.apps.core.bug_prevention.models import IdempotencyKey, RequestDeduplication
    from hub.apps.core.events.models import Event
    from hub.apps.tenants.request_tenant import tenant_context
    from hub.apps.users.models import User
    from hub.apps.users.protected_referrers import delete_protected_referrers_for_users

    from .offboarding import run_tenant_offboard_sweepers

    pre_sweep: dict[str, Any] = {}
    with tenant_context(tenant_id_str):
        pre_sweep.update(run_tenant_offboard_sweepers(tenant_id_str))

        user_ids = list(
            User.objects.filter(tenant_id=tenant_id_str).values_list("id", flat=True)
        )
        if user_ids:
            pre_sweep["user_protected_referrers"] = (
                delete_protected_referrers_for_users(user_ids)
            )

        # Count BEFORE delete: queryset.delete() totals include the
        # cascaded children (roles, memberships, tokens, keys), which
        # would inflate the itemized per-model counts.
        user_qs = User.objects.filter(tenant_id=tenant_id_str)
        pre_sweep["users"] = user_qs.count()
        user_qs.delete()

        event_qs = Event.objects.filter(tenant_id=tenant_id_str)
        pre_sweep["events"] = event_qs.count()
        event_qs.delete()
        idem_qs = IdempotencyKey.objects.filter(tenant_id=tenant_id_str)
        pre_sweep["idempotency_keys"] = idem_qs.count()
        idem_qs.delete()
        dedup_qs = RequestDeduplication.objects.filter(tenant_id=tenant_id_str)
        pre_sweep["request_deduplication"] = dedup_qs.count()
        dedup_qs.delete()
        if BaaSUsageRecord is not None:
            usage_qs = BaaSUsageRecord.objects.filter(tenant_id=tenant_id_str)
            pre_sweep["baas_usage_records"] = usage_qs.count()
            usage_qs.delete()
        else:
            pre_sweep["baas_usage_records"] = 0

    return pre_sweep


def _hard_delete_one_tenant(
    *, tenant_id, sweep_run_id: str | None, drill_skip_grace: bool = False
) -> dict[str, Any] | None:
    """Atomically re-lock + re-validate + hard-delete one tenant.

    Phase 235.3 audit-fix Gap 2 — the lookup is now via
    ``select_for_update(skip_locked=True)`` inside the function's own
    atomic block. The previous design materialised candidates eagerly
    and iterated without per-row locks; two concurrent sweep runs
    (e.g. the daily cron + an operator-triggered Job) could BOTH
    iterate the same tenant, BOTH pass the legal-hold / DSAR
    re-checks, and BOTH emit ``TENANT_HARD_DELETED`` for the same
    hard-delete attempt — the second ``tenant.delete()`` would raise
    (the row is gone) but the second audit emission would have
    already committed in its own transaction. ``SKIP LOCKED``
    serialises the two runs cleanly: the second simply skips any
    tenant the first one has locked.

    Returns the summary entry on a successful hard-delete, or
    ``None`` if the row was locked by another sweep, no longer
    eligible by the time we re-acquired it (legal_hold flipped, a
    DSAR-restriction opened, or ``restore()`` cleared the grace
    anchor), or already deleted.
    """
    now = timezone.now()
    cutoff = now - timedelta(days=GRACE_WINDOW_DAYS)
    # Unexpected cascade failures (FK constraint, signal raising,
    # etc.) propagate to the caller: the atomic block rolls back so
    # the audit row is gone too — caller sees None + can log + retry
    # next run.
    with transaction.atomic():
        try:
            tenant = Tenant.all_objects.select_for_update(skip_locked=True).get(
                pk=tenant_id
            )
        except Tenant.DoesNotExist:
            # Concurrent sweep already finished the delete OR the
            # row was locked by another process (SKIP LOCKED
            # returns no rows for locked-skipped) — either way,
            # this sweep can't make progress on this tenant.
            return None

        # Re-validate eligibility UNDER THE LOCK so we don't
        # hard-delete a tenant whose ``legal_hold`` flipped, or
        # whose ``restore()`` cleared the grace anchor, between
        # the candidate enumeration and the per-tenant lock
        # acquisition.
        if tenant.scheduled_for_deletion_at is None or tenant.legal_hold:
            return None
        # P3-1: the grace re-check applies only when NOT drill-skipping
        # — the drill's named bypass must reach the deletion (the
        # pre-fix unconditional re-check silently skipped every drill
        # candidate as lock_contention_or_state_drift). The legal_hold
        # + DSAR re-checks stay enforced in every mode.
        if not drill_skip_grace and tenant.scheduled_for_deletion_at >= cutoff:
            return None
        if tenant_blocked_by_open_dsar_restriction(tenant_id=str(tenant.id)):
            return None

        tenant_id_str = str(tenant.id)
        slug = tenant.slug
        display_name = tenant.name
        scheduled = tenant.scheduled_for_deletion_at

        # W4.3 (R2-B6/E1-E3) - itemized pre-sweep under tenant_context:
        # provider estate sweepers (delta-share), PROTECT user
        # referrers, the tenant's users, and bare-UUID tenant refs.
        # Runs BEFORE the audit row lands so the counts are truthful
        # and the audit row itself is the only survivor.
        pre_sweep = _pre_sweep_tenant(tenant_id_str)

        create_audit_event(
            resource_type="TENANT",
            action=_audit_et.TENANT_HARD_DELETED,
            actor_user=None,  # cron is system-driven
            tenant=tenant,
            resource_id=tenant_id_str,
            result="SUCCESS",
            details={
                "tenant_id": tenant_id_str,
                "slug": slug,
                "display_name": display_name,
                "scheduled_for_deletion_at": (
                    scheduled.isoformat() if scheduled else None
                ),
                "hard_deleted_at": now.isoformat(),
                "sweep_run_id": sweep_run_id,
                "pre_sweep": pre_sweep,
            },
            infer_tenant_from_actor=False,
        )
        # Cascade fires here — all child rows with on_delete=CASCADE
        # get deleted; AuditEvent rows (tenant on_delete=SET_NULL)
        # survive with tenant_id=NULL.
        tenant.delete()

    return {
        "tenant_id": tenant_id_str,
        "slug": slug,
        "hard_deleted_at": now.isoformat(),
    }


def run_tenant_hard_delete_sweep(
    *,
    dry_run: bool = False,
    sweep_run_id: str | None = None,
    tenant_slug: list[str] | None = None,
    drill_skip_grace: bool = False,
) -> dict[str, Any]:
    """Walk eligible tenants and hard-delete them.

    Eligibility:

    * ``scheduled_for_deletion_at IS NOT NULL`` (i.e. soft-deleted via
      Phase 235.3 endpoint).
    * ``scheduled_for_deletion_at < now() - 90d`` (grace expired) —
      bypassable ONLY in drill mode (``drill_skip_grace=True`` +
      ``tenant_slug`` — the P3-1 drill contract: named, never
      incidental).
    * ``legal_hold = False`` at sweep time (re-check — enforced in
      every mode).
    * No open RESTRICTION-class DSAR at sweep time (re-check —
      enforced in every mode).

    Returns
    -------
    A summary dict::

        {
            "dry_run": bool,
            "hard_deleted_count": int,
            "hard_deleted": [{"tenant_id": ..., "slug": ..., ...}, ...],
            "skipped": [{"tenant_id": ..., "reason": ...}, ...],
            "evaluated_count": int,
        }
    """
    cutoff = timezone.now() - timedelta(days=GRACE_WINDOW_DAYS)
    candidate_filter: dict[str, Any] = {
        "scheduled_for_deletion_at__isnull": False,
    }
    if not drill_skip_grace:
        candidate_filter["scheduled_for_deletion_at__lt"] = cutoff
    if tenant_slug:
        # Drill mode: named tenants only (the grace bypass is never a
        # blanket sweep).
        candidate_filter["slug__in"] = tenant_slug
    candidates = list(
        Tenant.all_objects.filter(**candidate_filter).order_by(
            "scheduled_for_deletion_at"
        )
    )

    hard_deleted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for tenant in candidates:
        # Re-check legal_hold at sweep time.
        if tenant.legal_hold:
            skipped.append(
                {
                    "tenant_id": str(tenant.id),
                    "slug": tenant.slug,
                    "reason": "legal_hold_active",
                }
            )
            logger.info(
                "tenant_hard_delete_sweep_skipped",
                extra={
                    "tenant_id": str(tenant.id),
                    "reason": "legal_hold_active",
                },
            )
            continue

        # Re-check DSAR-restriction at sweep time.
        if tenant_blocked_by_open_dsar_restriction(tenant_id=str(tenant.id)):
            skipped.append(
                {
                    "tenant_id": str(tenant.id),
                    "slug": tenant.slug,
                    "reason": "dsar_restriction_active",
                }
            )
            logger.info(
                "tenant_hard_delete_sweep_skipped",
                extra={
                    "tenant_id": str(tenant.id),
                    "reason": "dsar_restriction_active",
                },
            )
            continue

        if dry_run:
            # Report the would-be deletion without persisting it. The
            # operator can preview the impact before flipping the
            # ``--dry-run`` switch off.
            hard_deleted.append(
                {
                    "tenant_id": str(tenant.id),
                    "slug": tenant.slug,
                    "would_hard_delete_at": timezone.now().isoformat(),
                }
            )
            continue

        try:
            result = _hard_delete_one_tenant(
                tenant_id=tenant.id,
                sweep_run_id=sweep_run_id,
                drill_skip_grace=drill_skip_grace,
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.exception(
                "tenant_hard_delete_sweep_tenant_failed",
                extra={"tenant_id": str(tenant.id), "error": str(exc)},
            )
            skipped.append(
                {
                    "tenant_id": str(tenant.id),
                    "slug": tenant.slug,
                    "reason": "cascade_failed",
                    "error": str(exc),
                }
            )
            continue
        if result is None:
            # Phase 235.3 audit-fix Gap 2 — ``_hard_delete_one_tenant``
            # returns None when the row was lock-skipped (concurrent
            # sweep handling it), or when re-validation under the
            # row lock showed the tenant is no longer eligible
            # (legal_hold flipped, DSAR-restriction opened, restore()
            # cleared the grace anchor). Either way: log + skip with
            # an explicit reason so ops can distinguish lock churn
            # from constraint failures in the summary.
            skipped.append(
                {
                    "tenant_id": str(tenant.id),
                    "slug": tenant.slug,
                    "reason": "lock_contention_or_state_drift",
                }
            )
            continue
        hard_deleted.append(result)

    summary = {
        "dry_run": dry_run,
        "grace_window_days": GRACE_WINDOW_DAYS,
        "evaluated_count": len(candidates),
        "hard_deleted_count": len(hard_deleted),
        "hard_deleted": hard_deleted,
        "skipped": skipped,
    }
    logger.info("tenant_hard_delete_sweep_finished", extra={"summary": summary})
    return summary
