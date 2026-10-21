"""
Virtualization Metrics

Prometheus metrics for virtualization operations monitoring and observability.
Tracks virtual dataset lifecycle, query execution performance, cache hit rates, and result sizes.
"""

from hub.apps.observability.otel_metrics import (
    _CounterWrapper,
    _HistogramWrapper,
    _UpDownCounterWrapper,
)

# ============================================================================
# Virtual Dataset Lifecycle Metrics
# ============================================================================

virtualization_dataset_created_total = _CounterWrapper(
    "virtualization_dataset_created_total",
    "Total number of virtual datasets created",
    unit="1",
    expected_labels=("tenant_id", "query_type", "status"),
)

virtualization_dataset_updated_total = _CounterWrapper(
    "virtualization_dataset_updated_total",
    "Total number of virtual datasets updated",
    unit="1",
    expected_labels=("tenant_id", "query_type"),
)

virtualization_dataset_deleted_total = _CounterWrapper(
    "virtualization_dataset_deleted_total",
    "Total number of virtual datasets deleted",
    unit="1",
    expected_labels=("tenant_id", "reason"),
)

virtualization_dataset_creation_duration_seconds = _HistogramWrapper(
    "virtualization_dataset_creation_duration_seconds",
    "Virtual dataset creation duration in seconds",
    unit="s",
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    expected_labels=("tenant_id", "query_type", "status"),
)


# ============================================================================
# Query Execution Metrics
# ============================================================================

virtualization_query_execution_duration_seconds = _HistogramWrapper(
    "virtualization_query_execution_duration_seconds",
    "Query execution duration in seconds",
    unit="s",
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
    expected_labels=("tenant_id", "query_type", "execution_mode", "status"),
)

virtualization_query_execution_started_total = _CounterWrapper(
    "virtualization_query_execution_started_total",
    "Total number of query executions started",
    unit="1",
    expected_labels=("tenant_id", "query_type", "execution_mode"),
)

virtualization_query_execution_completed_total = _CounterWrapper(
    "virtualization_query_execution_completed_total",
    "Total number of query executions completed",
    unit="1",
    expected_labels=("tenant_id", "query_type", "execution_mode", "status"),
)

virtualization_query_execution_failed_total = _CounterWrapper(
    "virtualization_query_execution_failed_total",
    "Total number of query executions failed",
    unit="1",
    expected_labels=("tenant_id", "query_type", "execution_mode", "error_type"),
)

virtualization_query_execution_cancelled_total = _CounterWrapper(
    "virtualization_query_execution_cancelled_total",
    "Total number of query executions cancelled",
    unit="1",
    expected_labels=("tenant_id", "query_type", "execution_mode", "reason"),
)

# Success rate is calculated from completed_total and failed_total
# Formula: (completed_total{status="COMPLETED"} / (completed_total + failed_total)) * 100


# ============================================================================
# Cache Metrics
# ============================================================================

virtualization_query_result_cache_hit_rate = _CounterWrapper(
    "virtualization_query_result_cache_hits_total",
    "Total number of cache hits for query results",
    unit="1",
    expected_labels=("tenant_id", "query_type"),
)

virtualization_query_result_cache_misses_total = _CounterWrapper(
    "virtualization_query_result_cache_misses_total",
    "Total number of cache misses for query results",
    unit="1",
    expected_labels=("tenant_id", "query_type"),
)

# Cache hit rate is calculated as: cache_hits_total / (cache_hits_total + cache_misses_total) * 100


# ============================================================================
# Result Size Metrics
# ============================================================================

virtualization_query_result_size_bytes = _HistogramWrapper(
    "virtualization_query_result_size_bytes",
    "Query result size in bytes",
    unit="By",
    buckets=(1024, 10240, 102400, 1048576, 10485760, 104857600, 1073741824),  # 1KB to 1GB
    expected_labels=("tenant_id", "query_type", "execution_mode"),
)

virtualization_query_result_rows_total = _HistogramWrapper(
    "virtualization_query_result_rows_total",
    "Number of rows returned by query execution",
    unit="1",
    buckets=(10, 100, 1000, 10000, 100000, 1000000, 10000000),
    expected_labels=("tenant_id", "query_type", "execution_mode"),
)


# ============================================================================
# Active Resource Metrics
# ============================================================================

virtualization_dataset_count = _UpDownCounterWrapper(
    "virtualization_dataset_count",
    "Current number of virtual datasets",
    unit="1",
    expected_labels=("tenant_id", "status", "query_type"),
)

virtualization_query_execution_active_count = _UpDownCounterWrapper(
    "virtualization_query_execution_active_count",
    "Current number of active query executions",
    unit="1",
    expected_labels=("tenant_id", "query_type", "execution_mode"),
)


# ============================================================================
# Helper Functions
# ============================================================================


def get_tenant_id(tenant_id: str | None) -> str:
    """
    Get tenant ID for metrics labels (use 'system' if None).

    Args:
        tenant_id: Tenant ID or None

    Returns:
        Tenant ID string or 'system'
    """
    return str(tenant_id) if tenant_id else "system"


def get_query_type(query_type: str | None) -> str:
    """
    Get query type for metrics labels (use 'unknown' if None).

    Args:
        query_type: Query type or None

    Returns:
        Query type string or 'unknown'
    """
    return str(query_type) if query_type else "unknown"


def get_execution_mode(execution_mode: str | None) -> str:
    """
    Get execution mode for metrics labels (use 'unknown' if None).

    Args:
        execution_mode: Execution mode or None

    Returns:
        Execution mode string or 'unknown'
    """
    return str(execution_mode) if execution_mode else "unknown"
