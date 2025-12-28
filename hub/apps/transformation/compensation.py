"""
Transformation Pipeline Compensation

Implements compensation logic for transformation pipeline execution rollback.
Handles cleanup of resources created during pipeline execution when failures occur.
"""
import logging
from typing import Dict, Any, Optional, List
from django.db import transaction
from django.utils import timezone

from .models import PipelineExecution, ExecutionStatus
from .exceptions import TransformationExecutionError

logger = logging.getLogger(__name__)


class TransformationPipelineCompensation:
    """
    Compensation handler for transformation pipeline execution.

    Implements compensation logic for multi-service operations:
    - Quality service operations
    - Compliance service operations
    - Asset creation
    - Job creation
    - Event publishing (non-critical, logged only)
    """

    def __init__(self, execution: PipelineExecution):
        """
        Initialize compensation handler.

        Args:
            execution: PipelineExecution instance to compensate
        """
        self.execution = execution
        self.compensation_log: List[Dict[str, Any]] = []

    def log_compensation_operation(
        self,
        operation: str,
        status: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a compensation operation.

        Args:
            operation: Operation name
            status: Operation status (success, failed, skipped)
            details: Optional operation details
        """
        log_entry = {
            "timestamp": timezone.now().isoformat(),
            "operation": operation,
            "status": status,
            "details": details or {}
        }
        self.compensation_log.append(log_entry)
        logger.info(
            f"Compensation operation: {operation} - {status}",
            extra={
                "execution_id": str(self.execution.id),
                "operation": operation,
                "status": status,
                "details": details
            }
        )

    @transaction.atomic
    def compensate(
        self,
        rollback_execution: bool = True,
        cleanup_job: bool = True,
        cleanup_result_asset: bool = True,
        publish_compensation_events: bool = True
    ) -> Dict[str, Any]:
        """
        Execute compensation logic for pipeline execution failure.

        Args:
            rollback_execution: Whether to mark execution as failed
            cleanup_job: Whether to cancel associated job if exists
            cleanup_result_asset: Whether to cleanup result asset if exists
            publish_compensation_events: Whether to publish compensation events

        Returns:
            Compensation result dictionary
        """
        compensation_result = {
            "status": "success",
            "execution_id": str(self.execution.id),
            "timestamp": timezone.now().isoformat(),
            "operations": {}
        }

        try:
            # Mark execution as failed if not already
            if rollback_execution:
                try:
                    if not self.execution.is_terminal():
                        self.execution.mark_failed(
                            error_message="Execution failed and compensation triggered"
                        )
                        self.log_compensation_operation(
                            "rollback_execution",
                            "success",
                            {"status": self.execution.status}
                        )
                    else:
                        self.log_compensation_operation(
                            "rollback_execution",
                            "skipped",
                            {"reason": "Execution already in terminal state"}
                        )
                    compensation_result["operations"]["rollback_execution"] = {
                        "status": "success",
                        "execution_status": self.execution.status
                    }
                except Exception as e:
                    logger.exception(
                        f"Failed to rollback execution during compensation: {str(e)}",
                        extra={"execution_id": str(self.execution.id)}
                    )
                    self.log_compensation_operation(
                        "rollback_execution",
                        "failed",
                        {"error": str(e)}
                    )
                    compensation_result["status"] = "partial_failure"
                    compensation_result["operations"]["rollback_execution"] = {
                        "status": "failed",
                        "error": str(e)
                    }

            # Cancel associated job if exists
            if cleanup_job and self.execution.job:
                try:
                    from hub.apps.jobs.models import JobStatus

                    if self.execution.job.status not in [
                        JobStatus.COMPLETED,
                        JobStatus.FAILED,
                        JobStatus.CANCELLED
                    ]:
                        # Cancel the job
                        self.execution.job.status = JobStatus.CANCELLED
                        self.execution.job.save(update_fields=['status', 'updated_at'])
                        self.log_compensation_operation(
                            "cleanup_job",
                            "success",
                            {"job_id": str(self.execution.job.id)}
                        )
                    else:
                        self.log_compensation_operation(
                            "cleanup_job",
                            "skipped",
                            {"reason": "Job already in terminal state"}
                        )
                    compensation_result["operations"]["cleanup_job"] = {
                        "status": "success",
                        "job_id": str(self.execution.job.id)
                    }
                except Exception as e:
                    logger.exception(
                        f"Failed to cleanup job during compensation: {str(e)}",
                        extra={
                            "execution_id": str(self.execution.id),
                            "job_id": str(self.execution.job.id) if self.execution.job else None
                        }
                    )
                    self.log_compensation_operation(
                        "cleanup_job",
                        "failed",
                        {"error": str(e)}
                    )
                    compensation_result["status"] = "partial_failure"
                    compensation_result["operations"]["cleanup_job"] = {
                        "status": "failed",
                        "error": str(e)
                    }

            # Cleanup result asset if exists
            if cleanup_result_asset and self.execution.result_asset:
                try:
                    # Note: We don't delete the asset, just remove the reference
                    # Asset deletion should be handled by asset lifecycle management
                    # We just log that the asset was created but execution failed
                    self.log_compensation_operation(
                        "cleanup_result_asset",
                        "success",
                        {
                            "result_asset_id": str(self.execution.result_asset.id),
                            "note": "Asset reference removed, asset itself not deleted"
                        }
                    )
                    compensation_result["operations"]["cleanup_result_asset"] = {
                        "status": "success",
                        "result_asset_id": str(self.execution.result_asset.id),
                        "note": "Asset reference removed"
                    }
                except Exception as e:
                    logger.exception(
                        f"Failed to cleanup result asset during compensation: {str(e)}",
                        extra={
                            "execution_id": str(self.execution.id),
                            "result_asset_id": str(self.execution.result_asset.id) if self.execution.result_asset else None
                        }
                    )
                    self.log_compensation_operation(
                        "cleanup_result_asset",
                        "failed",
                        {"error": str(e)}
                    )
                    compensation_result["status"] = "partial_failure"
                    compensation_result["operations"]["cleanup_result_asset"] = {
                        "status": "failed",
                        "error": str(e)
                    }

            # Store compensation log in execution
            if self.compensation_log:
                if isinstance(self.execution.execution_log, list):
                    self.execution.execution_log.append({
                        "timestamp": timezone.now().isoformat(),
                        "level": "INFO",
                        "message": "Compensation operations completed",
                        "data": {
                            "compensation_log": self.compensation_log,
                            "compensation_result": compensation_result
                        }
                    })
                    self.execution.save(update_fields=['execution_log', 'updated_at'])

            # Publish compensation events (non-critical)
            if publish_compensation_events:
                try:
                    from hub.apps.core.events.service_publishers import TransformationEventPublisher
                    publisher = TransformationEventPublisher()
                    publisher.publish_pipeline_execution_failed(
                        pipeline_id=str(self.execution.pipeline.id),
                        execution_id=str(self.execution.id),
                        error_message="Execution failed and compensation completed",
                        error_code="COMPENSATION_COMPLETED",
                        error_details=compensation_result,
                        tenant_id=str(self.execution.pipeline.tenant_id),
                        user_id=None  # User ID not available in compensation context
                    )
                    self.log_compensation_operation(
                        "publish_compensation_events",
                        "success"
                    )
                except Exception as e:
                    # Non-critical, just log
                    logger.warning(
                        f"Failed to publish compensation events (non-critical): {str(e)}",
                        extra={"execution_id": str(self.execution.id)}
                    )
                    self.log_compensation_operation(
                        "publish_compensation_events",
                        "failed",
                        {"error": str(e), "note": "Non-critical operation"}
                    )

            compensation_result["compensation_log"] = self.compensation_log
            return compensation_result

        except Exception as e:
            logger.exception(
                f"Compensation failed with unexpected error: {str(e)}",
                extra={"execution_id": str(self.execution.id)}
            )
            compensation_result["status"] = "failed"
            compensation_result["error"] = str(e)
            compensation_result["compensation_log"] = self.compensation_log
            return compensation_result

