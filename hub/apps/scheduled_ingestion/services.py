"""
Ingestion Service

Service layer for scheduled ingestion operations.
Extracts ingestion logic from ingestion.py module.
All create/update paths call ScheduledIngestionBusinessRules before mutation.
"""

import contextlib
import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from hub.apps.core.events.service_publishers import IngestionEventPublisher
from hub.apps.core.services.base import BaseService, ValidationError
from hub.apps.orchestration.workflows.scheduled_ingestion import ScheduledIngestionWorkflow
from hub.apps.scheduled_ingestion.business_rules import ScheduledIngestionBusinessRules
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduledIngestionStatus,
)

logger = logging.getLogger(__name__)


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

    def _find_existing_ingestion_run(
        self,
        scheduled_ingestion: ScheduledIngestion,
        *,
        prefect_flow_run_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> ScheduledIngestionRun | None:
        """The shared idempotency lookup (6.11) — one source of truth for
        the replay contract (mirrors the export side's helper)."""
        if prefect_flow_run_id:
            existing = ScheduledIngestionRun.objects.filter(
                scheduled_ingestion=scheduled_ingestion,
                prefect_flow_run_id=prefect_flow_run_id,
            ).first()
            if existing:
                return existing
        if idempotency_key:
            for r in ScheduledIngestionRun.objects.filter(
                scheduled_ingestion=scheduled_ingestion
            ).order_by("-created_at")[:100]:
                if (r.result_json or {}).get("idempotency_key") == idempotency_key:
                    return r
        return None

    def execute_ingestion_run(
        self,
        scheduled_ingestion_id: str,
        tenant_id: str | None = None,
        user_id: str | None = None,
        prefect_flow_run_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """6.2 (wire-databricks-dlt-movement) — the dlt dispatch spine
        (design D1): create the run, dispatch through the canonical
        ``execute_ingestion`` seam (which routes to the
        ``execute_dlt_ingestion`` entrypoint for flagged tenants), and
        record the outcome on the run's terminal state."""
        effective_tenant_id = tenant_id or self.tenant_id
        scheduled_ingestion = self.get_resource_or_raise(
            ScheduledIngestion, scheduled_ingestion_id, tenant_id=effective_tenant_id
        )

        # 6.11 — the service-level no-double-dispatch contract: a replay
        # returns the existing run WITHOUT re-dispatching (the view layer
        # guards the HTTP surface; this guard covers direct seam callers).
        existing = self._find_existing_ingestion_run(
            scheduled_ingestion,
            prefect_flow_run_id=prefect_flow_run_id,
            idempotency_key=idempotency_key,
        )
        if existing:
            return {
                "run_id": str(existing.id),
                "run_status": existing.status,
                "files_found": existing.files_found or 0,
                "files_processed": existing.files_processed or 0,
                "files_failed": existing.files_failed or 0,
                # W3.8 — the replay returns the RECORDED count (the
                # pre-fix hardcoded 0 even for runs that created real
                # dataset rows).
                "datasets_created": existing.datasets_created or 0,
                "error_message": None,
                "replayed": True,
            }

        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=scheduled_ingestion,
            status=ScheduledIngestionRunStatus.PENDING,
            started_at=timezone.now(),
            prefect_flow_run_id=prefect_flow_run_id or None,
            result_json={"idempotency_key": idempotency_key} if idempotency_key else {},
        )

        # W3.1 (R2-P1) — the lifecycle is explicit: PENDING→RUNNING before
        # the entrypoint executes, then RUNNING→terminal on the outcome.
        # W3.5 (R2-P4) — the RUNNING transition carries the worker's
        # heartbeat (the liveness lease): a crash mid-spine leaves a
        # stale lease the stuck-run detector can recover.
        run.status = ScheduledIngestionRunStatus.RUNNING
        run.heartbeat_at = timezone.now()
        run.save(update_fields=["status", "heartbeat_at", "updated_at"])

        result = self.execute_ingestion(
            str(scheduled_ingestion.id), tenant_id=str(scheduled_ingestion.tenant_id)
        )

        # W3.1 (R2-P1) — the spine honors CANCELLED: a run cancelled while
        # the entrypoint executed keeps its terminal state; the dlt
        # outcome is recorded without overwriting it.
        run.refresh_from_db()
        if run.status == ScheduledIngestionRunStatus.CANCELLED:
            run.result_json = {**(run.result_json or {}), "dlt_outcome": result}
            run.save(update_fields=["result_json", "updated_at"])
            return {**result, "run_id": str(run.id), "run_status": run.status}

        failed = bool(result.get("files_failed")) or bool(result.get("error_message"))
        new_status = (
            ScheduledIngestionRunStatus.FAILED if failed else ScheduledIngestionRunStatus.COMPLETED
        )

        run.status = new_status
        run.files_found = result.get("files_found") or 0
        run.files_processed = result.get("files_processed") or 0
        run.files_failed = result.get("files_failed") or 0
        # W3.2 (R2-P5) — the spine records the same run-row fields as the
        # RQ worker task: datasets_created (one per ingested file) and the
        # canonical error_message (the parent propagation reads it).
        run.datasets_created = result.get("datasets_created") or 0
        run.error_message = result.get("error_message")
        run.completed_at = timezone.now()
        run.result_json = {**(run.result_json or {}), "dlt_outcome": result}
        run.save(
            update_fields=[
                "status",
                "files_found",
                "files_processed",
                "files_failed",
                "datasets_created",
                "error_message",
                "completed_at",
                "result_json",
                "updated_at",
            ]
        )

        # W3.2 (R2-P5) — uniform completion: the spine routes completion
        # through the canonical side-effect contract exactly once (the
        # same contract as the RQ worker task and the internal PATCH).
        # A side-effect failure must never roll back the run's terminal
        # state — the outbox retries them (Phase 76).
        try:
            from .worker_run_lifecycle import apply_run_completion_side_effects

            apply_run_completion_side_effects(run, new_status)
        except Exception as e:
            logger.error(
                "dlt_ingestion_side_effects_failed",
                run_id=str(run.id),
                error=str(e),
                exc_info=True,
            )

        return {**result, "run_id": str(run.id), "run_status": run.status}

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

        create_kw = {
            "tenant": tenant,
            "created_by": created_by,
            "name": name,
            "description": description or "",
            "source_type": source_type,
            "source_config": source_config,
            "schedule_type": schedule_type,
            "schedule_config": schedule_config,
            "file_pattern": file_pattern or ".*",
            "asset": asset,
            "contract": contract,
            "auto_create_asset": auto_create_asset,
            "auto_activate": auto_activate,
            "status": ScheduledIngestionStatus.ACTIVE,
        }
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
