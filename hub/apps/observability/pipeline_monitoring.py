"""
Pipeline Monitoring Service

Tracks pipeline execution times, success rates, error rates, latency, and throughput.
"""

from typing import Any

from django.db.models import Avg, Count, Q
from django.utils import timezone

from hub.apps.jobs.models import Job, JobType
from hub.apps.scheduled_ingestion.models import ScheduledIngestionRun

from .models import PipelineExecution


class PipelineMonitor:
    """
    Pipeline monitoring service for tracking execution metrics.
    """

    @staticmethod
    def record_execution(
        tenant_id: str,
        pipeline_type: str,
        pipeline_id: str,
        pipeline_name: str | None = None,
        status: str = "PENDING",
        started_at: timezone.datetime | None = None,
        completed_at: timezone.datetime | None = None,
        execution_time_seconds: float | None = None,
        latency_ms: float | None = None,
        throughput_items_per_second: float | None = None,
        items_processed: int = 0,
        items_failed: int = 0,
        error_message: str | None = None,
        error_code: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        result_json: dict[str, Any] | None = None,
    ) -> PipelineExecution:
        """
        Record a pipeline execution.

        Args:
            tenant_id: Tenant UUID
            pipeline_type: Type of pipeline (SCHEDULED_INGESTION, DQ_RUN, etc.)
            pipeline_id: Pipeline UUID
            pipeline_name: Optional pipeline name
            status: Execution status
            started_at: When execution started
            completed_at: When execution completed
            execution_time_seconds: Execution time in seconds
            latency_ms: Latency in milliseconds
            throughput_items_per_second: Throughput (items/second)
            items_processed: Number of items processed
            items_failed: Number of items that failed
            error_message: Error message if failed
            error_code: Error code for categorization
            resource_type: Resource type (DATASET, ASSET, etc.)
            resource_id: Resource UUID
            result_json: Result data

        Returns:
            PipelineExecution instance
        """
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.get(id=tenant_id)

        execution = PipelineExecution.objects.create(
            tenant=tenant,
            pipeline_type=pipeline_type,
            pipeline_id=pipeline_id,
            pipeline_name=pipeline_name,
            status=status,
            started_at=started_at or timezone.now(),
            completed_at=completed_at,
            execution_time_seconds=execution_time_seconds,
            latency_ms=latency_ms,
            throughput_items_per_second=throughput_items_per_second,
            items_processed=items_processed,
            items_failed=items_failed,
            error_message=error_message,
            error_code=error_code,
            resource_type=resource_type,
            resource_id=resource_id,
            result_json=result_json or {},
        )

        return execution

    @staticmethod
    def update_execution(
        execution_id: str,
        status: str | None = None,
        completed_at: timezone.datetime | None = None,
        execution_time_seconds: float | None = None,
        latency_ms: float | None = None,
        throughput_items_per_second: float | None = None,
        items_processed: int | None = None,
        items_failed: int | None = None,
        error_message: str | None = None,
        error_code: str | None = None,
        result_json: dict[str, Any] | None = None,
    ) -> PipelineExecution:
        """
        Update a pipeline execution.

        Args:
            execution_id: Execution UUID
            status: New status
            completed_at: Completion time
            execution_time_seconds: Execution time
            latency_ms: Latency
            throughput_items_per_second: Throughput
            items_processed: Items processed
            items_failed: Items failed
            error_message: Error message
            error_code: Error code
            result_json: Result data

        Returns:
            Updated PipelineExecution instance
        """
        execution = PipelineExecution.objects.get(id=execution_id)

        update_fields = ["updated_at"]

        if status is not None:
            execution.status = status
            update_fields.append("status")

        if completed_at is not None:
            execution.completed_at = completed_at
            update_fields.append("completed_at")

            # Calculate execution time if started_at exists
            if execution.started_at:
                execution.execution_time_seconds = (
                    completed_at - execution.started_at
                ).total_seconds()
                update_fields.append("execution_time_seconds")

        if execution_time_seconds is not None:
            execution.execution_time_seconds = execution_time_seconds
            update_fields.append("execution_time_seconds")

        if latency_ms is not None:
            execution.latency_ms = latency_ms
            update_fields.append("latency_ms")

        if throughput_items_per_second is not None:
            execution.throughput_items_per_second = throughput_items_per_second
            update_fields.append("throughput_items_per_second")

        if items_processed is not None:
            execution.items_processed = items_processed
            update_fields.append("items_processed")

        if items_failed is not None:
            execution.items_failed = items_failed
            update_fields.append("items_failed")

        if error_message is not None:
            execution.error_message = error_message
            update_fields.append("error_message")

        if error_code is not None:
            execution.error_code = error_code
            update_fields.append("error_code")

        if result_json is not None:
            execution.result_json = result_json
            update_fields.append("result_json")

        execution.save(update_fields=update_fields)

        return execution

    @staticmethod
    def get_pipeline_dashboard(
        tenant_id: str,
        pipeline_type: str | None = None,
        pipeline_id: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Get pipeline monitoring dashboard data.

        Args:
            tenant_id: Tenant UUID
            pipeline_type: Optional pipeline type filter
            pipeline_id: Optional pipeline ID filter
            limit: Maximum number of executions to return

        Returns:
            Dashboard data dictionary
        """
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.get(id=tenant_id)

        # Build query
        query = Q(tenant=tenant)

        if pipeline_type:
            query &= Q(pipeline_type=pipeline_type)

        if pipeline_id:
            query &= Q(pipeline_id=pipeline_id)

        # Get recent executions
        executions = PipelineExecution.objects.filter(query).order_by("-created_at")[:limit]

        # Calculate statistics
        stats_query = PipelineExecution.objects.filter(query)

        total_executions = stats_query.count()
        completed_executions = stats_query.filter(status="COMPLETED").count()
        failed_executions = stats_query.filter(status="FAILED").count()
        running_executions = stats_query.filter(status="RUNNING").count()

        # Calculate success rate
        terminal_executions = completed_executions + failed_executions
        success_rate = (
            (completed_executions / terminal_executions * 100) if terminal_executions > 0 else 0.0
        )

        # Calculate error rate
        error_rate = (
            (failed_executions / terminal_executions * 100) if terminal_executions > 0 else 0.0
        )

        # Calculate average execution time
        avg_execution_time = (
            stats_query.filter(status="COMPLETED", execution_time_seconds__isnull=False).aggregate(
                avg=Avg("execution_time_seconds")
            )["avg"]
            or 0.0
        )

        # Calculate average latency
        avg_latency = (
            stats_query.filter(status="COMPLETED", latency_ms__isnull=False).aggregate(
                avg=Avg("latency_ms")
            )["avg"]
            or 0.0
        )

        # Calculate average throughput
        avg_throughput = (
            stats_query.filter(
                status="COMPLETED", throughput_items_per_second__isnull=False
            ).aggregate(avg=Avg("throughput_items_per_second"))["avg"]
            or 0.0
        )

        # Get error codes distribution
        error_codes = (
            stats_query.filter(status="FAILED", error_code__isnull=False)
            .values("error_code")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Get pipeline type distribution
        pipeline_types = (
            stats_query.values("pipeline_type")
            .annotate(
                count=Count("id"),
                success_count=Count("id", filter=Q(status="COMPLETED")),
                failed_count=Count("id", filter=Q(status="FAILED")),
            )
            .order_by("-count")
        )

        return {
            "results": [
                {
                    "id": str(e.id),
                    "pipeline_type": e.pipeline_type,
                    "pipeline_id": str(e.pipeline_id),
                    "pipeline_name": e.pipeline_name,
                    "status": e.status,
                    "started_at": e.started_at.isoformat() if e.started_at else None,
                    "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                    "execution_time_seconds": e.execution_time_seconds,
                    "latency_ms": e.latency_ms,
                    "throughput_items_per_second": e.throughput_items_per_second,
                    "items_processed": e.items_processed,
                    "items_failed": e.items_failed,
                    "error_message": e.error_message,
                    "error_code": e.error_code,
                    "resource_type": e.resource_type,
                    "resource_id": str(e.resource_id) if e.resource_id else None,
                    "created_at": e.created_at.isoformat(),
                }
                for e in executions
            ],
            "summary": {
                "total_executions": total_executions,
                "completed_executions": completed_executions,
                "failed_executions": failed_executions,
                "running_executions": running_executions,
                "success_rate_percent": round(success_rate, 2),
                "error_rate_percent": round(error_rate, 2),
                "avg_execution_time_seconds": round(avg_execution_time, 2),
                "avg_latency_ms": round(avg_latency, 2),
                "avg_throughput_items_per_second": round(avg_throughput, 2),
                "error_codes": list(error_codes),
                "pipeline_types": list(pipeline_types),
            },
        }

    @staticmethod
    def sync_from_jobs(tenant_id: str, limit: int = 1000) -> int:
        """
        Sync pipeline executions from Job records.

        Args:
            tenant_id: Tenant UUID
            limit: Maximum number of jobs to process

        Returns:
            Number of executions created/updated
        """
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.get(id=tenant_id)

        # Get recent jobs that haven't been synced
        jobs = Job.objects.filter(
            tenant=tenant,
            type__in=[
                JobType.DQ_RUN,
                JobType.COMPLIANCE_RUN,
                JobType.CONTRACT_VALIDATION,
                JobType.SEMANTIC_MAPPING,
                JobType.SCHEDULED_INGESTION,
            ],
        ).order_by("-created_at")[:limit]

        count = 0

        for job in jobs:
            # Map job type to pipeline type
            pipeline_type_map = {
                JobType.DQ_RUN: "DQ_RUN",
                JobType.COMPLIANCE_RUN: "COMPLIANCE_RUN",
                JobType.CONTRACT_VALIDATION: "CONTRACT_VALIDATION",
                JobType.SEMANTIC_MAPPING: "SEMANTIC_MAPPING",
                JobType.SCHEDULED_INGESTION: "SCHEDULED_INGESTION",
            }

            pipeline_type = pipeline_type_map.get(job.type)
            if not pipeline_type:
                continue

            # Check if execution already exists
            execution, created = PipelineExecution.objects.get_or_create(
                tenant=tenant,
                pipeline_type=pipeline_type,
                pipeline_id=str(job.id),
                defaults={
                    "status": job.status,
                    "started_at": job.started_at,
                    "completed_at": job.completed_at,
                    "execution_time_seconds": (
                        (job.completed_at - job.started_at).total_seconds()
                        if job.started_at and job.completed_at
                        else None
                    ),
                    "error_message": job.error_message,
                    "resource_type": job.resource_type,
                    "resource_id": str(job.resource_id),
                    "result_json": job.result_json or {},
                },
            )

            if not created:
                # Update existing execution
                execution.status = job.status
                execution.started_at = job.started_at
                execution.completed_at = job.completed_at
                if job.started_at and job.completed_at:
                    execution.execution_time_seconds = (
                        job.completed_at - job.started_at
                    ).total_seconds()
                execution.error_message = job.error_message
                execution.result_json = job.result_json or {}
                execution.save()

            count += 1

        return count

    @staticmethod
    def sync_from_scheduled_ingestion_runs(tenant_id: str, limit: int = 1000) -> int:
        """
        Sync pipeline executions from ScheduledIngestionRun records.

        Args:
            tenant_id: Tenant UUID
            limit: Maximum number of runs to process

        Returns:
            Number of executions created/updated
        """
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.get(id=tenant_id)

        # Get recent runs
        runs = ScheduledIngestionRun.objects.filter(scheduled_ingestion__tenant=tenant).order_by(
            "-created_at"
        )[:limit]

        count = 0

        for run in runs:
            # Check if execution already exists
            execution, created = PipelineExecution.objects.get_or_create(
                tenant=tenant,
                pipeline_type="SCHEDULED_INGESTION",
                pipeline_id=str(run.scheduled_ingestion.id),
                defaults={
                    "pipeline_name": run.scheduled_ingestion.name,
                    "status": run.status,
                    "started_at": run.started_at,
                    "completed_at": run.completed_at,
                    "execution_time_seconds": (
                        (run.completed_at - run.started_at).total_seconds()
                        if run.started_at and run.completed_at
                        else None
                    ),
                    "items_processed": run.files_processed,
                    "items_failed": run.files_failed,
                    "error_message": run.error_message,
                    "resource_type": "ASSET" if run.scheduled_ingestion.asset else None,
                    "resource_id": str(run.scheduled_ingestion.asset.id)
                    if run.scheduled_ingestion.asset
                    else None,
                    "result_json": run.result_json or {},
                },
            )

            if not created:
                # Update existing execution
                execution.status = run.status
                execution.started_at = run.started_at
                execution.completed_at = run.completed_at
                if run.started_at and run.completed_at:
                    execution.execution_time_seconds = (
                        run.completed_at - run.started_at
                    ).total_seconds()
                execution.items_processed = run.files_processed
                execution.items_failed = run.files_failed
                execution.error_message = run.error_message
                execution.result_json = run.result_json or {}
                execution.save()

            count += 1

        return count
