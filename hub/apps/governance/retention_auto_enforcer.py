"""
Phase 232.7 — automated retention sweep: tombstone, 90-calendar-day grace, then hard-delete.

Separate from legacy ``RetentionPolicyEnforcer``, which honours per-policy grace windows
and omission of tombstone scheduling columns.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any, Optional

from django.db import transaction
from django.utils import timezone

import structlog

from hub.apps.audit.utils import create_audit_event
from hub.apps.audit import event_types as _audit_et

from hub.apps.governance.dsar_retention_block import resource_blocked_by_open_dsar_restriction
from hub.apps.governance.models import RetentionPolicy, RetentionPolicyType
from hub.apps.governance.retention import RetentionPolicyEnforcer


logger = structlog.get_logger(__name__)

_HARD_DELETE_AFTER_TOMBSTONE_DAYS = 90


def _legal_hold_active(policy: RetentionPolicy, now: datetime) -> bool:
    if not policy.legal_hold:
        return False
    if policy.legal_hold_expires_at is None:
        return True
    return policy.legal_hold_expires_at > now


def quarterly_period_bounds(year: int, quarter: int) -> tuple[datetime, datetime]:
    if quarter not in (1, 2, 3, 4):
        raise ValueError("quarter must be 1..4")
    start_month = {1: 1, 2: 4, 3: 7, 4: 10}[quarter]
    start = datetime(year, start_month, 1, tzinfo=dt_timezone.utc)
    if quarter == 4:
        end = datetime(year + 1, 1, 1, tzinfo=dt_timezone.utc)
    else:
        end_month = start_month + 3
        end = datetime(year, end_month, 1, tzinfo=dt_timezone.utc)
    # inclusive catalogue uses [start, end) for timestamp __gte/__lt filtering
    return start, end


@dataclass(frozen=True)
class RetentionQuarterlyTenantReport:
    year: int
    quarter: int
    tombstone_events_in_quarter: int
    hard_delete_events_in_quarter: int


def quarterly_retention_compliance_snapshot(
    *, tenant_id: str, year: int, quarter: int
) -> dict[str, Any]:
    """Counts audit rows for tombstone/hard-delete actions within a UTC calendar quarter."""
    from hub.apps.audit.models import AuditEvent

    start, end = quarterly_period_bounds(year, quarter)

    tomb = AuditEvent.objects.filter(
        tenant_id=tenant_id,
        action=_audit_et.RETENTION_RESOURCE_TOMBSTONED,
        timestamp__gte=start,
        timestamp__lt=end,
    ).count()

    hd = AuditEvent.objects.filter(
        tenant_id=tenant_id,
        action=_audit_et.RETENTION_RESOURCE_HARD_DELETED_AUTOSWEEP,
        timestamp__gte=start,
        timestamp__lt=end,
    ).count()

    return RetentionQuarterlyTenantReport(
        year=year,
        quarter=quarter,
        tombstone_events_in_quarter=tomb,
        hard_delete_events_in_quarter=hd,
    ).__dict__


def retention_enforcement_dashboard(*, tenant_id: str) -> dict[str, Any]:
    """Operational snapshot derived from mutable policy rows (cheap list endpoint).

    Phase 234.5 — also reports the per-event-type audit retention
    override counts under the ``audit_event_retention_overrides`` key.
    The 232.7 governance dashboard is the single surface ops uses to
    see "what does retention look like in this tenant"; bolting the
    audit-retention summary on here avoids forcing the SPA to call two
    endpoints (and keeps the regulation-key-driven retention story
    visible in one place for both data resources AND audit events).
    """
    now = timezone.now()
    qs = RetentionPolicy.objects.filter(tenant_id=tenant_id, enabled=True)
    overdue_tombstone = 0
    pending_hard_delete = 0
    active_legal_holds = 0
    for p in qs:
        if _legal_hold_active(p, now):
            active_legal_holds += 1
        resource = p.asset or p.dataset or p.file
        if p.policy_type != RetentionPolicyType.TIME_BASED.value:
            continue
        if not resource or p.retention_period_days is None:
            continue
        exp = resource.created_at + timedelta(days=p.retention_period_days)
        if p.tombstoned_at is None and now >= exp:
            overdue_tombstone += 1
        if (
            p.tombstoned_at is not None
            and p.hard_delete_scheduled_at is not None
            and now >= p.hard_delete_scheduled_at
        ):
            pending_hard_delete += 1

    # Phase 234.5 — audit retention override summary. Imported locally
    # so this module doesn't pull the audit app at import time (avoids
    # circular-import risk during app-config loading).
    from hub.apps.audit.models import AuditEventRetentionPolicy

    audit_qs = AuditEventRetentionPolicy.objects.filter(tenant_id=tenant_id)
    audit_total = audit_qs.count()
    audit_enabled = audit_qs.filter(enabled=True).count()
    audit_regulation_driven = audit_qs.filter(enabled=True).exclude(
        regulation_keys=[]
    ).count()

    return {
        "tenant_id": tenant_id,
        "generated_at": now.isoformat(),
        "enabled_policies": qs.count(),
        "awaiting_initial_tombstone": overdue_tombstone,
        "awaiting_hard_delete_after_grace": pending_hard_delete,
        "policies_under_legal_hold": active_legal_holds,
        "autosweep_hard_delete_grace_days": _HARD_DELETE_AFTER_TOMBSTONE_DAYS,
        "audit_event_retention_overrides": {
            "total": audit_total,
            "enabled": audit_enabled,
            "regulation_driven_enabled": audit_regulation_driven,
        },
    }


class RetentionAutoEnforcerSweep:
    """Cross-tenant batch driver (cron + Job handler)."""

    @staticmethod
    @transaction.atomic
    def enforce_policy_row(
        policy: RetentionPolicy, *, dry_run: bool, now: Optional[datetime] = None
    ) -> dict[str, Any]:
        now = now or timezone.now()
        out: dict[str, Any] = {
            "policy_id": str(policy.id),
            "phase": None,
            "skipped": False,
            "detail": "",
        }

        if policy.policy_type != RetentionPolicyType.TIME_BASED.value:
            out["skipped"] = True
            out["detail"] = "non_time_based_policy"
            return out

        resource = policy.asset or policy.dataset or policy.file
        if not resource:
            out["skipped"] = True
            out["detail"] = "missing_resource"
            return out

        asset_id = str(policy.asset_id) if policy.asset_id else None
        dataset_id = str(policy.dataset_id) if policy.dataset_id else None
        file_id = str(policy.file_id) if policy.file_id else None

        if _legal_hold_active(policy, now):
            out["skipped"] = True
            out["detail"] = "legal_hold_active"
            return out

        if resource_blocked_by_open_dsar_restriction(
            tenant_id=str(policy.tenant_id),
            asset_id=asset_id,
            dataset_id=dataset_id,
            file_id=file_id,
        ):
            out["skipped"] = True
            out["detail"] = "open_dsar_restriction"
            return out

        if policy.retention_period_days is None:
            out["skipped"] = True
            out["detail"] = "no_retention_period"
            return out

        expiry = resource.created_at + timedelta(days=policy.retention_period_days)

        # Phase B — honour scheduled hard-delete after tombstone grace
        if policy.tombstoned_at and policy.hard_delete_scheduled_at and now >= policy.hard_delete_scheduled_at:
            out["phase"] = "hard_delete"
            if dry_run:
                out["skipped"] = True
                out["detail"] = "dry_run_hard_delete_preview"
                return out

            create_audit_event(
                resource_type="RETENTION_POLICY",
                action=_audit_et.RETENTION_RESOURCE_HARD_DELETED_AUTOSWEEP,
                actor_user=policy.created_by,
                tenant=policy.tenant,
                resource_id=policy.pk,
                details={
                    "asset_id": asset_id,
                    "dataset_id": dataset_id,
                    "file_id": file_id,
                },
            )

            RetentionPolicyEnforcer._hard_delete_resource(resource)
            logger.info(
                "retention_autosweep_hard_deleted",
                policy_id=str(policy.id),
                tenant_id=str(policy.tenant_id),
            )
            out["detail"] = "hard_deleted_resource"
            return out

        # Phase A — first breach of retention window ⇒ tombstone + schedule hard-delete
        if now < expiry:
            out["skipped"] = True
            out["detail"] = "inside_retention_window"
            return out

        if policy.tombstoned_at is None:
            out["phase"] = "tombstone"
            if dry_run:
                out["skipped"] = True
                out["detail"] = "dry_run_tombstone_preview"
                return out

            RetentionPolicyEnforcer._soft_delete_resource(resource)
            grace_deadline = now + timedelta(days=_HARD_DELETE_AFTER_TOMBSTONE_DAYS)

            RetentionPolicy.objects.filter(pk=policy.pk).update(
                tombstoned_at=now,
                hard_delete_scheduled_at=grace_deadline,
                last_enforced_at=now,
                updated_at=now,
            )

            create_audit_event(
                resource_type="RETENTION_POLICY",
                action=_audit_et.RETENTION_RESOURCE_TOMBSTONED,
                actor_user=policy.created_by,
                tenant=policy.tenant,
                resource_id=policy.pk,
                details={
                    "asset_id": asset_id,
                    "dataset_id": dataset_id,
                    "file_id": file_id,
                    "hard_delete_scheduled_at": grace_deadline.isoformat(),
                },
            )
            logger.info(
                "retention_autosweep_tombstone",
                policy_id=str(policy.id),
                tenant_id=str(policy.tenant_id),
            )
            out["detail"] = "resource_tombstoned"
            return out

        # Already tombstoned; waiting grace window handled above
        if policy.hard_delete_scheduled_at is None:
            # Defensive reconciliation: retroactively anchor grace anchor if timestamps drifted.
            tomb_anchor = policy.tombstoned_at
            if tomb_anchor is None:
                out["skipped"] = True
                out["detail"] = "missing_tombstone_anchor"
                return out
            anchored = tomb_anchor + timedelta(days=_HARD_DELETE_AFTER_TOMBSTONE_DAYS)
            if not dry_run:
                RetentionPolicy.objects.filter(pk=policy.pk).update(
                    hard_delete_scheduled_at=anchored, updated_at=now
                )
            out["skipped"] = True
            out["detail"] = "repair_scheduled_at"
            return out

        out["skipped"] = True
        out["detail"] = "awaiting_hard_delete_window"
        return out

    @staticmethod
    def run_for_all_tenants(*, dry_run: bool = False) -> dict[str, Any]:
        """Iterate tenants flagged ``compliance_retention_enforcer_enabled``."""

        from hub.apps.tenants.models import Tenant
        from hub.apps.tenants.request_tenant import tenant_context

        summary: dict[str, Any] = {
            "tenants_seen": 0,
            "policies_considered": 0,
            "tombstones": 0,
            "hard_deletes": 0,
            "skipped": 0,
            "dry_run": dry_run,
        }

        tenants = Tenant.objects.filter(compliance_retention_enforcer_enabled=True).order_by("id")
        now = timezone.now()

        for tenant in tenants.iterator():
            summary["tenants_seen"] += 1
            tenant_id_str = str(tenant.id)

            with tenant_context(tenant_id_str):
                qs = RetentionPolicy.objects.select_related(
                    "tenant",
                    "asset",
                    "dataset",
                    "file",
                    "created_by",
                ).filter(
                    tenant_id=tenant.pk,
                    enabled=True,
                    policy_type=RetentionPolicyType.TIME_BASED.value,
                )

                for policy in qs:
                    summary["policies_considered"] += 1
                    snap = RetentionAutoEnforcerSweep.enforce_policy_row(policy, dry_run=dry_run, now=now)
                    detail = snap.get("detail") or ""
                    if detail == "resource_tombstoned":
                        summary["tombstones"] += 1
                    elif detail == "hard_deleted_resource":
                        summary["hard_deletes"] += 1
                    else:
                        summary["skipped"] += 1

        create_audit_event(
            resource_type="JOB",
            action=_audit_et.RETENTION_AUTOSWEEP_COMPLETED,
            actor_user=None,
            tenant=None,
            resource_id=None,
            details=summary,
        )

        logger.info("retention_autosweep_finished", summary=summary)
        return summary


def run_retention_enforcement_sweep(*, dry_run: bool = False) -> dict[str, Any]:
    """Entry point for CronJob management command + RQ handlers."""
    return RetentionAutoEnforcerSweep.run_for_all_tenants(dry_run=dry_run)
