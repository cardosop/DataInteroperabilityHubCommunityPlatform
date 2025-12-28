"""
Transformation Pipeline Monitoring

Provides metrics collection and distributed tracing for transformation pipelines.
"""
import logging
import time
from typing import Optional, Dict, Any
from contextlib import contextmanager

try:
    from opentelemetry import trace
except ImportError:
    trace = None

from hub.apps.observability.otel_metrics import (
    transformation_pipeline_created_total,
    transformation_pipeline_execution_duration_seconds,
    transformation_pipeline_execution_success_rate,
    transformation_pipeline_execution_queue_depth,
    transformation_preview_generation_duration_seconds,
    transformation_wrangling_operations_total,
)
from hub.apps.observability.otel_config import get_tracer

logger = logging.getLogger(__name__)


def _get_tracer():
    """Get OpenTelemetry tracer for transformation pipelines."""
    return get_tracer("transformation.pipeline")


def record_pipeline_created(tenant_id: str) -> None:
    """
    Record a transformation pipeline creation.

    Args:
        tenant_id: Tenant ID
    """
    try:
        transformation_pipeline_created_total.labels(
            tenant_id=tenant_id
        ).inc()
    except Exception as e:
        logger.warning(f"Failed to record pipeline created metric: {e}")


@contextmanager
def record_pipeline_execution(
    tenant_id: str,
    pipeline_id: Optional[str] = None,
    status: str = "unknown"
):
    """
    Context manager to record pipeline execution duration, success rate, and tracing.

    Args:
        tenant_id: Tenant ID
        pipeline_id: Optional pipeline ID for tracing
        status: Execution status (COMPLETED, FAILED, etc.)

    Yields:
        None
    """
    # Use span instrumentation helper for proper span management
    from hub.apps.observability.span_instrumentation import create_span, add_span_attributes, set_span_status, record_span_exception
    from opentelemetry.trace import StatusCode

    start_time = time.time()
    span_context = None
    span = None

    # Try to create span, but don't fail if it doesn't work
    try:
        span_context = create_span(
            "transformation.pipeline.execute",
            attributes={
                "tenant_id": tenant_id,
                "pipeline_id": pipeline_id or "unknown",
                "status": status
            }
        )
        span = span_context.__enter__()
    except Exception as e:
        logger.debug(f"Failed to create span: {e}")
        span = None

    try:
        yield
        execution_time = time.time() - start_time

        # Record duration
        try:
            transformation_pipeline_execution_duration_seconds.labels(
                status=status,
                tenant_id=tenant_id
            ).observe(execution_time)
        except Exception as e:
            logger.warning(f"Failed to record execution duration metric: {e}")

        # Update success rate (1.0 for success, 0.0 for failure)
        success_value = 1.0 if status == "COMPLETED" else 0.0
        try:
            transformation_pipeline_execution_success_rate.labels(
                tenant_id=tenant_id
            ).set(success_value)
        except Exception as e:
            logger.warning(f"Failed to record success rate metric: {e}")

        # Update span attributes
        if span:
            try:
                add_span_attributes({
                    "execution.duration_seconds": execution_time,
                    "execution.status": status
                })
                set_span_status(StatusCode.OK)
            except Exception as e:
                logger.debug(f"Failed to update span attributes: {e}")

    except Exception as e:
        execution_time = time.time() - start_time
        # Record failed execution
        try:
            transformation_pipeline_execution_duration_seconds.labels(
                status="FAILED",
                tenant_id=tenant_id
            ).observe(execution_time)
            transformation_pipeline_execution_success_rate.labels(
                tenant_id=tenant_id
            ).set(0.0)
        except Exception as e2:
            logger.warning(f"Failed to record failed execution metric: {e2}")

        # Update span with error
        if span:
            try:
                add_span_attributes({
                    "execution.duration_seconds": execution_time,
                    "execution.status": "FAILED",
                    "error": str(e)
                })
                record_span_exception(e)
                set_span_status(StatusCode.ERROR)
            except Exception as e2:
                logger.debug(f"Failed to update span with error: {e2}")
        # Re-raise the exception after recording metrics
        raise
    finally:
        # Clean up span context if it was created
        if span_context:
            try:
                # Exit with no exception if we're in finally (exception already handled above)
                span_context.__exit__(None, None, None)
            except Exception as e:
                logger.debug(f"Failed to exit span context: {e}")


def update_queue_depth(tenant_id: str, status: str, count: int) -> None:
    """
    Update the pipeline execution queue depth.

    Args:
        tenant_id: Tenant ID
        status: Execution status (PENDING, RUNNING, etc.)
        count: Number of executions in queue with this status
    """
    try:
        transformation_pipeline_execution_queue_depth.labels(
            status=status,
            tenant_id=tenant_id
        ).set(count)
    except Exception as e:
        logger.warning(f"Failed to update queue depth metric: {e}")


@contextmanager
def record_preview_generation(tenant_id: str):
    """
    Context manager to record preview generation duration.

    Args:
        tenant_id: Tenant ID

    Yields:
        None
    """
    start_time = time.time()
    try:
        yield
        duration = time.time() - start_time
        try:
            transformation_preview_generation_duration_seconds.labels(
                tenant_id=tenant_id
            ).observe(duration)
        except Exception as e:
            logger.warning(f"Failed to record preview generation duration: {e}")
    except Exception as e:
        duration = time.time() - start_time
        # Still record duration even on failure
        try:
            transformation_preview_generation_duration_seconds.labels(
                tenant_id=tenant_id
            ).observe(duration)
        except Exception as e2:
            logger.warning(f"Failed to record preview generation duration: {e2}")
        raise


def record_wrangling_operation(
    tenant_id: str,
    operation_type: str,
    status: str
) -> None:
    """
    Record a wrangling operation.

    Args:
        tenant_id: Tenant ID
        operation_type: Type of operation (FILTER, TRANSFORM, etc.)
        status: Operation status (SUCCESS, FAILED, etc.)
    """
    try:
        transformation_wrangling_operations_total.labels(
            operation_type=operation_type,
            status=status,
            tenant_id=tenant_id
        ).inc()
    except Exception as e:
        logger.warning(f"Failed to record wrangling operation metric: {e}")

