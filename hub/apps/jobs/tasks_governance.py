"""
Governance Job Handlers

Handlers for Governance job execution (retention policy enforcement).

SAVING CHECKPOINT: This module contains Governance job handlers (< 700 lines per project rule).
"""

import structlog

from .models import Job

logger = structlog.get_logger(__name__)


def _execute_retention_policy_enforcement_job(job_obj: Job) -> dict:
    """
    Execute RETENTION_POLICY_ENFORCEMENT job.

    Enforces retention policies for assets, datasets, and files.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with enforcement summary

    Raises:
        ValueError: For validation errors
        Exception: For other errors
    """
    from hub.apps.governance.retention import RetentionPolicyEnforcer

    tenant_id = job_obj.tenant_id

    logger.info(
        "Starting retention policy enforcement", job_id=str(job_obj.id), tenant_id=str(tenant_id)
    )

    try:
        # Enforce all policies
        results = RetentionPolicyEnforcer.enforce_all_policies(
            tenant_id=str(tenant_id) if tenant_id else None
        )

        logger.info(
            "Retention policy enforcement completed",
            job_id=str(job_obj.id),
            total_policies=results["total_policies"],
            enforced=results["enforced"],
            failed=results["failed"],
        )

        return {
            "success": True,
            "summary": {
                "total_policies": results["total_policies"],
                "enforced": results["enforced"],
                "failed": results["failed"],
                "no_action": results["no_action"],
            },
            "details": results["details"],
        }

    except Exception as e:
        logger.error(
            "Retention policy enforcement job failed",
            exc_info=True,
            job_id=str(job_obj.id),
            error=str(e),
        )
        raise


def _execute_retention_enforcement_sweep_job(job_obj: Job) -> dict:
    """
    Execute RETENTION_ENFORCEMENT_SWEEP job.

    Phase 232 — sweeps retention policies for expired resources and
    schedules hard-deletion.  Uses ``RetentionAutoEnforcerSweep``
    which is distinct from the policy enforcement job: it processes
    per-policy expiration logic with a dry-run flag.

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with sweep summary including dry_run flag
        and tenants_seen count.
    """
    from hub.apps.governance.retention_auto_enforcer import (
        run_retention_enforcement_sweep,
    )

    dry_run = bool((job_obj.details_json or {}).get("dry_run", False))

    try:
        results = run_retention_enforcement_sweep(dry_run=dry_run)
        return {
            "success": True,
            "summary": results,
            "details": {},
        }
    except Exception as e:
        logger.error(
            "Retention enforcement sweep job failed",
            exc_info=True,
            job_id=str(job_obj.id),
            error=str(e),
        )
        raise
