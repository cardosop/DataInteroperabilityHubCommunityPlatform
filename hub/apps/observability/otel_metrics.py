"""
Observability: OpenTelemetry Metrics

OpenTelemetry metrics implementation with Prometheus exporter for Django 6 compatibility.
Replaces prometheus-client and django-prometheus.

This module provides a complete OpenTelemetry-based metrics implementation that:
- Exports metrics in Prometheus format via the `/metrics` endpoint
- Maintains compatibility with the prometheus-client API (via wrapper classes)
- Supports Counter, Histogram, and Gauge (UpDownCounter) metric types
- Handles all existing metrics: HTTP, Job, DQ/Compliance, Database, Cache, File, Contract

Usage:
    from hub.apps.observability.otel_metrics import (
        http_requests_total,
        jobs_started_total,
        job_duration_seconds,
    )

    # Record metrics
    http_requests_total.labels(method='GET', route='/api/', status_class='2xx').inc()
    jobs_started_total.labels(job_type='DQ_RUN', tenant_id='123').inc()
    job_duration_seconds.labels(job_type='DQ_RUN', status='COMPLETED').observe(10.5)

Migration from prometheus-client:
    The API is compatible - existing code using prometheus-client patterns will work:
    - metric.labels(...).inc() for counters
    - metric.labels(...).observe(value) for histograms
    - metric.labels(...).set(value) for gauges

    All metric names and labels are preserved exactly.
"""
import os
from typing import Optional, Dict, Any
from django.conf import settings
from django.http import HttpResponse

# OpenTelemetry imports
try:
    from opentelemetry import metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.exporter.prometheus import PrometheusMetricReader, REGISTRY
    from opentelemetry.sdk.resources import Resource
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    REGISTRY = None
    CONTENT_TYPE_LATEST = 'text/plain; version=0.0.4'


# Global meter instance and metric reader
_meter: Optional[object] = None
# Use string annotation to avoid NameError if PrometheusMetricReader not available
_metric_reader: Optional['PrometheusMetricReader'] = None if not OPENTELEMETRY_AVAILABLE else None
_initialized = False


def setup_opentelemetry_metrics() -> Optional[object]:
    """
    Set up OpenTelemetry metrics with Prometheus exporter.

    Returns:
        Meter instance or None if not enabled/available
    """
    global _meter, _metric_reader, _initialized

    if not OPENTELEMETRY_AVAILABLE:
        return None

    # Check if Django settings are configured
    try:
        from django.conf import settings
        if not getattr(settings, 'OPENTELEMETRY_METRICS_ENABLED', True):
            return None
    except Exception:
        # Django not configured yet, will initialize later
        return None

    # Check if already initialized
    if _initialized and _meter is not None:
        return _meter

    try:
        # Create resource with service name
        resource = Resource.create({
            "service.name": "hub-api",
            "service.version": getattr(settings, 'APP_VERSION', '1.0.0'),
        })

        # Create Prometheus metric reader (uses prometheus_client REGISTRY)
        _metric_reader = PrometheusMetricReader(disable_target_info=False)

        # Create meter provider
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[_metric_reader]
        )

        # Set global meter provider
        metrics.set_meter_provider(meter_provider)

        # Get meter instance
        _meter = metrics.get_meter(__name__)
        _initialized = True

        return _meter

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to setup OpenTelemetry metrics: {e}", exc_info=True)
        return None


def get_meter() -> Optional[object]:
    """
    Get OpenTelemetry meter instance.

    Returns:
        Meter instance or None
    """
    global _meter
    if _meter is None:
        _meter = setup_opentelemetry_metrics()
    return _meter


# Initialize metrics on module import (lazy - will initialize when Django is ready)
# Don't call setup_opentelemetry_metrics() here as Django settings may not be configured yet


# Helper function (keep existing)
def get_status_class(status_code: int) -> str:
    """
    Get status class from HTTP status code.

    Args:
        status_code: HTTP status code

    Returns:
        Status class string (2xx, 4xx, 5xx)
    """
    if 200 <= status_code < 300:
        return '2xx'
    elif 400 <= status_code < 500:
        return '4xx'
    elif 500 <= status_code < 600:
        return '5xx'
    else:
        return 'other'


# ============================================================================
# Metric Wrapper Classes (handle None metrics gracefully)
# ============================================================================

class _ValueProxy:
    """Proxy object for _value.get() compatibility"""
    def __init__(self):
        self._count = 0.0

    def get(self):
        """Get current value (always returns 0 for OpenTelemetry - values not directly accessible)"""
        return self._count

    def set(self, value):
        """Set value (for testing)"""
        self._count = value


class _LabeledMetric:
    """Wrapper for labeled metric operations (compatibility with prometheus-client API)"""
    def __init__(self, metric, attributes: Dict[str, str]):
        self.metric = metric
        self.attributes = attributes or {}
        self._value = _ValueProxy()  # Compatibility property

    def inc(self, amount: float = 1):
        """Increment metric"""
        if hasattr(self.metric, 'add'):
            self.metric.add(amount, attributes=self.attributes)
            self._value._count += amount
        elif hasattr(self.metric, 'inc'):
            self.metric.inc(amount, attributes=self.attributes)
            self._value._count += amount

    def dec(self, amount: float = 1):
        """Decrement metric"""
        if hasattr(self.metric, 'add'):
            self.metric.add(-amount, attributes=self.attributes)
            self._value._count -= amount
        elif hasattr(self.metric, 'dec'):
            self.metric.dec(amount, attributes=self.attributes)
            self._value._count -= amount

    def observe(self, value: float):
        """Observe a value (for histograms)"""
        if hasattr(self.metric, 'record'):
            self.metric.record(value, attributes=self.attributes)
        elif hasattr(self.metric, 'observe'):
            self.metric.observe(value, attributes=self.attributes)

    def set(self, value: float):
        """Set metric value (for gauges)"""
        if hasattr(self.metric, 'set'):
            self.metric.set(value, attributes=self.attributes)
            self._value._count = value


class _CounterWrapper:
    """Wrapper for Counter metrics that handles None gracefully"""
    def __init__(self, name: str, description: str, unit: str = '1', expected_labels: tuple = None):
        self.name = name
        self.description = description
        self.unit = unit
        self._counter = None
        self._expected_labels = expected_labels or ()

    @property
    def _labelnames(self):
        """Compatibility property for prometheus-client API"""
        return self._expected_labels

    @property
    def _value(self):
        """Compatibility property for prometheus-client API (_value.get())"""
        # Return a proxy that tracks value for unlabeled metrics
        if not hasattr(self, '_value_proxy'):
            self._value_proxy = _ValueProxy()
        return self._value_proxy

    def _get_counter(self):
        """Get or create the counter metric"""
        if self._counter is None:
            meter = get_meter()
            if meter is not None:
                self._counter = meter.create_counter(
                    name=self.name,
                    description=self.description,
                    unit=self.unit
                )
        return self._counter

    def add(self, amount: float, attributes: Dict[str, str] = None):
        """Add to counter"""
        counter = self._get_counter()
        if counter is not None:
            counter.add(amount, attributes=attributes or {})

    def inc(self, attributes: Dict[str, str] = None):
        """Increment counter by 1"""
        self.add(1, attributes=attributes)

    def labels(self, **kwargs) -> _LabeledMetric:
        """Create a labeled metric (compatibility with prometheus-client API)"""
        return _LabeledMetric(self, kwargs)


class _HistogramWrapper:
    """Wrapper for Histogram metrics that handles None gracefully"""
    def __init__(self, name: str, description: str, unit: str, buckets: tuple, expected_labels: tuple = None):
        self.name = name
        self.description = description
        self.unit = unit
        self.buckets = buckets
        self._histogram = None
        self._expected_labels = expected_labels or ()

    @property
    def _labelnames(self):
        """Compatibility property for prometheus-client API"""
        return self._expected_labels

    @property
    def _value(self):
        """Compatibility property for prometheus-client API (_value.get())"""
        # Return a proxy that tracks value for unlabeled metrics
        if not hasattr(self, '_value_proxy'):
            self._value_proxy = _ValueProxy()
        return self._value_proxy

    def _get_histogram(self):
        """Get or create the histogram metric"""
        if self._histogram is None:
            meter = get_meter()
            if meter is not None:
                self._histogram = meter.create_histogram(
                    name=self.name,
                    description=self.description,
                    unit=self.unit,
                    explicit_bucket_boundaries_advisory=list(self.buckets)
                )
        return self._histogram

    def record(self, amount: float, attributes: Dict[str, str] = None):
        """Record a value"""
        histogram = self._get_histogram()
        if histogram is not None:
            histogram.record(amount, attributes=attributes or {})

    def observe(self, amount: float, attributes: Dict[str, str] = None):
        """Alias for record (for compatibility with prometheus-client API)"""
        self.record(amount, attributes=attributes)

    def labels(self, **kwargs) -> _LabeledMetric:
        """Create a labeled metric (compatibility with prometheus-client API)"""
        return _LabeledMetric(self, kwargs)


class _UpDownCounterWrapper:
    """Wrapper for UpDownCounter metrics that handles None gracefully"""
    def __init__(self, name: str, description: str, unit: str = '1', expected_labels: tuple = None):
        self.name = name
        self.description = description
        self.unit = unit
        self._counter = None
        self._current_values: Dict[str, float] = {}  # Track current values by attribute key
        self._expected_labels = expected_labels or ()

    @property
    def _labelnames(self):
        """Compatibility property for prometheus-client API"""
        return self._expected_labels

    @property
    def _value(self):
        """Compatibility property for prometheus-client API (_value.get())"""
        # Return a proxy that tracks value for unlabeled metrics
        if not hasattr(self, '_value_proxy'):
            self._value_proxy = _ValueProxy()
        return self._value_proxy

    def _get_counter(self):
        """Get or create the updown counter metric"""
        if self._counter is None:
            meter = get_meter()
            if meter is not None:
                self._counter = meter.create_up_down_counter(
                    name=self.name,
                    description=self.description,
                    unit=self.unit
                )
        return self._counter

    def _get_key(self, attributes: Dict[str, str] = None) -> str:
        """Get a key for the attributes dict"""
        if attributes is None:
            return ''
        return ','.join(f"{k}={v}" for k, v in sorted(attributes.items()))

    def add(self, amount: float, attributes: Dict[str, str] = None):
        """Add to counter"""
        counter = self._get_counter()
        if counter is not None:
            counter.add(amount, attributes=attributes or {})
            # Track current value
            key = self._get_key(attributes)
            self._current_values[key] = self._current_values.get(key, 0) + amount

    def set(self, value: float, attributes: Dict[str, str] = None):
        """Set counter to a specific value (resets to 0 first, then adds value)"""
        key = self._get_key(attributes)
        current = self._current_values.get(key, 0)
        # Reset to 0 by subtracting current value
        if current != 0:
            self.add(-current, attributes=attributes)
        # Set to new value by adding it
        if value != 0:
            self.add(value, attributes=attributes)
        # Update value proxy for unlabeled metrics (when no attributes)
        if attributes is None or len(attributes) == 0:
            if not hasattr(self, '_value_proxy'):
                self._value_proxy = _ValueProxy()
            self._value_proxy.set(value)

    def inc(self, amount: float = 1, attributes: Dict[str, str] = None):
        """Increment counter"""
        self.add(amount, attributes=attributes)

    def dec(self, amount: float = 1, attributes: Dict[str, str] = None):
        """Decrement counter"""
        self.add(-amount, attributes=attributes)

    def labels(self, **kwargs) -> _LabeledMetric:
        """Create a labeled metric (compatibility with prometheus-client API)"""
        return _LabeledMetric(self, kwargs)


# ============================================================================
# Counter Metrics
# ============================================================================


# HTTP Request Metrics
http_requests_total = _CounterWrapper(
    'http_requests_total',
    'Total number of HTTP requests',
    unit='1',
    expected_labels=('method', 'route', 'status_class')
)

http_errors_total = _CounterWrapper(
    'http_errors_total',
    'Total number of HTTP errors',
    unit='1',
    expected_labels=('method', 'route', 'status_code')
)

# Job Metrics
jobs_started_total = _CounterWrapper(
    'jobs_started_total',
    'Total number of jobs started',
    unit='1',
    expected_labels=('job_type', 'tenant_id')
)

jobs_completed_total = _CounterWrapper(
    'jobs_completed_total',
    'Total number of jobs completed',
    unit='1',
    expected_labels=('job_type', 'status', 'tenant_id')
)

jobs_failed_total = _CounterWrapper(
    'jobs_failed_total',
    'Total number of jobs failed',
    unit='1',
    expected_labels=('job_type', 'error_code', 'tenant_id')
)

# DQ & Compliance Metrics
dq_runs_total = _CounterWrapper(
    'dq_runs_total',
    'Total number of DQ runs',
    unit='1',
    expected_labels=('status', 'engine', 'tenant_id')
)

compliance_runs_total = _CounterWrapper(
    'compliance_runs_total',
    'Total number of compliance runs',
    unit='1',
    expected_labels=('status', 'risk_level', 'tenant_id')
)

# Cache Metrics
cache_hits_total = _CounterWrapper(
    'cache_hits_total',
    'Total number of cache hits',
    unit='1',
    expected_labels=('cache_key_prefix',)
)

cache_misses_total = _CounterWrapper(
    'cache_misses_total',
    'Total number of cache misses',
    unit='1',
    expected_labels=('cache_key_prefix',)
)

# File Storage Metrics
file_uploads_total = _CounterWrapper(
    'file_uploads_total',
    'Total number of file uploads',
    unit='1',
    expected_labels=('status', 'file_type', 'tenant_id')
)

# Contract Metrics
contract_validations_total = _CounterWrapper(
    'contract_validations_total',
    'Total number of contract validations',
    unit='1',
    expected_labels=('status', 'spec_type', 'tenant_id')
)

contract_migrations_total = _CounterWrapper(
    'contract_migrations_total',
    'Total number of contract migrations',
    unit='1',
    expected_labels=('source_version', 'target_version', 'strategy', 'status', 'tenant_id')
)

# Normalization Coverage Metrics (Phase 15)
normalization_coverage_by_object = _HistogramWrapper(
    'normalization_coverage_by_object',
    'Normalization coverage percentage by object type',
    unit='1',
    buckets=(0.0, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 1.0),
    expected_labels=('object_type', 'tenant_id')
)

contract_json_size_bytes = _HistogramWrapper(
    'contract_json_size_bytes',
    'Size of hub_contract_json in bytes',
    unit='By',
    buckets=(1024, 10240, 102400, 1048576, 10485760, 104857600),
    expected_labels=('tenant_id',)
)

contract_missing_objects_total = _CounterWrapper(
    'contract_missing_objects_total',
    'Total number of contracts with missing objects',
    unit='1',
    expected_labels=('object_type', 'tenant_id')
)

contract_broken_lineage_links_total = _CounterWrapper(
    'contract_broken_lineage_links_total',
    'Total number of broken lineage links detected',
    unit='1',
    expected_labels=('link_type', 'tenant_id')
)

# ODPS Metrics (Task 6.2.1)
odps_ingestion_total = _CounterWrapper(
    'odps_ingestion_total',
    'Total number of ODPS ingestion operations (marketplace)',
    unit='1',
    expected_labels=('source', 'tenant_id')
)

odps_normalization_total = _CounterWrapper(
    'odps_normalization_total',
    'Total number of ODPS normalization operations',
    unit='1',
    expected_labels=('status', 'version', 'tenant_id')
)

odps_ref_resolution_total = _CounterWrapper(
    'odps_ref_resolution_total',
    'Total number of $ref resolution operations',
    unit='1',
    expected_labels=('ref_type', 'status', 'tenant_id')
)

odps_ref_resolution_failures_total = _CounterWrapper(
    'odps_ref_resolution_failures_total',
    'Total number of $ref resolution failures',
    unit='1',
    expected_labels=('ref_type', 'error_type', 'tenant_id')
)

odps_external_fetch_failures_total = _CounterWrapper(
    'odps_external_fetch_failures_total',
    'Total number of external $ref fetch failures',
    unit='1',
    expected_labels=('error_type', 'tenant_id')
)

odps_version_distribution_total = _CounterWrapper(
    'odps_version_distribution_total',
    'Total number of ODPS documents by version',
    unit='1',
    expected_labels=('version', 'tenant_id')
)

odps_rate_limit_violations_total = _CounterWrapper(
    'odps_rate_limit_violations_total',
    'Total number of ODPS $ref rate limit violations',
    unit='1',
    expected_labels=('level', 'tenant_id', 'user_id')
)

odps_ref_cache_hits_total = _CounterWrapper(
    'odps_ref_cache_hits_total',
    'Total number of external $ref cache hits',
    unit='1',
    expected_labels=('tenant_id',)
)

odps_ref_cache_misses_total = _CounterWrapper(
    'odps_ref_cache_misses_total',
    'Total number of external $ref cache misses',
    unit='1',
    expected_labels=('tenant_id',)
)

# ODPS Semantic Mapping Metrics (Task 6.6.3)
odps_semantic_mapping_duration_seconds = _HistogramWrapper(
    'odps_semantic_mapping_duration_seconds',
    'ODPS semantic mapping duration in seconds',
    unit='s',
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    expected_labels=('status', 'tenant_id')
)

odps_semantic_mapping_total = _CounterWrapper(
    'odps_semantic_mapping_total',
    'Total number of ODPS semantic mapping operations',
    unit='1',
    expected_labels=('status', 'tenant_id')
)

odps_semantic_mapping_success_rate = _UpDownCounterWrapper(
    'odps_semantic_mapping_success_rate',
    'ODPS semantic mapping success rate (0-1)',
    unit='1',
    expected_labels=('tenant_id',)
)

# ODCS Metrics (Task 6.2.2 - explicit backward compatibility)
odcs_ingestion_total = _CounterWrapper(
    'odcs_ingestion_total',
    'Total number of ODCS ingestion operations (technical)',
    unit='1',
    expected_labels=('source', 'tenant_id')
)

odcs_normalization_total = _CounterWrapper(
    'odcs_normalization_total',
    'Total number of ODCS normalization operations (all versions)',
    unit='1',
    expected_labels=('status', 'version', 'tenant_id')
)

odcs_version_distribution_total = _CounterWrapper(
    'odcs_version_distribution_total',
    'Total number of ODCS documents by version (3.0.2, 3.0.1, 3.0.0, 3.0.0-preview, 2.2.2)',
    unit='1',
    expected_labels=('version', 'tenant_id')
)

odcs_normalization_regression_total = _CounterWrapper(
    'odcs_normalization_regression_total',
    'Total number of ODCS normalization regressions detected',
    unit='1',
    expected_labels=('version', 'regression_type', 'tenant_id')
)


# ============================================================================
# Histogram Metrics
# ============================================================================

# HTTP Request Duration
http_request_duration_seconds = _HistogramWrapper(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    unit='s',
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    expected_labels=('method', 'route', 'status_class')
)

# Job Duration
job_duration_seconds = _HistogramWrapper(
    'job_duration_seconds',
    'Job duration in seconds',
    unit='s',
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0),
    expected_labels=('job_type', 'status')
)

# Database Query Duration
db_query_duration_seconds = _HistogramWrapper(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    unit='s',
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    expected_labels=('operation',)
)

# File Upload Size
file_upload_size_bytes = _HistogramWrapper(
    'file_upload_size_bytes',
    'File upload size in bytes',
    unit='By',
    buckets=(1024, 10240, 102400, 1048576, 10485760, 104857600, 1073741824),
    expected_labels=('file_type',)
)

# ODPS $ref Resolution Duration (Task 6.2.1)
# Buckets optimized for p50, p95, p99 percentiles
odps_ref_resolution_duration_seconds = _HistogramWrapper(
    'odps_ref_resolution_duration_seconds',
    'Duration of $ref resolution operations in seconds',
    unit='s',
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    expected_labels=('ref_type', 'tenant_id')
)

# ODPS Export Duration (Task 6.6.1)
# Buckets optimized for export operations (typically faster than ref resolution)
odps_export_duration_seconds = _HistogramWrapper(
    'odps_export_duration_seconds',
    'Duration of ODPS export operations in seconds',
    unit='s',
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    expected_labels=('format', 'size_category', 'tenant_id')
)

# ODPS Export Size (Task 6.6.1)
# Buckets optimized for export sizes (bytes)
odps_export_size_bytes = _HistogramWrapper(
    'odps_export_size_bytes',
    'Size of ODPS export output in bytes',
    unit='By',
    buckets=(1024, 10240, 102400, 1048576, 10485760, 104857600, 1073741824),
    expected_labels=('format', 'tenant_id')
)

# ODPS Export Total (Task 6.6.4)
# Counter to track export attempts with status for failure rate alerts
odps_export_total = _CounterWrapper(
    'odps_export_total',
    'Total number of ODPS export operations',
    unit='1',
    expected_labels=('status', 'format', 'tenant_id')
)

# ODPS Linking Metrics (Task 6.6.2)
odps_linking_total = _CounterWrapper(
    'odps_linking_total',
    'Total number of ODPS linking operations',
    unit='1',
    expected_labels=('direction', 'tenant_id')
)

odps_linking_success_total = _CounterWrapper(
    'odps_linking_success_total',
    'Total number of successful ODPS linking operations',
    unit='1',
    expected_labels=('direction', 'tenant_id')
)

odps_linking_failures_total = _CounterWrapper(
    'odps_linking_failures_total',
    'Total number of failed ODPS linking operations',
    unit='1',
    expected_labels=('direction', 'error_code', 'tenant_id')
)

odps_linking_duration_seconds = _HistogramWrapper(
    'odps_linking_duration_seconds',
    'Duration of ODPS linking operations in seconds',
    unit='s',
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    expected_labels=('direction', 'tenant_id')
)


# ============================================================================
# Gauge Metrics (using UpDownCounter for settable values)
# ============================================================================

# Database Metrics
db_connections_active = _UpDownCounterWrapper(
    'db_connections_active',
    'Number of active database connections',
    unit='1',
    expected_labels=()
)

# Job Queue Metrics
job_queue_length = _UpDownCounterWrapper(
    'job_queue_length',
    'Current number of jobs in queue',
    unit='1',
    expected_labels=('job_type', 'queue_name')
)

# Per-tenant job count metrics
tenant_running_jobs = _UpDownCounterWrapper(
    'tenant_running_jobs',
    'Current number of running jobs per tenant',
    unit='1',
    expected_labels=('tenant_id',)
)

tenant_queued_jobs = _UpDownCounterWrapper(
    'tenant_queued_jobs',
    'Current number of queued jobs per tenant',
    unit='1',
    expected_labels=('tenant_id',)
)

# Asset Status Metrics
asset_dq_status = _UpDownCounterWrapper(
    'asset_dq_status_count',
    'Number of assets by DQ status',
    unit='1',
    expected_labels=('status', 'tenant_id')
)

asset_compliance_status = _UpDownCounterWrapper(
    'asset_compliance_status_count',
    'Number of assets by compliance status',
    unit='1',
    expected_labels=('status', 'tenant_id')
)

# Scheduled Ingestion Metrics
scheduled_ingestions_total = _CounterWrapper(
    'scheduled_ingestions_total',
    'Total number of scheduled ingestions',
    unit='1',
    expected_labels=('status', 'source_type', 'tenant_id')
)

scheduled_ingestion_runs_total = _CounterWrapper(
    'scheduled_ingestion_runs_total',
    'Total number of scheduled ingestion runs',
    unit='1',
    expected_labels=('status', 'scheduled_ingestion_id', 'tenant_id')
)

scheduled_ingestion_files_processed_total = _CounterWrapper(
    'scheduled_ingestion_files_processed_total',
    'Total number of files processed by scheduled ingestions',
    unit='1',
    expected_labels=('scheduled_ingestion_id', 'tenant_id')
)

scheduled_ingestion_files_failed_total = _CounterWrapper(
    'scheduled_ingestion_files_failed_total',
    'Total number of files failed in scheduled ingestions',
    unit='1',
    expected_labels=('scheduled_ingestion_id', 'tenant_id')
)

scheduled_ingestion_datasets_created_total = _CounterWrapper(
    'scheduled_ingestion_datasets_created_total',
    'Total number of datasets created by scheduled ingestions',
    unit='1',
    expected_labels=('scheduled_ingestion_id', 'tenant_id')
)

scheduled_ingestion_duration_seconds = _HistogramWrapper(
    'scheduled_ingestion_duration_seconds',
    'Duration of scheduled ingestion runs in seconds',
    unit='s',
    expected_labels=('scheduled_ingestion_id', 'status', 'tenant_id'),
    buckets=(10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0)
)

scheduled_ingestion_files_per_run = _HistogramWrapper(
    'scheduled_ingestion_files_per_run',
    'Number of files processed per ingestion run',
    unit='1',
    expected_labels=('scheduled_ingestion_id', 'tenant_id'),
    buckets=(1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0)
)

scheduled_ingestion_active_count = _UpDownCounterWrapper(
    'scheduled_ingestion_active_count',
    'Current number of active scheduled ingestions',
    unit='1',
    expected_labels=('tenant_id',)
)

# Service Layer Metrics
service_operations_total = _CounterWrapper(
    'service_operations_total',
    'Total number of service operations',
    unit='1',
    expected_labels=('service', 'operation', 'tenant_id')
)

service_operation_duration_seconds = _HistogramWrapper(
    'service_operation_duration_seconds',
    'Duration of service operations in seconds',
    unit='s',
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0),
    expected_labels=('service', 'operation', 'tenant_id')
)

service_operation_errors_total = _CounterWrapper(
    'service_operation_errors_total',
    'Total number of service operation errors',
    unit='1',
    expected_labels=('service', 'operation', 'error_code', 'tenant_id')
)

# Cross-Service Communication Metrics
service_calls_total = _CounterWrapper(
    'service_calls_total',
    'Total number of cross-service calls',
    unit='1',
    expected_labels=('source_service', 'target_service', 'method', 'status', 'tenant_id')
)

service_call_duration_seconds = _HistogramWrapper(
    'service_call_duration_seconds',
    'Duration of cross-service calls in seconds',
    unit='s',
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0),
    expected_labels=('source_service', 'target_service', 'method', 'status', 'tenant_id')
)

service_call_errors_total = _CounterWrapper(
    'service_call_errors_total',
    'Total number of cross-service call errors',
    unit='1',
    expected_labels=('source_service', 'target_service', 'method', 'error_type', 'tenant_id')
)

service_call_retries_total = _CounterWrapper(
    'service_call_retries_total',
    'Total number of cross-service call retries',
    unit='1',
    expected_labels=('source_service', 'target_service', 'method', 'retry_count', 'tenant_id')
)

service_call_timeouts_total = _CounterWrapper(
    'service_call_timeouts_total',
    'Total number of cross-service call timeouts',
    unit='1',
    expected_labels=('source_service', 'target_service', 'method', 'tenant_id')
)

# Service Health Metrics
service_health_checks_total = _CounterWrapper(
    'service_health_checks_total',
    'Total number of service health checks',
    unit='1',
    expected_labels=('service', 'status', 'check_type')
)

service_health_check_duration_seconds = _HistogramWrapper(
    'service_health_check_duration_seconds',
    'Duration of service health checks in seconds',
    unit='s',
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
    expected_labels=('service', 'check_type')
)

service_health_status = _UpDownCounterWrapper(
    'service_health_status',
    'Current health status of services (1=healthy, 0=unhealthy)',
    unit='1',
    expected_labels=('service',)
)


# ============================================================================
# Metrics View Function
# ============================================================================

def metrics_view(request):
    """
    Prometheus metrics endpoint using OpenTelemetry Prometheus exporter.

    Returns:
        HTTP response with Prometheus metrics in text format
    """
    if not OPENTELEMETRY_AVAILABLE or REGISTRY is None:
        return HttpResponse("Metrics not available", status=503, content_type='text/plain')

    try:
        # Generate Prometheus format from the registry
        metrics_data = generate_latest(REGISTRY)
        return HttpResponse(metrics_data, content_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to generate metrics: {e}", exc_info=True)
        return HttpResponse(f"Error generating metrics: {str(e)}", status=500, content_type='text/plain')

