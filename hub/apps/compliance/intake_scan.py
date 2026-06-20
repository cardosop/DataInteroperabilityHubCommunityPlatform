"""
Phase 231.1 — compliance intake auto-scan (idempotent enqueue + activation gate helpers).

Idempotency: ``django.core.cache.cache.add`` — on django-redis this maps to
``SET key value NX EX <ttl>`` (SETNX with TTL). LocMemCache uses the same
``add()`` contract for tests without Redis.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.core.cache import cache
from django.db.models import F, QuerySet

if TYPE_CHECKING:
    from hub.apps.compliance.models import ComplianceRun

logger = logging.getLogger(__name__)

INTAKE_SCAN_IDEMPOTENCY_TTL_SECONDS = 300

#: Stable text appended by ``Asset.can_activate()`` when the tenant gate is on
#: but no qualifying ComplianceRun exists yet.
COMPLIANCE_INTAKE_ACTIVATION_BLOCKER = (
    "Compliance intake gate: a succeeded compliance run with allowed_to_store=true "
    "is required before activation (tenant compliance_intake_gate_enabled)."
)


def _enqueue_lock_cache_key(asset_id: str, tenant_id: str) -> str:
    return f"compliance:intake_scan:enqueue:{tenant_id}:{asset_id}"


def compliance_runs_order_by_activation_latest(
    qs: QuerySet,
) -> QuerySet:
    """
    Order runs for \"latest for activation\" semantics.

    PENDING/RUNNING rows usually have ``completed_at=NULL``; with plain
    ``-completed_at`` those NULLs sort ahead of real timestamps on PostgreSQL,
    incorrectly choosing an in-flight run over a finished one.  Use
    ``nulls_last`` so the latest *completed* run wins; tie-break on
    ``created_at``.
    """
    return qs.order_by(F("completed_at").desc(nulls_last=True), "-created_at")


def latest_compliance_run_for_asset_activation(asset: Any):
    """Same selection as Asset.activate (5.4.3) — single source of truth."""
    return compliance_runs_order_by_activation_latest(
        asset.compliance_runs.all(),
    ).first()


def compliance_intake_gate_satisfied_for_asset(asset: Any) -> bool:
    """
    Intake gate: latest run (per activation ordering) must be terminal success.

    Stricter than 5.4.3 alone: requires ``SUCCEEDED`` plus
    ``allowed_to_store is True`` so activation cannot bypass an in-flight scan.
    """
    from hub.apps.compliance.models import ComplianceRunStatus

    latest = latest_compliance_run_for_asset_activation(asset)
    if latest is None:
        return False
    if latest.status == ComplianceRunStatus.FAILED:
        return False
    if latest.allowed_to_store is not True:
        return False
    if latest.status != ComplianceRunStatus.SUCCEEDED:
        return False
    return True


def enqueue_compliance_intake_scan(asset_id: str, tenant_id: str) -> ComplianceRun | None:
    """
    Create a COMPLIANCE_RUN job for the asset, with 5-minute idempotency per (tenant, asset).

    Returns the new ComplianceRun, or None if skipped (duplicate window) or on failure.
    Never raises — failures are logged (signal path is fail-soft).
    """
    from hub.apps.assets.models import Asset
    from hub.apps.audit import event_types
    from hub.apps.audit.utils import create_audit_event
    from hub.apps.compliance.services import ComplianceService
    from hub.apps.users.models import User

    cache_key = _enqueue_lock_cache_key(asset_id, tenant_id)
    if not cache.add(cache_key, "1", timeout=INTAKE_SCAN_IDEMPOTENCY_TTL_SECONDS):
        logger.info(
            "compliance_intake_scan_skipped_idempotent",
            extra={"asset_id": asset_id, "tenant_id": tenant_id},
        )
        return None

    try:
        asset = Asset.objects.select_related("tenant").get(id=asset_id, tenant_id=tenant_id)
    except Asset.DoesNotExist:
        logger.warning(
            "compliance_intake_scan_asset_missing",
            extra={"asset_id": asset_id, "tenant_id": tenant_id},
        )
        cache.delete(cache_key)
        return None

    if not asset.created_by_id:
        logger.warning(
            "compliance_intake_scan_skipped_no_created_by",
            extra={"asset_id": asset_id, "tenant_id": tenant_id},
        )
        cache.delete(cache_key)
        return None

    tenant = asset.tenant
    if not tenant.compliance_intake_gate_enabled:
        logger.info(
            "compliance_intake_scan_skipped_gate_disabled",
            extra={"asset_id": asset_id, "tenant_id": tenant_id},
        )
        cache.delete(cache_key)
        return None

    try:
        user = User.objects.get(id=asset.created_by_id)
    except User.DoesNotExist:
        logger.warning(
            "compliance_intake_scan_skipped_actor_missing",
            extra={"asset_id": asset_id, "user_id": str(asset.created_by_id)},
        )
        cache.delete(cache_key)
        return None

    service = ComplianceService(
        tenant_id=str(tenant.id),
        user_id=str(user.id),
    )

    # 285.10.3.2.5 — Warehouse-native intake branch
    # Check if the asset's latest dataset is an EXTERNAL_WAREHOUSE
    latest_dataset = asset.datasets.order_by("-version").first()
    if (
        latest_dataset
        and latest_dataset.kind == "EXTERNAL_REF"
        and latest_dataset.snapshot_metadata
        and latest_dataset.snapshot_metadata.get("storage_type") == "EXTERNAL_WAREHOUSE"
    ):
        try:
            run = ComplianceService.scan_inmemory_warehouse(
                dataset=latest_dataset,
                tenant=tenant,
                warehouse_config=latest_dataset.snapshot_metadata,
                regulations=getattr(tenant, "licensed_regulation_keys", None),
                user=user,
            )
        except Exception:
            logger.exception("compliance_warehouse_intake_scan_failed")
            cache.delete(cache_key)
            return None
    else:
        try:
            run = service.create_compliance_run(
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                asset_id=str(asset.id),
                scan_mode="internal",
                tenant=tenant,
                user=user,
                asset=asset,
            )
        except Exception:
            logger.exception(
                "compliance_intake_scan_enqueue_failed",
                extra={"asset_id": asset_id, "tenant_id": tenant_id},
            )
            cache.delete(cache_key)
            return None

    try:
        create_audit_event(
            resource_type="ASSET",
            action=event_types.COMPLIANCE_INTAKE_SCAN_ENQUEUED,
            actor_user=user,
            tenant=tenant,
            resource_id=str(asset.id),
            details={
                "asset_id": str(asset.id),
                "tenant_id": str(tenant.id),
                "compliance_run_id": str(run.id),
                "job_id": str(run.job.id) if run.job else None,
            },
        )
    except Exception:
        logger.exception(
            "compliance_intake_scan_enqueued_audit_failed",
            extra={"asset_id": asset_id, "tenant_id": tenant_id, "run_id": str(run.id)},
        )

    from hub.apps.compliance.metrics_phase231 import (
        EVENT_SCAN_ENQUEUED,
        record_compliance_intake_gate_event,
    )

    record_compliance_intake_gate_event(EVENT_SCAN_ENQUEUED, tenant.id)
    return run


def maybe_emit_compliance_intake_gate_block_audit(
    *,
    asset: Any,
    blockers: list[str],
    actor_user: Any,
    request: Any = None,
) -> None:
    """Emit COMPLIANCE_INTAKE_GATE_BLOCK when activation failed on intake gate."""
    if COMPLIANCE_INTAKE_ACTIVATION_BLOCKER not in blockers:
        return

    from hub.apps.audit import event_types
    from hub.apps.audit.utils import create_audit_event

    try:
        create_audit_event(
            resource_type="ASSET",
            action=event_types.COMPLIANCE_INTAKE_GATE_BLOCK,
            actor_user=actor_user,
            tenant=getattr(asset, "tenant", None),
            resource_id=str(asset.id),
            details={
                "asset_id": str(asset.id),
                "blockers": list(blockers),
            },
            request=request,
        )
    except Exception:
        logger.exception(
            "compliance_intake_gate_block_audit_failed",
            extra={"asset_id": str(asset.id)},
        )
    else:
        from hub.apps.compliance.metrics_phase231 import (
            EVENT_ACTIVATION_GATE_BLOCK,
            record_compliance_intake_gate_event,
        )

        record_compliance_intake_gate_event(
            EVENT_ACTIVATION_GATE_BLOCK,
            getattr(getattr(asset, "tenant", None), "id", None),
        )
