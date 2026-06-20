"""
Observability Service

Service layer for observability operations.
Extracts observability logic from views.py and monitoring modules.
"""

from typing import Any

import structlog

from hub.apps.core.events.service_publishers import ObservabilityEventPublisher
from hub.apps.core.services.base import BaseService, NotFoundError
from hub.apps.observability.freshness import FreshnessMonitor
from hub.apps.observability.schema_drift import SchemaDriftDetector
from hub.apps.observability.volume import VolumeMonitor

logger = structlog.get_logger(__name__)


def _hex_to_uuid(hex_string: str, length: int = 32) -> str:
    """
    Convert hex string to UUID format.

    Args:
        hex_string: Hex string (without 0x prefix)
        length: Target length (32 for UUID, pad if needed)

    Returns:
        UUID format string: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    """
    # Pad to required length
    padded = hex_string.zfill(length)
    # Convert to UUID format
    return f"{padded[:8]}-{padded[8:12]}-{padded[12:16]}-{padded[16:20]}-{padded[20:]}"


class ObservabilityService(BaseService, ObservabilityEventPublisher):
    """
    Service for observability operations.

    Provides business logic for:
    - Data freshness monitoring
    - Volume monitoring
    - Schema drift detection

    Publishes observability events for metrics, traces, logs, and alerts.
    """

    service_name = "observability_service"

    def __init__(self, tenant_id: str | None = None, user_id: str | None = None):
        """
        Initialize ObservabilityService.

        Args:
            tenant_id: Optional tenant ID
            user_id: Optional user ID
        """
        # Set attributes directly (BaseService doesn't have __init__)
        self.tenant_id = tenant_id
        self.user_id = user_id
        # Initialize event publisher
        ObservabilityEventPublisher.__init__(self, tenant_id=tenant_id, user_id=user_id)

    def _validate_tenant_id(self, tenant_id: str) -> None:
        """Ensure tenant exists; raise NotFoundError if not."""
        from hub.apps.tenants.models import Tenant

        if not Tenant.objects.filter(id=tenant_id).exists():
            raise NotFoundError(f"Tenant with id {tenant_id} not found")

    def get_freshness_dashboard(
        self,
        tenant_id: str,
        dataset_id: str | None = None,
        asset_id: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Get data freshness dashboard.

        Args:
            tenant_id: Tenant ID
            dataset_id: Optional dataset ID filter
            asset_id: Optional asset ID filter
            limit: Maximum number of records

        Returns:
            Freshness dashboard data dictionary
        """
        self._validate_tenant_id(tenant_id)
        import time

        from opentelemetry import trace

        start_time = time.time()
        trace_id = None
        span_id = None

        # Try to get trace context if OpenTelemetry is enabled
        if hasattr(trace, "get_current_span"):
            try:
                span = trace.get_current_span()
                if span and span.get_span_context().is_valid:
                    span_context = span.get_span_context()
                    # Convert 128-bit trace_id to UUID format (32 hex chars -> UUID)
                    trace_id_hex = format(span_context.trace_id, "032x")
                    trace_id = _hex_to_uuid(trace_id_hex, length=32)
                    # Convert 64-bit span_id to UUID format (pad to 32 hex chars)
                    span_id_hex = format(span_context.span_id, "016x")
                    span_id = _hex_to_uuid(span_id_hex, length=32)
            except Exception as e:
                logger.debug(
                    "observability_trace_context_failed",
                    extra={
                        "error_type": type(e).__name__,
                        "error": str(e),
                        "operation": "get_freshness_dashboard",
                    },
                )

        try:
            result = self.execute_with_metrics(
                operation="get_freshness_dashboard",
                func=lambda: FreshnessMonitor.get_freshness_dashboard(
                    tenant_id=tenant_id, dataset_id=dataset_id, asset_id=asset_id, limit=limit
                ),
                tenant_id=tenant_id,
            )

            # Publish trace event if we have trace context
            if trace_id and span_id:
                duration_ms = (time.time() - start_time) * 1000
                try:
                    self.publish_trace_created(
                        trace_id=trace_id,
                        span_id=span_id,
                        operation_name="get_freshness_dashboard",
                        duration_ms=duration_ms,
                        status="ok",
                        attributes={
                            "dataset_id": dataset_id,
                            "asset_id": asset_id,
                            "limit": limit,
                        },
                        tenant_id=tenant_id,
                    )
                except Exception as e:
                    logger.warning(
                        "failed_to_publish_trace_event",
                        error=str(e),
                        operation="get_freshness_dashboard",
                    )

            return result
        except Exception as e:
            # Publish trace event with error status if we have trace context
            if trace_id and span_id:
                duration_ms = (time.time() - start_time) * 1000
                try:
                    self.publish_trace_created(
                        trace_id=trace_id,
                        span_id=span_id,
                        operation_name="get_freshness_dashboard",
                        duration_ms=duration_ms,
                        status="error",
                        attributes={
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                        tenant_id=tenant_id,
                    )
                except Exception as pub_err:
                    logger.warning(
                        "observability_trace_event_publish_failed",
                        extra={
                            "error_type": type(pub_err).__name__,
                            "error": str(pub_err),
                            "operation": "get_freshness_dashboard",
                        },
                    )
            raise

    def get_volume_dashboard(
        self,
        tenant_id: str,
        dataset_id: str | None = None,
        asset_id: str | None = None,
        limit: int = 100,
        period_type: str = "DAILY",
    ) -> dict[str, Any]:
        """
        Get volume monitoring dashboard.

        Args:
            tenant_id: Tenant ID
            dataset_id: Optional dataset ID filter
            asset_id: Optional asset ID filter
            limit: Maximum number of records
            period_type: Period type (HOURLY or DAILY, default: DAILY)

        Returns:
            Volume dashboard data dictionary
        """
        self._validate_tenant_id(tenant_id)
        import time

        from opentelemetry import trace

        start_time = time.time()
        trace_id = None
        span_id = None

        # Try to get trace context if OpenTelemetry is enabled
        if hasattr(trace, "get_current_span"):
            try:
                span = trace.get_current_span()
                if span and span.get_span_context().is_valid:
                    span_context = span.get_span_context()
                    # Convert 128-bit trace_id to UUID format (32 hex chars -> UUID)
                    trace_id_hex = format(span_context.trace_id, "032x")
                    trace_id = _hex_to_uuid(trace_id_hex, length=32)
                    # Convert 64-bit span_id to UUID format (pad to 32 hex chars)
                    span_id_hex = format(span_context.span_id, "016x")
                    span_id = _hex_to_uuid(span_id_hex, length=32)
            except Exception as e:
                logger.debug(
                    "observability_trace_context_failed",
                    extra={
                        "error_type": type(e).__name__,
                        "error": str(e),
                        "operation": "get_volume_dashboard",
                    },
                )

        try:
            result = self.execute_with_metrics(
                operation="get_volume_dashboard",
                func=lambda: VolumeMonitor.get_volume_dashboard(
                    tenant_id=tenant_id,
                    dataset_id=dataset_id,
                    asset_id=asset_id,
                    period_type=period_type,
                    limit=limit,
                ),
                tenant_id=tenant_id,
            )

            # Publish trace event if we have trace context
            if trace_id and span_id:
                duration_ms = (time.time() - start_time) * 1000
                try:
                    self.publish_trace_created(
                        trace_id=trace_id,
                        span_id=span_id,
                        operation_name="get_volume_dashboard",
                        duration_ms=duration_ms,
                        status="ok",
                        attributes={
                            "dataset_id": dataset_id,
                            "asset_id": asset_id,
                            "period_type": period_type,
                            "limit": limit,
                        },
                        tenant_id=tenant_id,
                    )
                except Exception as e:
                    logger.warning(
                        "failed_to_publish_trace_event",
                        error=str(e),
                        operation="get_volume_dashboard",
                    )

            return result
        except Exception as e:
            # Publish trace event with error status if we have trace context
            if trace_id and span_id:
                duration_ms = (time.time() - start_time) * 1000
                try:
                    self.publish_trace_created(
                        trace_id=trace_id,
                        span_id=span_id,
                        operation_name="get_volume_dashboard",
                        duration_ms=duration_ms,
                        status="error",
                        attributes={
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                        tenant_id=tenant_id,
                    )
                except Exception as pub_err:
                    logger.warning(
                        "observability_trace_event_publish_failed",
                        extra={
                            "error_type": type(pub_err).__name__,
                            "error": str(pub_err),
                            "operation": "get_volume_dashboard",
                        },
                    )
            raise

    def get_schema_drift_dashboard(
        self,
        tenant_id: str,
        dataset_id: str | None = None,
        asset_id: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Get schema drift detection dashboard.

        Args:
            tenant_id: Tenant ID
            dataset_id: Optional dataset ID filter
            asset_id: Optional asset ID filter
            limit: Maximum number of records

        Returns:
            Schema drift dashboard data dictionary
        """
        self._validate_tenant_id(tenant_id)
        import time

        from opentelemetry import trace

        start_time = time.time()
        trace_id = None
        span_id = None

        # Try to get trace context if OpenTelemetry is enabled
        if hasattr(trace, "get_current_span"):
            try:
                span = trace.get_current_span()
                if span and span.get_span_context().is_valid:
                    span_context = span.get_span_context()
                    # Convert 128-bit trace_id to UUID format (32 hex chars -> UUID)
                    trace_id_hex = format(span_context.trace_id, "032x")
                    trace_id = _hex_to_uuid(trace_id_hex, length=32)
                    # Convert 64-bit span_id to UUID format (pad to 32 hex chars)
                    span_id_hex = format(span_context.span_id, "016x")
                    span_id = _hex_to_uuid(span_id_hex, length=32)
            except Exception as e:
                logger.debug(
                    "observability_trace_context_failed",
                    extra={
                        "error_type": type(e).__name__,
                        "error": str(e),
                        "operation": "get_schema_drift_dashboard",
                    },
                )

        try:
            result = self.execute_with_metrics(
                operation="get_schema_drift_dashboard",
                func=lambda: SchemaDriftDetector.get_drift_dashboard(
                    tenant_id=tenant_id, dataset_id=dataset_id, asset_id=asset_id, limit=limit
                ),
                tenant_id=tenant_id,
            )

            # Publish trace event if we have trace context
            if trace_id and span_id:
                duration_ms = (time.time() - start_time) * 1000
                try:
                    self.publish_trace_created(
                        trace_id=trace_id,
                        span_id=span_id,
                        operation_name="get_schema_drift_dashboard",
                        duration_ms=duration_ms,
                        status="ok",
                        attributes={
                            "dataset_id": dataset_id,
                            "asset_id": asset_id,
                            "limit": limit,
                        },
                        tenant_id=tenant_id,
                    )
                except Exception as e:
                    logger.warning(
                        "failed_to_publish_trace_event",
                        error=str(e),
                        operation="get_schema_drift_dashboard",
                    )

            return result
        except Exception as e:
            # Publish trace event with error status if we have trace context
            if trace_id and span_id:
                duration_ms = (time.time() - start_time) * 1000
                try:
                    self.publish_trace_created(
                        trace_id=trace_id,
                        span_id=span_id,
                        operation_name="get_schema_drift_dashboard",
                        duration_ms=duration_ms,
                        status="error",
                        attributes={
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                        tenant_id=tenant_id,
                    )
                except Exception as pub_err:
                    logger.warning(
                        "observability_trace_event_publish_failed",
                        extra={
                            "error_type": type(pub_err).__name__,
                            "error": str(pub_err),
                            "operation": "get_schema_drift_dashboard",
                        },
                    )
            raise

    def record_metric(
        self,
        tenant_id: str,
        dataset_id: str | None = None,
        asset_id: str | None = None,
        last_update_time: str | None = None,
        freshness_sla: str | None = None,
        row_count: int | None = None,
        size_bytes: int | None = None,
        schema_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Record a data observability metric and publish event.

        Args:
            tenant_id: Tenant ID
            dataset_id: Optional dataset ID
            asset_id: Optional asset ID
            last_update_time: Last update timestamp (ISO format string)
            freshness_sla: Freshness SLA level
            row_count: Number of rows
            size_bytes: Size in bytes
            schema_json: Schema JSON for drift detection

        Returns:
            Dictionary with metric information
        """
        from django.utils.dateparse import parse_datetime

        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset
        from hub.apps.tenants.models import Tenant

        # Get tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise ValueError(f"Tenant {tenant_id} not found")

        # Get dataset/asset
        dataset = None
        asset = None

        if dataset_id:
            try:
                dataset = Dataset.objects.get(id=dataset_id, tenant=tenant)
            except Dataset.DoesNotExist:
                raise ValueError(f"Dataset {dataset_id} not found")

        if asset_id:
            try:
                asset = Asset.objects.get(id=asset_id, tenant=tenant)
            except Asset.DoesNotExist:
                raise ValueError(f"Asset {asset_id} not found")

        # Parse last_update_time
        parsed_last_update_time = None
        if last_update_time:
            parsed_last_update_time = parse_datetime(last_update_time)

        # Record metric
        metric = FreshnessMonitor.record_metric(
            tenant_id=tenant_id,
            dataset=dataset,
            asset=asset,
            last_update_time=parsed_last_update_time,
            freshness_sla=freshness_sla,
            row_count=row_count,
            size_bytes=size_bytes,
            schema_json=schema_json,
        )

        # Publish metric recorded event
        try:
            self.publish_metric_recorded(
                metric_name="data_observability_metric",
                metric_value=metric.freshness_age_seconds if metric.freshness_age_seconds else None,
                metric_type="gauge",
                labels={
                    "dataset_id": str(dataset.id) if dataset else None,
                    "asset_id": str(asset.id) if asset else None,
                    "freshness_sla": freshness_sla,
                    "is_stale": str(metric.is_stale),
                },
                tenant_id=tenant_id,
            )
        except Exception as e:
            logger.warning("failed_to_publish_metric_event", error=str(e), metric_id=str(metric.id))

        # Check if stale and publish alert if needed
        if metric.is_stale:
            try:
                self.publish_alert_triggered(
                    alert_name="data_stale",
                    alert_severity="warning",
                    alert_message=f"Data is stale: {metric.freshness_age_seconds}s exceeds SLA {freshness_sla}",
                    metric_name="freshness_age_seconds",
                    threshold_value=metric.freshness_sla_seconds,
                    current_value=metric.freshness_age_seconds,
                    dataset_id=str(dataset.id) if dataset else None,
                    asset_id=str(asset.id) if asset else None,
                    tenant_id=tenant_id,
                )
            except Exception as e:
                logger.warning(
                    "failed_to_publish_stale_alert_event", error=str(e), metric_id=str(metric.id)
                )

        # Detect schema drift if schema_json provided
        if schema_json:
            try:
                drift = SchemaDriftDetector.detect_drift(
                    tenant_id=tenant_id,
                    dataset=dataset,
                    asset=asset,
                    current_schema_json=schema_json,
                )

                # Publish alert if drift detected
                # SchemaDrift is only created when changes are found,
                # so its existence alone means drift was detected.
                if drift:
                    try:
                        self.publish_alert_triggered(
                            alert_name="schema_drift_detected",
                            alert_severity="warning",
                            alert_message=f"Schema drift detected for {'dataset' if dataset else 'asset'} {dataset_id or asset_id}",
                            metric_name="schema_drift",
                            threshold_value=0,
                            current_value=len(drift.new_fields or [])
                            + len(drift.removed_fields or [])
                            + len(drift.type_changes or [])
                            or 1,
                            dataset_id=str(dataset.id) if dataset else None,
                            asset_id=str(asset.id) if asset else None,
                            tenant_id=tenant_id,
                        )
                    except Exception as e:
                        logger.warning(
                            "failed_to_publish_schema_drift_alert_event",
                            error=str(e),
                            drift_id=str(drift.id) if drift else None,
                        )
            except Exception as e:
                logger.warning("failed_to_detect_schema_drift", error=str(e))

        return {
            "id": str(metric.id),
            "recorded_at": metric.recorded_at.isoformat(),
            "is_stale": metric.is_stale,
        }

    def publish_log_event(
        self,
        message: str,
        log_level: str = "INFO",
        logger_name: str | None = None,
        context: dict[str, Any] | None = None,
        tenant_id: str | None = None,
    ) -> str:
        """
        Publish a log event.

        This is a convenience method for publishing log events from observability operations.

        Args:
            message: Log message
            log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            logger_name: Logger name
            context: Additional context dictionary
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            Event ID
        """
        return self.publish_log_created(
            message=message,
            log_level=log_level,
            logger_name=logger_name or self.__class__.__module__,
            context=context,
            tenant_id=tenant_id or self.tenant_id,
        )
