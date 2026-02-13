"""
DQ Service

Service layer for DQ run operations.
All create/update/delete paths call DQBusinessRules before mutation.
"""
from typing import Dict, Any, Optional, List
from django.db import transaction

from hub.apps.core.services.base import BaseService, NotFoundError, ValidationError
from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine
from hub.apps.dq.business_rules import DQBusinessRules


class DQService(BaseService):
    """
    Service for DQ run operations.

    Provides business logic for:
    - DQ run creation (with business rules validation)
    - DQ run update and delete (with validation)
    """

    service_name = "dq_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        self.tenant_id = tenant_id
        self.user_id = user_id

    @transaction.atomic
    def create_dq_run(
        self,
        tenant_id: str,
        user_id: str,
        asset_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        file_id: Optional[str] = None,
        profile_key: Optional[str] = None,
        tenant=None,
        user=None,
        asset=None,
        dataset=None,
        file_obj=None,
    ) -> DQRun:
        """
        Create a DQ run. Validates via DQBusinessRules before mutation.

        Args:
            tenant_id: Tenant UUID
            user_id: User UUID
            asset_id: Optional asset UUID
            dataset_id: Optional dataset UUID
            file_id: Optional file UUID
            profile_key: Optional profile key (default from tenant config)
            tenant: Optional tenant instance (if already resolved)
            user: Optional user instance (if already resolved)
            asset, dataset, file_obj: Optional resolved resource instances

        Returns:
            Created DQRun instance

        Raises:
            ValidationError: If DQBusinessRules reject
        """
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User
        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File
        from hub.apps.jobs.models import JobType
        from hub.apps.jobs.utils import create_job, get_job_timeout
        from hub.apps.tenants.services import get_tenant_dq_profile

        tenant = tenant or Tenant.objects.get(id=tenant_id)
        user = user or User.objects.get(id=user_id)

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
        if file_obj is None and file_id:
            try:
                file_obj = File.objects.get(id=file_id, tenant_id=tenant_id)
            except File.DoesNotExist:
                raise ValidationError(
                    "File not found",
                    code="BUSINESS_RULES_VALIDATION",
                    details={"file_id": file_id},
                )

        profile_key = profile_key or get_tenant_dq_profile(tenant_id)
        if profile_key.endswith("_gx") or "gx" in profile_key.lower():
            engine = DQEngine.GREAT_EXPECTATIONS
        elif profile_key.endswith("_soda") or "soda" in profile_key.lower():
            engine = DQEngine.SODA
        else:
            engine = DQEngine.GREAT_EXPECTATIONS

        # Validate via DQBusinessRules before any mutation (unsaved payload)
        payload_run = DQRun(
            tenant_id=tenant_id,
            asset=asset,
            dataset=dataset,
            file=file_obj,
            profile_key=profile_key,
            engine=engine,
            status=DQRunStatus.PENDING,
        )
        rules = DQBusinessRules(tenant_id=tenant_id, user_id=user_id)
        result = rules.validate(
            dq_run=payload_run,
            tenant=tenant,
            user=user,
            validation_type="dq_run",
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
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=temp_resource_id,
            details_json={},
            timeout_seconds=get_job_timeout(JobType.DQ_RUN),
        )
        dq_run = DQRun.objects.create(
            tenant=tenant,
            asset=asset,
            dataset=dataset,
            file=file_obj,
            job=job,
            profile_key=profile_key,
            engine=engine,
            status=DQRunStatus.PENDING,
        )
        job.resource_id = str(dq_run.id)
        job.details_json["dq_run_id"] = str(dq_run.id)
        job.save(update_fields=["resource_id", "details_json"])

        try:
            from hub.apps.jobs.tasks import process_job
            from django_rq import get_queue

            queue = get_queue("default")
            queue.enqueue(
                process_job,
                str(job.id),
                job_type=JobType.DQ_RUN,
                timeout=get_job_timeout(JobType.DQ_RUN),
            )
        except Exception:
            pass

        return dq_run
