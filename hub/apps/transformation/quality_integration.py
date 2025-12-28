"""
Quality Integration Service for Transformation Pipelines

Integrates with QualityService to run quality checks on input and output assets
during transformation pipeline execution, compare metrics, and publish alerts.
"""
import structlog
from typing import Dict, Any, Optional, Tuple, List
from django.utils import timezone
from django.db import transaction

from hub.apps.dq.service_client import DQServiceClient
from hub.apps.dq.alerting import DQAlertingService
from hub.apps.dq.models import DQRun, DQRunStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset
from hub.apps.transformation.models import PipelineExecution

logger = structlog.get_logger(__name__)


class TransformationQualityIntegration:
    """
    Service for integrating quality checks into transformation pipeline execution.

    Provides methods to:
    - Run quality checks on input asset before transformation
    - Run quality checks on output asset after transformation
    - Compare quality metrics (before vs after)
    - Store quality metrics in execution_log
    - Publish quality degradation alerts
    """

    def __init__(self, execution: PipelineExecution):
        """
        Initialize quality integration for a pipeline execution.

        Args:
            execution: PipelineExecution instance
        """
        self.execution = execution
        self.dq_client = DQServiceClient()
        self.alerting_service = DQAlertingService()
        self.storage_client = S3StorageClient()

    def run_input_quality_check(
        self,
        profile_key: str = "intake_basic_gx"
    ) -> Dict[str, Any]:
        """
        Run quality checks on input asset before transformation.

        Args:
            profile_key: DQ profile key to use (default: "intake_basic_gx")

        Returns:
            Dictionary with quality check results including:
            - quality_score: Overall quality score (0.0-1.0)
            - overall_status: Overall status (PASS, WARN, FAIL)
            - checks: List of individual check results
            - engine_type: DQ engine type used
            - engine_version: DQ engine version
            - metadata: Additional metadata
        """
        asset = self.execution.asset

        # Get latest dataset for asset
        latest_dataset = asset.datasets.order_by('-version').first()
        if not latest_dataset or not latest_dataset.file:
            logger.warning(
                "No dataset or file found for input asset quality check",
                execution_id=str(self.execution.id),
                asset_id=str(asset.id)
            )
            return {
                "quality_score": None,
                "overall_status": "UNKNOWN",
                "checks": [],
                "engine_type": None,
                "engine_version": None,
                "metadata": {
                    "error": "No dataset or file found for asset"
                }
            }

        file_obj = latest_dataset.file

        # Get contract for asset (for quality rules extraction)
        contract = asset.contracts.filter(status="ACTIVE").first()

        try:
            # Check DQ service health
            is_healthy, _ = self.dq_client.health_check()
            if not is_healthy:
                logger.warning(
                    "DQ service is unavailable, skipping input quality check",
                    execution_id=str(self.execution.id),
                    asset_id=str(asset.id)
                )
                return {
                    "quality_score": None,
                    "overall_status": "UNKNOWN",
                    "checks": [],
                    "engine_type": None,
                    "engine_version": None,
                    "metadata": {
                        "error": "DQ service unavailable"
                    }
                }

            # Download file content
            file_content = self.storage_client.get_file_content(file_obj.storage_path)

            # Determine file format
            file_format = self._determine_file_format(file_obj, latest_dataset)

            # Run DQ check
            dq_result = self.dq_client.run_dq(
                file_content=file_content,
                file_format=file_format,
                profile_key=profile_key,
                contract=contract
            )

            logger.info(
                "Input quality check completed",
                execution_id=str(self.execution.id),
                asset_id=str(asset.id),
                quality_score=dq_result.get("quality_score"),
                overall_status=dq_result.get("overall_status")
            )

            return dq_result

        except Exception as e:
            logger.error(
                "Failed to run input quality check",
                execution_id=str(self.execution.id),
                asset_id=str(asset.id),
                error=str(e),
                exc_info=True
            )
            return {
                "quality_score": None,
                "overall_status": "UNKNOWN",
                "checks": [],
                "engine_type": None,
                "engine_version": None,
                "metadata": {
                    "error": str(e)
                }
            }

    def run_output_quality_check(
        self,
        result_asset: Asset,
        profile_key: str = "intake_basic_gx"
    ) -> Dict[str, Any]:
        """
        Run quality checks on output asset after transformation.

        Args:
            result_asset: Result asset created by transformation
            profile_key: DQ profile key to use (default: "intake_basic_gx")

        Returns:
            Dictionary with quality check results including:
            - quality_score: Overall quality score (0.0-1.0)
            - overall_status: Overall status (PASS, WARN, FAIL)
            - checks: List of individual check results
            - engine_type: DQ engine type used
            - engine_version: DQ engine version
            - metadata: Additional metadata
        """
        # Get latest dataset for result asset
        latest_dataset = result_asset.datasets.order_by('-version').first()
        if not latest_dataset or not latest_dataset.file:
            logger.warning(
                "No dataset or file found for output asset quality check",
                execution_id=str(self.execution.id),
                result_asset_id=str(result_asset.id)
            )
            return {
                "quality_score": None,
                "overall_status": "UNKNOWN",
                "checks": [],
                "engine_type": None,
                "engine_version": None,
                "metadata": {
                    "error": "No dataset or file found for result asset"
                }
            }

        file_obj = latest_dataset.file

        # Get contract for result asset (for quality rules extraction)
        contract = result_asset.contracts.filter(status="ACTIVE").first()

        try:
            # Check DQ service health
            is_healthy, _ = self.dq_client.health_check()
            if not is_healthy:
                logger.warning(
                    "DQ service is unavailable, skipping output quality check",
                    execution_id=str(self.execution.id),
                    result_asset_id=str(result_asset.id)
                )
                return {
                    "quality_score": None,
                    "overall_status": "UNKNOWN",
                    "checks": [],
                    "engine_type": None,
                    "engine_version": None,
                    "metadata": {
                        "error": "DQ service unavailable"
                    }
                }

            # Download file content
            file_content = self.storage_client.get_file_content(file_obj.storage_path)

            # Determine file format
            file_format = self._determine_file_format(file_obj, latest_dataset)

            # Run DQ check
            dq_result = self.dq_client.run_dq(
                file_content=file_content,
                file_format=file_format,
                profile_key=profile_key,
                contract=contract
            )

            logger.info(
                "Output quality check completed",
                execution_id=str(self.execution.id),
                result_asset_id=str(result_asset.id),
                quality_score=dq_result.get("quality_score"),
                overall_status=dq_result.get("overall_status")
            )

            return dq_result

        except Exception as e:
            logger.error(
                "Failed to run output quality check",
                execution_id=str(self.execution.id),
                result_asset_id=str(result_asset.id),
                error=str(e),
                exc_info=True
            )
            return {
                "quality_score": None,
                "overall_status": "UNKNOWN",
                "checks": [],
                "engine_type": None,
                "engine_version": None,
                "metadata": {
                    "error": str(e)
                }
            }

    def compare_quality_metrics(
        self,
        input_metrics: Dict[str, Any],
        output_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compare quality metrics between input and output assets.

        Args:
            input_metrics: Quality metrics from input asset check
            output_metrics: Quality metrics from output asset check

        Returns:
            Dictionary with comparison results including:
            - quality_score_delta: Change in quality score (output - input)
            - quality_score_delta_percent: Percentage change
            - status_change: Change in overall status
            - checks_comparison: Comparison of individual checks
            - degradation_detected: Boolean indicating if quality degraded
            - improvement_detected: Boolean indicating if quality improved
        """
        input_score = input_metrics.get("quality_score")
        output_score = output_metrics.get("quality_score")

        # Handle None scores
        if input_score is None or output_score is None:
            return {
                "quality_score_delta": None,
                "quality_score_delta_percent": None,
                "status_change": None,
                "checks_comparison": [],
                "degradation_detected": False,
                "improvement_detected": False,
                "metadata": {
                    "error": "Cannot compare: missing quality scores",
                    "input_score": input_score,
                    "output_score": output_score
                }
            }

        # Calculate delta
        quality_score_delta = output_score - input_score
        quality_score_delta_percent = (quality_score_delta / input_score * 100) if input_score > 0 else 0.0

        # Determine status change
        input_status = input_metrics.get("overall_status", "UNKNOWN")
        output_status = output_metrics.get("overall_status", "UNKNOWN")
        status_change = self._compare_status(input_status, output_status)

        # Compare individual checks
        checks_comparison = self._compare_checks(
            input_metrics.get("checks", []),
            output_metrics.get("checks", [])
        )

        # Determine if degradation/improvement detected
        degradation_detected = quality_score_delta < 0
        improvement_detected = quality_score_delta > 0

        comparison = {
            "quality_score_delta": quality_score_delta,
            "quality_score_delta_percent": quality_score_delta_percent,
            "status_change": status_change,
            "checks_comparison": checks_comparison,
            "degradation_detected": degradation_detected,
            "improvement_detected": improvement_detected,
            "input_quality_score": input_score,
            "output_quality_score": output_score,
            "input_status": input_status,
            "output_status": output_status
        }

        logger.info(
            "Quality metrics comparison completed",
            execution_id=str(self.execution.id),
            quality_score_delta=quality_score_delta,
            quality_score_delta_percent=quality_score_delta_percent,
            degradation_detected=degradation_detected
        )

        return comparison

    def store_quality_metrics_in_execution_log(
        self,
        input_metrics: Dict[str, Any],
        output_metrics: Optional[Dict[str, Any]] = None,
        comparison: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Store quality metrics in execution_log.

        Args:
            input_metrics: Quality metrics from input asset check
            output_metrics: Optional quality metrics from output asset check
            comparison: Optional comparison results
        """
        # Ensure execution_log is a list
        if not isinstance(self.execution.execution_log, list):
            self.execution.execution_log = []

        # Create log entry for input quality check
        input_log_entry = {
            "timestamp": timezone.now().isoformat(),
            "type": "quality_check",
            "stage": "input",
            "quality_score": input_metrics.get("quality_score"),
            "overall_status": input_metrics.get("overall_status"),
            "checks_count": len(input_metrics.get("checks", [])),
            "engine_type": input_metrics.get("engine_type"),
            "engine_version": input_metrics.get("engine_version"),
            "metadata": input_metrics.get("metadata", {})
        }
        self.execution.execution_log.append(input_log_entry)

        # Add output quality check log entry if available
        if output_metrics:
            output_log_entry = {
                "timestamp": timezone.now().isoformat(),
                "type": "quality_check",
                "stage": "output",
                "quality_score": output_metrics.get("quality_score"),
                "overall_status": output_metrics.get("overall_status"),
                "checks_count": len(output_metrics.get("checks", [])),
                "engine_type": output_metrics.get("engine_type"),
                "engine_version": output_metrics.get("engine_version"),
                "metadata": output_metrics.get("metadata", {})
            }
            self.execution.execution_log.append(output_log_entry)

        # Add comparison log entry if available
        if comparison:
            comparison_log_entry = {
                "timestamp": timezone.now().isoformat(),
                "type": "quality_comparison",
                "quality_score_delta": comparison.get("quality_score_delta"),
                "quality_score_delta_percent": comparison.get("quality_score_delta_percent"),
                "status_change": comparison.get("status_change"),
                "degradation_detected": comparison.get("degradation_detected"),
                "improvement_detected": comparison.get("improvement_detected"),
                "input_quality_score": comparison.get("input_quality_score"),
                "output_quality_score": comparison.get("output_quality_score"),
                "checks_comparison": comparison.get("checks_comparison", [])
            }
            self.execution.execution_log.append(comparison_log_entry)

        # Save execution
        self.execution.save(update_fields=['execution_log', 'updated_at'])

        logger.info(
            "Quality metrics stored in execution_log",
            execution_id=str(self.execution.id),
            has_output=output_metrics is not None,
            has_comparison=comparison is not None
        )

    def publish_quality_degradation_alerts(
        self,
        comparison: Dict[str, Any],
        threshold: float = 0.05
    ) -> List[Dict[str, Any]]:
        """
        Publish quality degradation alerts if quality drops below threshold.

        Args:
            comparison: Quality metrics comparison results
            threshold: Quality degradation threshold (default: 0.05 = 5% drop)

        Returns:
            List of published alerts
        """
        alerts_published = []

        # Check if degradation detected
        if not comparison.get("degradation_detected", False):
            logger.debug(
                "No quality degradation detected, skipping alerts",
                execution_id=str(self.execution.id)
            )
            return alerts_published

        quality_score_delta = comparison.get("quality_score_delta")
        quality_score_delta_percent = comparison.get("quality_score_delta_percent")

        # Check if degradation exceeds threshold
        if quality_score_delta is None:
            return alerts_published

        # Use absolute value for threshold check
        abs_delta_percent = abs(quality_score_delta_percent) if quality_score_delta_percent is not None else 0.0
        threshold_percent = threshold * 100

        if abs_delta_percent < threshold_percent:
            logger.debug(
                "Quality degradation below threshold, skipping alerts",
                execution_id=str(self.execution.id),
                delta_percent=abs_delta_percent,
                threshold_percent=threshold_percent
            )
            return alerts_published

        # Create DQ run for alerting (if needed)
        # For transformation quality alerts, we'll create a synthetic alert
        # that can be evaluated by the alerting service
        try:
            # Get result asset
            result_asset = self.execution.result_asset
            if not result_asset:
                logger.warning(
                    "No result asset available for quality degradation alert",
                    execution_id=str(self.execution.id)
                )
                return alerts_published

            # Create a temporary DQ run for alerting purposes
            # This allows us to use the existing alerting infrastructure
            dq_run = self._create_alerting_dq_run(result_asset, comparison)

            # Evaluate alerting rules
            triggered_alerts = self.alerting_service.evaluate_rules(
                dq_run=dq_run,
                metric_type="quality_score"
            )

            # Also create a custom transformation-specific alert
            custom_alert = {
                "type": "transformation_quality_degradation",
                "execution_id": str(self.execution.id),
                "pipeline_id": str(self.execution.pipeline.id),
                "pipeline_name": self.execution.pipeline.name,
                "input_asset_id": str(self.execution.asset.id),
                "input_asset_name": self.execution.asset.name,
                "result_asset_id": str(result_asset.id),
                "result_asset_name": result_asset.name,
                "quality_score_delta": quality_score_delta,
                "quality_score_delta_percent": quality_score_delta_percent,
                "input_quality_score": comparison.get("input_quality_score"),
                "output_quality_score": comparison.get("output_quality_score"),
                "status_change": comparison.get("status_change"),
                "threshold": threshold,
                "triggered_at": timezone.now().isoformat(),
                "message": (
                    f"Quality degradation detected in transformation pipeline '{self.execution.pipeline.name}': "
                    f"Quality score dropped by {abs(quality_score_delta_percent):.2f}% "
                    f"(from {comparison.get('input_quality_score'):.2%} to {comparison.get('output_quality_score'):.2%})"
                )
            }

            alerts_published.append(custom_alert)
            alerts_published.extend(triggered_alerts)

            # Publish transformation quality degradation event
            try:
                from hub.apps.core.events.service_publishers import TransformationEventPublisher
                from hub.apps.core.events.publisher import EventPublisher

                event_publisher = EventPublisher(
                    service_name="transformation_service",
                    tenant_id=str(self.execution.pipeline.tenant_id),
                    user_id=None
                )

                event_publisher.publish(
                    event_type="transformation.pipeline.quality.degradation",
                    data={
                        "execution_id": str(self.execution.id),
                        "pipeline_id": str(self.execution.pipeline.id),
                        "pipeline_name": self.execution.pipeline.name,
                        "input_asset_id": str(self.execution.asset.id),
                        "input_asset_name": self.execution.asset.name,
                        "result_asset_id": str(result_asset.id),
                        "result_asset_name": result_asset.name,
                        "quality_score_delta": quality_score_delta,
                        "quality_score_delta_percent": quality_score_delta_percent,
                        "input_quality_score": comparison.get("input_quality_score"),
                        "output_quality_score": comparison.get("output_quality_score"),
                        "threshold": threshold,
                        "status_change": comparison.get("status_change")
                    },
                    tenant_id=str(self.execution.pipeline.tenant_id)
                )
            except Exception as e:
                logger.warning(
                    "Failed to publish quality degradation event",
                    execution_id=str(self.execution.id),
                    error=str(e),
                    exc_info=True
                )

            logger.info(
                "Quality degradation alerts published",
                execution_id=str(self.execution.id),
                alerts_count=len(alerts_published),
                quality_score_delta_percent=quality_score_delta_percent
            )

        except Exception as e:
            logger.error(
                "Failed to publish quality degradation alerts",
                execution_id=str(self.execution.id),
                error=str(e),
                exc_info=True
            )

        return alerts_published

    def _determine_file_format(
        self,
        file_obj,
        dataset: Optional[Dataset] = None
    ) -> str:
        """
        Determine file format from file object and dataset.

        Args:
            file_obj: File model instance
            dataset: Optional Dataset model instance

        Returns:
            File format string (csv, json, parquet)
        """
        # Try dataset format first
        if dataset and dataset.format:
            format_map = {
                "CSV": "csv",
                "JSON": "json",
                "PARQUET": "parquet"
            }
            return format_map.get(dataset.format.upper(), "csv")

        # Try file content type
        if file_obj.content_type:
            content_type_map = {
                "text/csv": "csv",
                "application/csv": "csv",
                "application/json": "json",
                "text/json": "json",
                "application/parquet": "parquet",
                "application/x-parquet": "parquet"
            }
            if file_obj.content_type.lower() in content_type_map:
                return content_type_map[file_obj.content_type.lower()]

        # Try filename extension
        if file_obj.name:
            filename_lower = file_obj.name.lower()
            if filename_lower.endswith(".csv"):
                return "csv"
            elif filename_lower.endswith((".json", ".ndjson")):
                return "json"
            elif filename_lower.endswith(".parquet"):
                return "parquet"

        # Default to csv
        return "csv"

    def _compare_status(
        self,
        input_status: str,
        output_status: str
    ) -> str:
        """
        Compare status change between input and output.

        Args:
            input_status: Input asset status
            output_status: Output asset status

        Returns:
            Status change description
        """
        status_order = {"PASS": 3, "WARN": 2, "FAIL": 1, "UNKNOWN": 0}

        input_order = status_order.get(input_status.upper(), 0)
        output_order = status_order.get(output_status.upper(), 0)

        if output_order > input_order:
            return "IMPROVED"
        elif output_order < input_order:
            return "DEGRADED"
        else:
            return "UNCHANGED"

    def _compare_checks(
        self,
        input_checks: list,
        output_checks: list
    ) -> list:
        """
        Compare individual quality checks between input and output.

        Args:
            input_checks: List of input check results
            output_checks: List of output check results

        Returns:
            List of check comparisons
        """
        # Create maps for easier lookup
        input_checks_map = {
            check.get("check_id") or check.get("name"): check
            for check in input_checks
        }
        output_checks_map = {
            check.get("check_id") or check.get("name"): check
            for check in output_checks
        }

        # Get all unique check IDs
        all_check_ids = set(input_checks_map.keys()) | set(output_checks_map.keys())

        comparisons = []
        for check_id in all_check_ids:
            input_check = input_checks_map.get(check_id)
            output_check = output_checks_map.get(check_id)

            comparison = {
                "check_id": check_id,
                "check_name": input_check.get("name") if input_check else output_check.get("name"),
                "input_status": input_check.get("status") if input_check else None,
                "output_status": output_check.get("status") if output_check else None,
                "status_change": None,
                "input_value": input_check.get("value") if input_check else None,
                "output_value": output_check.get("value") if output_check else None,
                "value_delta": None
            }

            # Calculate status change
            if input_check and output_check:
                comparison["status_change"] = self._compare_status(
                    input_check.get("status", "UNKNOWN"),
                    output_check.get("status", "UNKNOWN")
                )

                # Calculate value delta if both have numeric values
                input_value = input_check.get("value")
                output_value = output_check.get("value")
                if isinstance(input_value, (int, float)) and isinstance(output_value, (int, float)):
                    comparison["value_delta"] = output_value - input_value

            comparisons.append(comparison)

        return comparisons

    def _create_alerting_dq_run(
        self,
        asset: Asset,
        comparison: Dict[str, Any]
    ) -> DQRun:
        """
        Create a DQ run for alerting purposes.

        Args:
            asset: Asset to create DQ run for
            comparison: Quality comparison results

        Returns:
            DQRun instance
        """
        # Try to get existing DQ run for this asset
        # If not found, create a minimal one for alerting
        dq_run = DQRun.objects.filter(
            asset=asset,
            tenant=asset.tenant
        ).order_by('-created_at').first()

        if not dq_run:
            # Create job first (required for DQRun)
            from hub.apps.jobs.utils import create_job, get_job_timeout
            from hub.apps.jobs.models import JobType
            import uuid

            temp_resource_id = str(uuid.uuid4())
            job = create_job(
                tenant=asset.tenant,
                user=None,  # System-initiated
                job_type=JobType.DQ_RUN,
                resource_type="DQ_RUN",
                resource_id=temp_resource_id,
                details_json={
                    "from_transformation": True,
                    "execution_id": str(self.execution.id)
                },
                timeout_seconds=get_job_timeout(JobType.DQ_RUN)
            )

            # Create minimal DQ run for alerting
            from hub.apps.dq.models import DQEngine
            dq_run = DQRun.objects.create(
                tenant=asset.tenant,
                asset=asset,
                job=job,
                profile_key="intake_basic_gx",  # Default profile
                engine=DQEngine.GREAT_EXPECTATIONS,  # Default engine
                status=DQRunStatus.SUCCEEDED,
                quality_score=comparison.get("output_quality_score", 0.0),
                details_json={
                    "quality_score": comparison.get("output_quality_score", 0.0),
                    "overall_status": comparison.get("output_status", "UNKNOWN"),
                    "from_transformation": True,
                    "execution_id": str(self.execution.id)
                } if comparison else {}
            )

            # Update job with dq_run_id
            job.resource_id = str(dq_run.id)
            job.details_json['dq_run_id'] = str(dq_run.id)
            job.save(update_fields=['resource_id', 'details_json'])

        return dq_run

