"""
Phase 234.1 audit-fix — Job handler for ``JobType.AUDIT_MERKLE_SNAPSHOT``.

Mirrors the pattern in ``hub/apps/jobs/tasks_governance.py``: a tiny
adapter that runs inside the generic ``execute_job_by_type`` dispatcher
(``hub/apps/jobs/tasks_base.py``) and delegates to the pure work
function in :mod:`hub.apps.audit.merkle`.

The work function (``snapshot_all_tenants_now``) is also called
directly by the ``audit_merkle_snapshot_sweep`` Django management
command — same code path, two activation surfaces:

* Kubernetes CronJob (hourly) → management command → work function.
* Operator-triggered job (e.g. after a known-bad period) → ``Job``
  row of type ``AUDIT_MERKLE_SNAPSHOT`` → dispatcher → this adapter →
  work function.

Both paths converge on a single implementation so the proof-of-tamper
trail is identical regardless of who scheduled it.
"""
from __future__ import annotations
import structlog

from .models import AuditMerkleSnapshot

logger = structlog.get_logger(__name__)


def _execute_audit_merkle_snapshot_job(job_obj) -> dict:
    """Handler for ``JobType.AUDIT_MERKLE_SNAPSHOT``.

    ``job_obj.details_json`` may carry:

    * ``window_hours`` (int, default 1) — width of each tenant's window.

    Returns a result dict suitable for the job's ``result_json``: total
    snapshots produced + a per-tenant breakdown for ops dashboards.
    """
    from hub.apps.audit.merkle import snapshot_all_tenants_now

    details = job_obj.details_json or {}
    window_hours = int(details.get("window_hours", 1) or 1)

    logger.info(
        "audit_merkle_snapshot_job_starting",
        job_id=str(job_obj.id),
        window_hours=window_hours,
    )

    try:
        rows = snapshot_all_tenants_now(window_hours=window_hours)
    except Exception:
        logger.exception(
            "audit_merkle_snapshot_job_failed", job_id=str(job_obj.id)
        )
        raise

    per_tenant: dict[str, dict] = {}
    for row in rows:
        key = str(row.tenant_id) if row.tenant_id else "__platform__"
        per_tenant[key] = {
            "snapshot_id": str(row.id),
            "root_hex": row.root_hex,
            "event_count": row.event_count,
            "first_chain_sequence": row.first_chain_sequence,
            "last_chain_sequence": row.last_chain_sequence,
            "s3_bucket": row.s3_bucket,
            "s3_key": row.s3_key,
            "s3_version_id": row.s3_version_id,
        }

    result = {
        "success": True,
        "summary": {
            "snapshots_produced": len(rows),
            "tenants_covered": len(per_tenant),
            "window_hours": window_hours,
        },
        "per_tenant": per_tenant,
    }
    logger.info(
        "audit_merkle_snapshot_job_completed",
        job_id=str(job_obj.id),
        snapshots_produced=len(rows),
    )
    return result


def _execute_audit_permanent_delete_sweep_job(job_obj) -> dict:
    """Phase 234.4 handler for ``JobType.AUDIT_PERMANENT_DELETE_SWEEP``.

    ``job_obj.details_json`` may carry:

    * ``dry_run`` (bool, default False) — preview without deletion.
    * ``tenant_id`` (str | None) — restrict to one tenant; ``"__platform__"``
      for the no-tenant chain. Omit to sweep every tenant.
    * ``age_threshold_days`` (int, default 90) — grace window.

    Returns a result dict suitable for the job's ``result_json``: the
    full summary from :func:`run_audit_permanent_delete_sweep`.
    """
    from hub.apps.audit.retention_purge import (
        DEFAULT_AGE_THRESHOLD_DAYS,
        run_audit_permanent_delete_sweep,
    )

    details = job_obj.details_json or {}
    dry_run = bool(details.get("dry_run", False))
    tenant_id = details.get("tenant_id")
    age_threshold_days = int(
        details.get("age_threshold_days", DEFAULT_AGE_THRESHOLD_DAYS)
        or DEFAULT_AGE_THRESHOLD_DAYS
    )

    logger.info(
        "audit_permanent_delete_sweep_job_starting",
        job_id=str(job_obj.id),
        dry_run=dry_run,
        tenant_id=tenant_id,
        age_threshold_days=age_threshold_days,
    )

    try:
        summary = run_audit_permanent_delete_sweep(
            dry_run=dry_run,
            tenant_id=tenant_id,
            age_threshold_days=age_threshold_days,
        )
    except Exception:
        logger.exception(
            "audit_permanent_delete_sweep_job_failed",
            job_id=str(job_obj.id),
        )
        raise

    logger.info(
        "audit_permanent_delete_sweep_job_completed",
        job_id=str(job_obj.id),
        deleted_count=summary.get("deleted_count"),
        tenants_swept=summary.get("tenants_swept"),
    )
    return {"success": True, "summary": summary}
