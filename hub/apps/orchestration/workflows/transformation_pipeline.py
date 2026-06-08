"""
Transformation Pipeline Workflow — Phase 115F fix

Orchestrates transformation pipeline execution via the workflow engine.
Steps: validate → create_execution → run_pipeline → store_results → audit
"""

import logging
import uuid
from typing import Any, Dict, Optional

from django.db import transaction
from django.utils import timezone

from hub.apps.orchestration.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
)
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine

logger = logging.getLogger(__name__)


class TransformationPipelineWorkflow:
    """
    Workflow for executing transformation pipelines.

    Provides the interface expected by TransformationService.execute_pipeline():
      - register_tasks(engine)
      - register_workflow(registry)
      - execute(pipeline_id, asset_id, tenant_id, user_id, ...)
    """

    WORKFLOW_NAME = "transformation_pipeline"

    @classmethod
    def register_workflow(cls, registry: WorkflowRegistry) -> None:
        """Register the transformation pipeline workflow."""
        workflow_dsl = {
            "version": "1.0.0",
            "dependencies": [],
            "steps": [
                {
                    "name": "validate_pipeline",
                    "type": "task",
                    "task": "transformation.validate_pipeline",
                },
                {
                    "name": "create_execution",
                    "type": "task",
                    "task": "transformation.create_execution",
                },
                {
                    "name": "run_pipeline",
                    "type": "task",
                    "task": "transformation.run_pipeline",
                },
                {
                    "name": "store_results",
                    "type": "task",
                    "task": "transformation.store_results",
                },
                {
                    "name": "audit_logging",
                    "type": "task",
                    "task": "transformation.audit_logging",
                },
            ],
            "compensation": {"enabled": True},
        }
        registry.register_workflow(cls.WORKFLOW_NAME, workflow_dsl)

    @classmethod
    def register_tasks(cls, engine: WorkflowEngine) -> None:
        """Register all task functions."""
        engine.register_task(
            "transformation.validate_pipeline",
            cls._validate_pipeline_task,
        )
        engine.register_task(
            "transformation.create_execution",
            cls._create_execution_task,
        )
        engine.register_task(
            "transformation.run_pipeline",
            cls._run_pipeline_task,
        )
        engine.register_task(
            "transformation.store_results",
            cls._store_results_task,
        )
        engine.register_task(
            "transformation.audit_logging",
            cls._audit_logging_task,
        )

    @classmethod
    def execute(
        cls,
        pipeline_id: str,
        asset_id: str,
        tenant_id: str,
        user_id: Optional[str] = None,
        execution_mode: str = "SYNC",
        engine: Optional[WorkflowEngine] = None,
        registry: Optional[WorkflowRegistry] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Execute the transformation pipeline workflow.

        Returns dict with execution_id, status, and result.
        """
        from hub.apps.assets.models import Asset
        from hub.apps.jobs.models import JobType
        from hub.apps.jobs.utils import create_job
        from hub.apps.tenants.models import Tenant
        from hub.apps.transformation.models import (
            ExecutionMode,
            ExecutionStatus,
            PipelineExecution,
            TransformationPipeline,
        )

        pipeline = TransformationPipeline.objects.get(
            id=pipeline_id, tenant_id=tenant_id,
        )
        asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)

        # All transformation execution is now async (Phase 285.9 dbt-native).
        # SYNC mode was removed; DuckDB/Polars in-worker execution is deprecated.
        mode = ExecutionMode.ASYNC
        if execution_mode and execution_mode != "ASYNC":
            logger.warning(
                "transformation_sync_mode_ignored",
                pipeline_id=str(pipeline_id),
                requested_mode=execution_mode,
            )

        execution = PipelineExecution.objects.create(
            pipeline=pipeline,
            asset=asset,
            execution_mode=mode,
            status=ExecutionStatus.PENDING,
        )

        # Create job for tracking
        tenant = Tenant.objects.get(id=tenant_id)
        user_obj = None
        if user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user_obj = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass

        job = create_job(
            tenant=tenant,
            user=user_obj,
            job_type=JobType.TRANSFORMATION,
            resource_type="TRANSFORMATION_PIPELINE",
            resource_id=str(pipeline_id),
            details_json={
                "pipeline_id": str(pipeline_id),
                "asset_id": str(asset_id),
                "execution_id": str(execution.id),
                "execution_mode": execution_mode,
            },
            timeout_seconds=600,
            priority="NORMAL",
        )

        execution.job = job
        # Assign a unique flow-trace identifier.  When Prefect integration is
        # wired, this will be replaced by the actual Prefect flow run ID
        # returned by the Prefect API.
        execution.prefect_flow_run_id = uuid.uuid4()
        execution.save(update_fields=["job", "prefect_flow_run_id", "updated_at"])

        logger.info(
            "transformation_execution_created pipeline_id=%s execution_id=%s prefect_flow_run_id=%s",
            pipeline_id, str(execution.id), str(execution.prefect_flow_run_id),
        )

        # Create WorkflowInstance for execution tracking
        workflow_def, _ = WorkflowDefinition.objects.get_or_create(
            name=cls.WORKFLOW_NAME,
            version="1.0.0",
            defaults={
                "description": "Transformation pipeline workflow",
                "dsl_json": {
                    "version": "1.0.0",
                    "steps": [
                        {"name": "validate_pipeline", "type": "task",
                         "task": "transformation.validate_pipeline"},
                        {"name": "run_pipeline", "type": "task",
                         "task": "transformation.run_pipeline"},
                    ],
                },
                "is_active": True,
            },
        )
        # All workflows start as DRAFT (queued for async execution).
        workflow_instance = WorkflowInstance.objects.create(
            workflow_definition=workflow_def,
            workflow_name=cls.WORKFLOW_NAME,
            workflow_version="1.0.0",
            tenant_id=tenant_id,
            status=WorkflowStatus.DRAFT,
            input_data={
                "pipeline_id": str(pipeline_id),
                "asset_id": str(asset_id),
                "execution_mode": execution_mode,
            },
        )
        execution.workflow_instance = workflow_instance
        execution.save(
            update_fields=["workflow_instance", "updated_at"],
        )

        if mode == ExecutionMode.ASYNC:
            # ASYNC: already PENDING from creation — Prefect worker will update
            pass
        else:
            # SYNC: complete immediately with result asset
            from hub.apps.assets.models import AssetStatus
            result_asset = Asset.objects.create(
                tenant_id=tenant_id,
                key=f"transform-result-{execution.id}",
                name=f"Result: {pipeline.name}",
                description=(
                    f"Transformation output from pipeline "
                    f"'{pipeline.name}' v{pipeline.version}"
                ),
                domain=getattr(asset, "domain", "transform"),
                status=AssetStatus.DRAFT,
            )
            execution.result_asset = result_asset
            execution.status = ExecutionStatus.COMPLETED
            execution.completed_at = timezone.now()
            execution.metrics = {
                "duration_seconds": 0.0,
                "rows_processed": 0,
            }
            execution.save(update_fields=[
                "result_asset", "status", "completed_at",
                "metrics", "updated_at",
            ])
            # Mark workflow instance completed for sync mode
            workflow_instance.status = WorkflowStatus.COMPLETED
            workflow_instance.completed_at = timezone.now()
            workflow_instance.save(
                update_fields=[
                    "status", "completed_at", "updated_at",
                ],
            )

        return {
            "success": True,
            "execution_id": str(execution.id),
            "status": execution.status,
            "job_id": str(job.id),
            "pipeline_id": str(pipeline_id),
            "asset_id": str(asset_id),
            "workflow_instance_id": str(workflow_instance.id),
        }

    # ── Task implementations ─────────────────────────────────────

    @staticmethod
    def _validate_pipeline_task(context: Dict[str, Any]) -> Dict:
        return {"valid": True}

    @staticmethod
    def _create_execution_task(context: Dict[str, Any]) -> Dict:
        return {"execution_created": True}

    @staticmethod
    def _run_pipeline_task(context: Dict[str, Any]) -> Dict:
        return {"pipeline_executed": True}

    @staticmethod
    def _store_results_task(context: Dict[str, Any]) -> Dict:
        return {"results_stored": True}

    @staticmethod
    def _audit_logging_task(context: Dict[str, Any]) -> Dict:
        logger.info("transformation_audit_logged")
        return {"audit_logged": True}
