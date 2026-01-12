"""
Marketplace Integration Metrics Utilities

Helper functions for tracking marketplace integration metrics including
API calls, connector operations, and sync jobs.
"""
import time
import structlog
from typing import Optional, Dict, Any
from functools import wraps

logger = structlog.get_logger(__name__)


def track_marketplace_api_call(
    marketplace_type: str,
    endpoint: str,
    method: str,
    tenant_id: Optional[str] = None,
    func=None,
    *args,
    **kwargs
):
    """
    Track API calls to marketplaces with metrics.

    This function can be used as a decorator or called directly to wrap
    HTTP requests to marketplace APIs.

    Usage as decorator:
        @track_marketplace_api_call(marketplace_type="CKAN_INSTANCE", endpoint="/api/3/action/package_list", method="GET")
        def make_api_call(self, ...):
            ...

    Usage as context manager:
        with track_marketplace_api_call(marketplace_type, endpoint, method, tenant_id):
            response = httpx.get(url)

    Args:
        marketplace_type: Marketplace type (e.g., "CKAN_INSTANCE", "SNOWFLAKE_DATA_MARKETPLACE")
        endpoint: API endpoint path (e.g., "/api/3/action/package_list")
        method: HTTP method (e.g., "GET", "POST")
        tenant_id: Optional tenant ID for metrics
        func: Optional function to wrap (for decorator usage)
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        Result from function execution (if used as decorator) or context manager
    """
    start_time = time.time()
    status_code = "200"
    error_type = None

    # If used as decorator
    if func is not None:
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal status_code, error_type
            try:
                result = func(*args, **kwargs)
                # Try to extract status code from result if it's an httpx.Response
                if hasattr(result, 'status_code'):
                    status_code = str(result.status_code)
                return result
            except Exception as e:
                status_code = "error"
                error_type = type(e).__name__
                # Try to extract status code from exception
                if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                    status_code = str(e.response.status_code)
                raise
            finally:
                _record_api_metrics(
                    marketplace_type, endpoint, method, status_code,
                    start_time, tenant_id, error_type
                )
        return wrapper

    # If used as context manager
    class APICallTracker:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            nonlocal status_code, error_type
            if exc_type is not None:
                status_code = "error"
                error_type = exc_type.__name__
                # Try to extract status code from exception
                if hasattr(exc_val, 'response') and hasattr(exc_val.response, 'status_code'):
                    status_code = str(exc_val.response.status_code)
            _record_api_metrics(
                marketplace_type, endpoint, method, status_code,
                start_time, tenant_id, error_type
            )
            return False  # Don't suppress exceptions

    return APICallTracker()


def _record_api_metrics(
    marketplace_type: str,
    endpoint: str,
    method: str,
    status_code: str,
    start_time: float,
    tenant_id: Optional[str],
    error_type: Optional[str]
):
    """Record API call metrics and structured logging."""
    try:
        from hub.apps.integrations.logging_utils import get_correlation_context
        correlation_context = get_correlation_context()
    except Exception:
        correlation_context = {}

    duration = time.time() - start_time
    is_error = status_code == "error" or (status_code.startswith("4") or status_code.startswith("5"))

    # Log API call with structured fields
    log_level = "error" if is_error else "info"
    logger.log(
        log_level,
        "marketplace_api_call",
        marketplace_type=marketplace_type,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        tenant_id=tenant_id,
        duration_seconds=duration,
        error_type=error_type if is_error else None,
        **correlation_context,
    )

    try:
        from hub.apps.observability.otel_metrics import (
            marketplace_api_calls_total,
            marketplace_api_call_duration_seconds,
            marketplace_api_call_errors_total,
        )

        # Record API call count
        marketplace_api_calls_total.labels(
            marketplace_type=marketplace_type,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            tenant_id=tenant_id or "unknown",
        ).inc()

        # Record duration
        marketplace_api_call_duration_seconds.labels(
            marketplace_type=marketplace_type,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
        ).observe(duration)

        # Record errors if any
        if is_error:
            marketplace_api_call_errors_total.labels(
                marketplace_type=marketplace_type,
                endpoint=endpoint,
                method=method,
                error_type=error_type or status_code,
                tenant_id=tenant_id or "unknown",
            ).inc()
    except Exception as e:
        # Log but don't fail API call if metrics fail
        logger.warning(
            "metrics_recording_failed",
            marketplace_type=marketplace_type,
            endpoint=endpoint,
            method=method,
            error=str(e),
            error_type=type(e).__name__,
            **correlation_context,
            exc_info=True,
        )

