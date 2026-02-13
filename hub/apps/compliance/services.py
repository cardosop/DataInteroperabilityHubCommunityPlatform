"""
Compliance Service

Service layer for compliance run operations.
All create/update/delete paths call ComplianceBusinessRules before mutation.
"""
from typing import Dict, Any, Optional, List
from django.db import transaction

from hub.apps.core.services.base import BaseService, NotFoundError, ValidationError
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.compliance.business_rules import ComplianceBusinessRules


class ComplianceService(BaseService):
    """
    Service for compliance run operations.

    Provides business logic for:
    - Compliance run creation (with business rules validation)
    - Compliance run update and delete (with validation)
    """

    service_name = "compliance_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        self.tenant_id = tenant_id
        self.user_id = user_id

    @transaction.atomic
    def create_compliance_run(
        self,
        tenant_id: str,
        user_id: str,
        asset_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        file_id: Optional[str] = None,
        scan_mode: str = "internal",
        applicable_regulations: Optional[List[str]] = None,
        tenant=None,
        user=None,
        asset=None,
        dataset=None,
        file_obj=None,
    ) -> ComplianceRun:
        """
        Create a compliance run. Validates via ComplianceBusinessRules before mutation.

        Args:
            tenant_id: Tenant UUID
            user_id: User UUID
            asset_id: Optional asset UUID
            dataset_id: Optional dataset UUID
            file_id: Optional file UUID
            scan_mode: Scan mode (internal/external)
            applicable_regulations: Optional list of regulations
            tenant: Optional tenant instance (if already resolved)
            user: Optional user instance (if already resolved)
            asset, dataset, file_obj: Optional resolved resource instances

        Returns:
            Created ComplianceRun instance

        Raises:
            ValidationError: If ComplianceBusinessRules reject
        """
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User
        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File
        from hub.apps.jobs.models import JobType
        from hub.apps.jobs.utils import create_job, get_job_timeout

        try:
            tenant = tenant or Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise NotFoundError("Tenant not found", details={"tenant_id": tenant_id})
        try:
            user = user or User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise NotFoundError("User not found", details={"user_id": user_id})

        if asset is None and asset_id:
            try:
                asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
            except Asset.DoesNotExist:
                raise ValidationError(
                    "Asset not found",
                    code="BUSINESS_RULES_VALIDATION",
                    details={"asset_id": asset_id},
                )
        if dataset is None and dataset_id:
            try:
                dataset = Dataset.objects.get(id=dataset_id, tenant_id=tenant_id)
            except Dataset.DoesNotExist:
                raise ValidationError(
                    "Dataset not found",
                    code="BUSINESS_RULES_VALIDATION",
                    details={"dataset_id": dataset_id},
                )
            if asset and dataset.asset != asset:
                raise ValidationError(
                    "Dataset does not belong to the specified asset",
                    code="BUSINESS_RULES_VALIDATION",
                )
            # Inherit asset from dataset when only dataset_id provided
            if asset is None and dataset.asset_id:
                asset = dataset.asset
        if file_obj is None and file_id:
            try:
                file_obj = File.objects.get(id=file_id, tenant_id=tenant_id)
            except File.DoesNotExist:
                raise ValidationError(
                    "File not found",
                    code="BUSINESS_RULES_VALIDATION",
                    details={"file_id": file_id},
                )

        # Validate via ComplianceBusinessRules before any mutation (unsaved payload)
        payload_run = ComplianceRun(
            tenant_id=tenant_id,
            asset=asset,
            dataset=dataset,
            file=file_obj,
            status=ComplianceRunStatus.PENDING,
        )
        rules = ComplianceBusinessRules(tenant_id=tenant_id, user_id=user_id)
        result = rules.validate(
            compliance_run=payload_run,
            tenant=tenant,
            user=user,
            validation_type="compliance_run",
        )
        if not result.is_valid:
            raise ValidationError(
                "; ".join(result.errors),
                code="BUSINESS_RULES_VALIDATION",
                details=result.details,
            )

        # Create job and run (same as previous view logic)
        import uuid
        temp_resource_id = str(uuid.uuid4())
        job = create_job(
            tenant=tenant,
            user=user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=temp_resource_id,
            details_json={
                "scan_mode": scan_mode,
                "applicable_regulations": applicable_regulations or [],
            },
            timeout_seconds=get_job_timeout(JobType.COMPLIANCE_RUN),
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=tenant,
            asset=asset,
            dataset=dataset,
            file=file_obj,
            job=job,
            status=ComplianceRunStatus.PENDING,
        )
        job.resource_id = str(compliance_run.id)
        job.details_json["compliance_run_id"] = str(compliance_run.id)
        job.save(update_fields=["resource_id", "details_json"])

        try:
            from hub.apps.jobs.tasks import process_job
            from django_rq import get_queue

            queue = get_queue("default")
            queue.enqueue(
                process_job,
                str(job.id),
                job_type=JobType.COMPLIANCE_RUN,
                timeout=get_job_timeout(JobType.COMPLIANCE_RUN),
            )
        except Exception:
            pass  # Log in view/caller if needed; job remains PENDING

        return compliance_run
