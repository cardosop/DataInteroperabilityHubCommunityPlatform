"""
ODPS Job Queue Utilities

Utilities for enqueueing ODPS operations as background jobs.
Task 8.4.2: Integrate with Job Queue
"""

from typing import Any

import structlog

from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User

logger = structlog.get_logger(__name__)


def enqueue_odps_normalization_job(
    contract_id: str,
    tenant_id: str,
    user_id: str | None = None,
    details_json: dict[str, Any] | None = None,
) -> str:
    """
    Enqueue ODPS normalization job.

    Args:
        contract_id: Contract UUID
        tenant_id: Tenant UUID
        user_id: User UUID (optional)
        details_json: Additional job details (optional)

    Returns:
        Job ID (UUID string)

    Raises:
        ValidationError: If tenant job limits are exceeded
    """
    try:
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id) if user_id else None

        job_details = details_json or {}
        job_details["contract_id"] = contract_id

        job = create_job(
            tenant=tenant,
            user=user,
            job_type=JobType.ODPS_NORMALIZATION.value,
            resource_type="CONTRACT",
            resource_id=contract_id,
            details_json=job_details,
        )

        logger.info(
            "odps_normalization_job_enqueued",
            job_id=str(job.id),
            contract_id=contract_id,
            tenant_id=tenant_id,
            message="ODPS normalization job enqueued successfully",
        )

        return str(job.id)
    except Exception as e:
        logger.error(
            "odps_normalization_job_enqueue_failed",
            contract_id=contract_id,
            tenant_id=tenant_id,
            error=str(e),
            exc_info=True,
        )
        raise


def enqueue_odps_ref_resolution_job(
    contract_id: str,
    tenant_id: str,
    user_id: str | None = None,
    details_json: dict[str, Any] | None = None,
) -> str:
    """
    Enqueue ODPS $ref resolution job.

    Args:
        contract_id: Contract UUID
        tenant_id: Tenant UUID
        user_id: User UUID (optional)
        details_json: Additional job details (optional)

    Returns:
        Job ID (UUID string)

    Raises:
        ValidationError: If tenant job limits are exceeded
    """
    try:
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id) if user_id else None

        job_details = details_json or {}
        job_details["contract_id"] = contract_id

        job = create_job(
            tenant=tenant,
            user=user,
            job_type=JobType.ODPS_REF_RESOLUTION.value,
            resource_type="CONTRACT",
            resource_id=contract_id,
            details_json=job_details,
        )

        logger.info(
            "odps_ref_resolution_job_enqueued",
            job_id=str(job.id),
            contract_id=contract_id,
            tenant_id=tenant_id,
            message="ODPS $ref resolution job enqueued successfully",
        )

        return str(job.id)
    except Exception as e:
        logger.error(
            "odps_ref_resolution_job_enqueue_failed",
            contract_id=contract_id,
            tenant_id=tenant_id,
            error=str(e),
            exc_info=True,
        )
        raise


def enqueue_odps_export_job(
    contract_id: str,
    tenant_id: str,
    user_id: str | None = None,
    export_format: str = "json",
    odps_version: str | None = None,
    details_json: dict[str, Any] | None = None,
) -> str:
    """
    Enqueue ODPS export job.

    Args:
        contract_id: Contract UUID
        tenant_id: Tenant UUID
        user_id: User UUID (optional)
        export_format: Export format ("json" or "yaml", default: "json")
        odps_version: Target ODPS version (optional, default: "4.1")
        details_json: Additional job details (optional)

    Returns:
        Job ID (UUID string)

    Raises:
        ValidationError: If tenant job limits are exceeded
    """
    try:
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id) if user_id else None

        job_details = details_json or {}
        job_details["contract_id"] = contract_id
        job_details["export_format"] = export_format.lower()
        if odps_version:
            job_details["odps_version"] = odps_version

        job = create_job(
            tenant=tenant,
            user=user,
            job_type=JobType.ODPS_EXPORT.value,
            resource_type="CONTRACT",
            resource_id=contract_id,
            details_json=job_details,
        )

        logger.info(
            "odps_export_job_enqueued",
            job_id=str(job.id),
            contract_id=contract_id,
            tenant_id=tenant_id,
            export_format=export_format,
            odps_version=odps_version,
            message="ODPS export job enqueued successfully",
        )

        return str(job.id)
    except Exception as e:
        logger.error(
            "odps_export_job_enqueue_failed",
            contract_id=contract_id,
            tenant_id=tenant_id,
            error=str(e),
            exc_info=True,
        )
        raise


def enqueue_odps_semantic_mapping_job(
    contract_id: str,
    tenant_id: str,
    user_id: str | None = None,
    details_json: dict[str, Any] | None = None,
) -> str:
    """
    Enqueue ODPS semantic mapping job.

    Args:
        contract_id: Contract UUID
        tenant_id: Tenant UUID
        user_id: User UUID (optional)
        details_json: Additional job details (optional)

    Returns:
        Job ID (UUID string)

    Raises:
        ValidationError: If tenant job limits are exceeded
    """
    try:
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id) if user_id else None

        job_details = details_json or {}
        job_details["contract_id"] = contract_id

        job = create_job(
            tenant=tenant,
            user=user,
            job_type=JobType.ODPS_SEMANTIC_MAPPING.value,
            resource_type="CONTRACT",
            resource_id=contract_id,
            details_json=job_details,
        )

        logger.info(
            "odps_semantic_mapping_job_enqueued",
            job_id=str(job.id),
            contract_id=contract_id,
            tenant_id=tenant_id,
            message="ODPS semantic mapping job enqueued successfully",
        )

        return str(job.id)
    except Exception as e:
        logger.error(
            "odps_semantic_mapping_job_enqueue_failed",
            contract_id=contract_id,
            tenant_id=tenant_id,
            error=str(e),
            exc_info=True,
        )
        raise


def enqueue_odps_linking_job(
    odps_contract_id: str,
    odcs_contract_id: str,
    tenant_id: str,
    user_id: str | None = None,
    details_json: dict[str, Any] | None = None,
) -> str:
    """
    Enqueue ODPS linking job.

    Args:
        odps_contract_id: ODPS contract UUID
        odcs_contract_id: ODCS contract UUID
        tenant_id: Tenant UUID
        user_id: User UUID (optional)
        details_json: Additional job details (optional)

    Returns:
        Job ID (UUID string)

    Raises:
        ValidationError: If tenant job limits are exceeded
    """
    try:
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id) if user_id else None

        job_details = details_json or {}
        job_details["odps_contract_id"] = odps_contract_id
        job_details["odcs_contract_id"] = odcs_contract_id

        job = create_job(
            tenant=tenant,
            user=user,
            job_type=JobType.ODPS_LINKING.value,
            resource_type="CONTRACT",
            resource_id=odps_contract_id,
            details_json=job_details,
        )

        logger.info(
            "odps_linking_job_enqueued",
            job_id=str(job.id),
            odps_contract_id=odps_contract_id,
            odcs_contract_id=odcs_contract_id,
            tenant_id=tenant_id,
            message="ODPS linking job enqueued successfully",
        )

        return str(job.id)
    except Exception as e:
        logger.error(
            "odps_linking_job_enqueue_failed",
            odps_contract_id=odps_contract_id,
            odcs_contract_id=odcs_contract_id,
            tenant_id=tenant_id,
            error=str(e),
            exc_info=True,
        )
        raise
