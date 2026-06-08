"""
Phase 235.3 — Job handler for ``JobType.TENANT_HARD_DELETE_SWEEP``.

Tiny adapter that runs inside the generic ``execute_job_by_type``
dispatcher (``hub/apps/jobs/tasks_base.py``) and delegates to the pure
work function in :mod:`hub.apps.tenants.tenant_hard_delete_sweep`.

The work function is also called directly by the
``tenant_hard_delete_sweep`` Django management command — same code
path, two activation surfaces:

* Kubernetes CronJob (daily) → management command → work function.
* Operator-triggered job (post-incident re-run) → ``Job`` row of
  type ``TENANT_HARD_DELETE_SWEEP`` → dispatcher → this adapter →
  work function.
"""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _execute_tenant_hard_delete_sweep_job(job_obj) -> dict[str, Any]:
    """Handler for ``JobType.TENANT_HARD_DELETE_SWEEP``.

    ``job_obj.details_json`` may carry:

    * ``dry_run`` (bool, default False) — preview without deletion.

    Returns a result dict suitable for the job's ``result_json``: the
    full summary from :func:`run_tenant_hard_delete_sweep`.
    """
    from hub.apps.tenants.tenant_hard_delete_sweep import (
        run_tenant_hard_delete_sweep,
    )

    details = job_obj.details_json or {}
    dry_run = bool(details.get("dry_run", False))
    sweep_run_id = str(job_obj.id)

    logger.info(
        "tenant_hard_delete_sweep_job_starting",
        extra={"job_id": sweep_run_id, "dry_run": dry_run},
    )

    try:
        summary = run_tenant_hard_delete_sweep(
            dry_run=dry_run, sweep_run_id=sweep_run_id
        )
    except Exception:
        logger.exception(
            "tenant_hard_delete_sweep_job_failed",
            extra={"job_id": sweep_run_id},
        )
        raise

    logger.info(
        "tenant_hard_delete_sweep_job_completed",
        extra={
            "job_id": sweep_run_id,
            "hard_deleted_count": summary.get("hard_deleted_count"),
            "skipped_count": len(summary.get("skipped") or []),
        },
    )
    return {"success": True, "summary": summary}


def _execute_impersonation_expire_sweep_job(job_obj) -> dict[str, Any]:
    """Phase 235.4 — handler for ``JobType.IMPERSONATION_EXPIRE_SWEEP``.

    Adapter on the same shape as
    :func:`_execute_tenant_hard_delete_sweep_job` — runs the pure
    sweep function and bubbles up the summary as ``result_json``.
    """
    from hub.apps.tenants.expire_impersonation_sweep import (
        run_expire_impersonation_sessions,
    )

    sweep_run_id = str(job_obj.id)
    logger.info(
        "impersonation_expire_sweep_job_starting",
        extra={"job_id": sweep_run_id},
    )
    try:
        summary = run_expire_impersonation_sessions(sweep_run_id=sweep_run_id)
    except Exception:
        logger.exception(
            "impersonation_expire_sweep_job_failed",
            extra={"job_id": sweep_run_id},
        )
        raise

    logger.info(
        "impersonation_expire_sweep_job_completed",
        extra={
            "job_id": sweep_run_id,
            "expired_count": summary.get("expired_count"),
            "skipped_count": len(summary.get("skipped") or []),
        },
    )
    return {"success": True, "summary": summary}
