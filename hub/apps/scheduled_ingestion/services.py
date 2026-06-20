"""
Ingestion Service

Service layer for scheduled ingestion operations.
Extracts ingestion logic from ingestion.py module.
All create/update paths call ScheduledIngestionBusinessRules before mutation.
"""

import contextlib
from typing import Any

from django.db import transaction

from hub.apps.core.events.service_publishers import IngestionEventPublisher
from hub.apps.core.services.base import BaseService, ValidationError
from hub.apps.orchestration.workflows.scheduled_ingestion import ScheduledIngestionWorkflow
from hub.apps.scheduled_ingestion.business_rules import ScheduledIngestionBusinessRules
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionStatus,
)


class IngestionService(BaseService, IngestionEventPublisher):
    """
    Service for scheduled ingestion operations.

    Provides business logic for:
    - Scheduled ingestion execution
    - Ingestion status monitoring
    - Ingestion configuration management
    """

    service_name = "ingestion_service"

    def __init__(self, tenant_id: str | None = None, user_id: str | None = None):
        """
        Initialize IngestionService.

        Args:
            tenant_id: Optional tenant ID
            user_id: Optional user ID
        """
        super().__init__(tenant_id=tenant_id, user_id=user_id)

    def execute_ingestion(
        self, scheduled_ingestion_id: str, tenant_id: str | None = None
    ) -> dict[str, Any]:
        """
        Execute a scheduled ingestion using workflow orchestration.

        Args:
            scheduled_ingestion_id: Scheduled ingestion ID
            tenant_id: Optional tenant ID for filtering

        Returns:
            Execution result dictionary

        Raises:
            NotFoundError: If scheduled ingestion not found
        """
        scheduled_ingestion = self.get_resource_or_raise(
            ScheduledIngestion, scheduled_ingestion_id, tenant_id=tenant_id or self.tenant_id
        )

        return self.execute_with_metrics(
            operation="execute_ingestion",
            func=lambda: self._execute_ingestion_impl(scheduled_ingestion),
            tenant_id=str(scheduled_ingestion.tenant_id),
        )

    def _execute_ingestion_impl(self, scheduled_ingestion: ScheduledIngestion) -> dict[str, Any]:
        """Internal implementation of ingestion execution."""
        # Phase 285.6 — when the dlt engine feature flag is enabled, use
        # the unified DataMovementPipeline instead of the legacy connector path.
        if getattr(scheduled_ingestion.tenant, "data_movement_enabled", False):
            from hub.data_movement.ingestion_execution import execute_dlt_ingestion

            return execute_dlt_ingestion(str(scheduled_ingestion.id))

        # Execute workflow (legacy connector path)
        workflow_result = ScheduledIngestionWorkflow.execute(
            scheduled_ingestion_id=str(scheduled_ingestion.id)
        )

        # Extract results from workflow output
        output_data = workflow_result.get("output_data", {})
        state_summary = output_data.get("state_summary", {})

        return {
            "files_found": output_data.get("files_found", 0),
            "files_processed": state_summary.get("total_processed", 0),
            "files_failed": state_summary.get("total_failed", 0),
            "datasets_created": state_summary.get("total_processed", 0),
            "ingestion_state": {
                "processed_files": state_summary.get("total_processed", 0),
                "failed_files": state_summary.get("total_failed", 0),
                "permanent_failures": state_summary.get("permanent_failures", 0),
                "retryable_failures": state_summary.get("retryable_failures", 0),
                "last_processed_at": state_summary.get("last_processed_timestamp"),
            },
            "workflow_instance_id": workflow_result.get("workflow_instance_id"),
        }

    @transaction.atomic
    def create_scheduled_ingestion(
        self,
        tenant,
        created_by,
        name: str,
        source_type: str,
        source_config: dict[str, Any],
        schedule_type: str = "DAILY",
        schedule_config: dict[str, Any] | None = None,
        file_pattern: str = "",
        description: str | None = None,
        asset=None,
        contract=None,
        auto_create_asset: bool = False,
        auto_activate: bool = False,
        **kwargs,
    ) -> ScheduledIngestion:
        """
        Create a scheduled ingestion. Validates via ScheduledIngestionBusinessRules before mutation.

        Returns:
            Created ScheduledIngestion instance.

        Raises:
            ValidationError: If ScheduledIngestionBusinessRules reject.
        """
        schedule_config = schedule_config or {}
        payload = ScheduledIngestion(
            tenant=tenant,
            created_by=created_by,
            name=name,
            description=description or "",
            source_type=source_type,
            source_config=source_config,
            schedule_type=schedule_type,
            schedule_config=schedule_config,
            file_pattern=file_pattern or ".*",
            asset=asset,
            contract=contract,
            auto_create_asset=auto_create_asset,
            auto_activate=auto_activate,
            status=ScheduledIngestionStatus.ACTIVE,
        )
        rules = ScheduledIngestionBusinessRules(
            tenant_id=str(tenant.id),
            user_id=str(created_by.id) if created_by else None,
        )
        result = rules.validate(
            schedule=payload,
            tenant=tenant,
            user=created_by,
            validation_type="schedule",
        )
        if not result.is_valid:
            raise ValidationError(
                "; ".join(result.errors),
                code="BUSINESS_RULES_VALIDATION",
                details=result.details,
            )

        # Check plan limit (Phase 25.1.2, hardened Phase 113.B)
        from hub.apps.tenants.services import PlanLimitService

        plan_limit_service = PlanLimitService(
            tenant_id=str(tenant.id),
            user_id=str(created_by.id) if created_by else None,
        )
        plan_limit_service.check_limit(
            tenant_id=str(tenant.id),
            limit_key="max_scheduled_ingestions",
            delta=1,
        )

        create_kw = dict(
            tenant=tenant,
            created_by=created_by,
            name=name,
            description=description or "",
            source_type=source_type,
            source_config=source_config,
            schedule_type=schedule_type,
            schedule_config=schedule_config,
            file_pattern=file_pattern or ".*",
            asset=asset,
            contract=contract,
            auto_create_asset=auto_create_asset,
            auto_activate=auto_activate,
            status=ScheduledIngestionStatus.ACTIVE,
        )
        for k in ["prefect_work_pool_name"]:
            if k in kwargs and kwargs[k] is not None:
                create_kw[k] = kwargs[k]
        scheduled_ingestion = ScheduledIngestion.objects.create(**create_kw)
        return scheduled_ingestion

    @transaction.atomic
    def update_scheduled_ingestion(
        self,
        scheduled_ingestion_id: str,
        tenant_id: str,
        user_id: str,
        **update_data,
    ) -> ScheduledIngestion:
        """
        Update a scheduled ingestion. Validates via ScheduledIngestionBusinessRules before mutation.

        Args:
            scheduled_ingestion_id: Scheduled ingestion ID
            tenant_id: Tenant ID
            user_id: User ID performing the update
            **update_data: Fields to update

        Returns:
            Updated ScheduledIngestion instance

        Raises:
            NotFoundError: If scheduled ingestion not found
            ValidationError: If ScheduledIngestionBusinessRules reject
        """
        scheduled_ingestion = self.get_resource_or_raise(
            ScheduledIngestion,
            scheduled_ingestion_id,
            tenant_id=tenant_id,
        )

        # Create a temporary instance with updated data for validation
        updated_payload = ScheduledIngestion(
            tenant=scheduled_ingestion.tenant,
            created_by=scheduled_ingestion.created_by,
            name=update_data.get("name", scheduled_ingestion.name),
            description=update_data.get("description", scheduled_ingestion.description),
            source_type=update_data.get("source_type", scheduled_ingestion.source_type),
            source_config=update_data.get("source_config", scheduled_ingestion.source_config),
            schedule_type=update_data.get("schedule_type", scheduled_ingestion.schedule_type),
            schedule_config=update_data.get("schedule_config", scheduled_ingestion.schedule_config),
            file_pattern=update_data.get("file_pattern", scheduled_ingestion.file_pattern),
            asset=update_data.get("asset", scheduled_ingestion.asset),
            contract=update_data.get("contract", scheduled_ingestion.contract),
            auto_create_asset=update_data.get(
                "auto_create_asset", scheduled_ingestion.auto_create_asset
            ),
            auto_activate=update_data.get("auto_activate", scheduled_ingestion.auto_activate),
            status=update_data.get("status", scheduled_ingestion.status),
        )

        # Validate via business rules
        rules = ScheduledIngestionBusinessRules(
            tenant_id=tenant_id,
            user_id=user_id,
        )
        result = rules.validate(
            schedule=updated_payload,
            tenant=scheduled_ingestion.tenant,
            user=scheduled_ingestion.created_by,
            validation_type="schedule",
        )
        if not result.is_valid:
            raise ValidationError(
                "; ".join(result.errors),
                code="BUSINESS_RULES_VALIDATION",
                details=result.details,
            )

        # Update fields
        for field, value in update_data.items():
            if hasattr(scheduled_ingestion, field):
                setattr(scheduled_ingestion, field, value)

        scheduled_ingestion.save()

        # Create audit event (API expects actor_user and tenant instances)
        from django.contrib.auth import get_user_model

        from hub.apps.audit.utils import create_audit_event
        from hub.apps.tenants.models import Tenant

        User = get_user_model()
        actor_user = User.objects.filter(id=user_id).first()
        tenant = Tenant.objects.filter(id=tenant_id).first()
        create_audit_event(
            resource_type="SCHEDULED_INGESTION",
            action="SCHEDULED_INGESTION_UPDATED",
            actor_user=actor_user,
            tenant=tenant,
            resource_id=str(scheduled_ingestion.id),
            details=update_data,
        )

        return scheduled_ingestion

    def get_ingestion_status(
        self, scheduled_ingestion_id: str, tenant_id: str | None = None
    ) -> ScheduledIngestion:
        """
        Get scheduled ingestion status.

        Args:
            scheduled_ingestion_id: Scheduled ingestion ID
            tenant_id: Optional tenant ID for filtering

        Returns:
            ScheduledIngestion instance

        Raises:
            NotFoundError: If scheduled ingestion not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        return self.execute_with_metrics(
            operation="get_ingestion_status",
            tenant_id=effective_tenant_id,
            func=lambda: self.get_resource_or_raise(
                ScheduledIngestion, scheduled_ingestion_id, tenant_id=effective_tenant_id
            ),
        )

    @transaction.atomic
    def delete_scheduled_ingestion(
        self,
        scheduled_ingestion_id: str,
        tenant_id: str,
        user_id: str,
    ) -> None:
        """
        Delete a scheduled ingestion with audit.

        Args:
            scheduled_ingestion_id: Scheduled ingestion ID
            tenant_id: Tenant ID
            user_id: User ID performing the deletion

        Raises:
            NotFoundError: If scheduled ingestion not found
        """
        scheduled_ingestion = self.get_resource_or_raise(
            ScheduledIngestion,
            scheduled_ingestion_id,
            tenant_id=tenant_id,
        )

        # Create audit event before deletion
        from django.contrib.auth import get_user_model

        from hub.apps.audit.utils import create_audit_event
        from hub.apps.tenants.models import Tenant

        User = get_user_model()
        actor_user = None
        if user_id:
            with contextlib.suppress(User.DoesNotExist):
                actor_user = User.objects.get(id=user_id)

        tenant = scheduled_ingestion.tenant
        if not tenant:
            with contextlib.suppress(Tenant.DoesNotExist):
                tenant = Tenant.objects.get(id=tenant_id)

        create_audit_event(
            resource_type="SCHEDULED_INGESTION",
            action="DELETED",
            actor_user=actor_user,
            tenant=tenant,
            resource_id=str(scheduled_ingestion.id),
            details={"name": scheduled_ingestion.name},
        )

        # Delete scheduled ingestion
        scheduled_ingestion.delete()
