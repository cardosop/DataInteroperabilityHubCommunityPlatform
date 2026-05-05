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
from typing import Any, Dict, Optional

from django.conf import settings
from django.http import HttpResponse

# OpenTelemetry imports
try:
    from opentelemetry import metrics
    from opentelemetry.exporter.prometheus import REGISTRY, PrometheusMetricReader
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    REGISTRY = None
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"


# Global meter instance and metric reader
_meter: Optional[object] = None
# Use string annotation to avoid NameError if PrometheusMetricReader not available
_metric_reader: Optional["PrometheusMetricReader"] = None if not OPENTELEMETRY_AVAILABLE else None
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

        if not getattr(settings, "OPENTELEMETRY_METRICS_ENABLED", True):
            return None
    except Exception:
        # Django not configured yet, will initialize later
        return None

    # Check if already initialized
    if _initialized and _meter is not None:
        return _meter

    try:
        # Create resource with service name
        resource = Resource.create(
            {
                "service.name": "hub-api",
                "service.version": getattr(settings, "APP_VERSION", "1.0.0"),
            }
        )

        # Create Prometheus metric reader (uses prometheus_client REGISTRY)
        _metric_reader = PrometheusMetricReader(disable_target_info=False)

        # Verify REGISTRY is available after creating PrometheusMetricReader
        # REGISTRY is set by PrometheusMetricReader when it's instantiated
        if REGISTRY is None:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                "REGISTRY is None after creating PrometheusMetricReader. This may indicate an issue with opentelemetry-exporter-prometheus."
            )

        # Create meter provider
        meter_provider = MeterProvider(resource=resource, metric_readers=[_metric_reader])

        # Set global meter provider
        metrics.set_meter_provider(meter_provider)

        # Get meter instance
        _meter = metrics.get_meter(__name__)
        _initialized = True

        return _meter

    except (ImportError, AttributeError, ValueError) as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            "Failed to setup OpenTelemetry metrics (expected if not configured)",
            extra={"error_type": type(e).__name__},
        )
        return None
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.exception(
            "Unexpected error setting up OpenTelemetry metrics",
            extra={"error_type": type(e).__name__},
        )
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
        return "2xx"
    elif 400 <= status_code < 500:
        return "4xx"
    elif 500 <= status_code < 600:
        return "5xx"
    else:
        return "other"


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


def _labeled_metric_cache_key(kwargs: Dict[str, str]) -> frozenset:
    """Stable cache key for labeled metric instances (same labels -> same _LabeledMetric)."""
    return frozenset((k, str(v)) for k, v in sorted(kwargs.items()))


def _get_or_create_labeled(wrapper: Any, kwargs: Dict[str, Any]) -> Any:
    """
    Return a single _LabeledMetric per wrapper+labels so .inc() accumulates on ._value
    and get_contract_cache_metrics() reads non-zero hit counts.
    """
    cache = getattr(wrapper, "_labeled_metrics_cache", None)
    if cache is None:
        cache = {}
        setattr(wrapper, "_labeled_metrics_cache", cache)
    key = _labeled_metric_cache_key(kwargs)
    if key not in cache:
        cache[key] = _LabeledMetric(wrapper, dict(kwargs))
    return cache[key]


class _LabeledMetric:
    """Wrapper for labeled metric operations (compatibility with prometheus-client API)"""

    def __init__(self, metric, attributes: Dict[str, str]):
        self.metric = metric
        self.attributes = attributes or {}
        self._value = _ValueProxy()  # Compatibility property

    def inc(self, amount: float = 1):
        """Increment metric"""
        if hasattr(self.metric, "add"):
            self.metric.add(amount, attributes=self.attributes)
            self._value._count += amount
        elif hasattr(self.metric, "inc"):
            self.metric.inc(amount, attributes=self.attributes)
            self._value._count += amount

    def dec(self, amount: float = 1):
        """Decrement metric"""
        if hasattr(self.metric, "add"):
            self.metric.add(-amount, attributes=self.attributes)
            self._value._count -= amount
        elif hasattr(self.metric, "dec"):
            self.metric.dec(amount, attributes=self.attributes)
            self._value._count -= amount

    def observe(self, value: float):
        """Observe a value (for histograms)"""
        if hasattr(self.metric, "record"):
            self.metric.record(value, attributes=self.attributes)
            self._value._count += 1
        elif hasattr(self.metric, "observe"):
            self.metric.observe(value, attributes=self.attributes)
            self._value._count += 1

    def set(self, value: float):
        """Set metric value (for gauges)"""
        if hasattr(self.metric, "set"):
            self.metric.set(value, attributes=self.attributes)
            self._value._count = value


class _CounterWrapper:
    """Wrapper for Counter metrics that handles None gracefully"""

    def __init__(self, name: str, description: str, unit: str = "1", expected_labels: tuple = None):
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
        if not hasattr(self, "_value_proxy"):
            self._value_proxy = _ValueProxy()
        return self._value_proxy

    def _get_counter(self):
        """Get or create the counter metric"""
        if self._counter is None:
            meter = get_meter()
            if meter is not None:
                self._counter = meter.create_counter(
                    name=self.name, description=self.description, unit=self.unit
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
        return _get_or_create_labeled(self, kwargs)


class _HistogramWrapper:
    """Wrapper for Histogram metrics that handles None gracefully"""

    def __init__(
        self, name: str, description: str, unit: str, buckets: tuple, expected_labels: tuple = None
    ):
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
        if not hasattr(self, "_value_proxy"):
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
                    explicit_bucket_boundaries_advisory=list(self.buckets),
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
        return _get_or_create_labeled(self, kwargs)


class _UpDownCounterWrapper:
    """Wrapper for UpDownCounter metrics that handles None gracefully"""

    def __init__(self, name: str, description: str, unit: str = "1", expected_labels: tuple = None):
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
        if not hasattr(self, "_value_proxy"):
            self._value_proxy = _ValueProxy()
        return self._value_proxy

    def _get_counter(self):
        """Get or create the updown counter metric"""
        if self._counter is None:
            meter = get_meter()
            if meter is not None:
                self._counter = meter.create_up_down_counter(
                    name=self.name, description=self.description, unit=self.unit
                )
        return self._counter

    def _get_key(self, attributes: Dict[str, str] = None) -> str:
        """Get a key for the attributes dict"""
        if attributes is None:
            return ""
        return ",".join(f"{k}={v}" for k, v in sorted(attributes.items()))

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
            if not hasattr(self, "_value_proxy"):
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
        return _get_or_create_labeled(self, kwargs)


# ============================================================================
# Counter Metrics
# ============================================================================


# HTTP Request Metrics
http_requests_total = _CounterWrapper(
    "http_requests_total",
    "Total number of HTTP requests",
    unit="1",
    expected_labels=("method", "route", "status_class"),
)

http_errors_total = _CounterWrapper(
    "http_errors_total",
    "Total number of HTTP errors",
    unit="1",
    expected_labels=("method", "route", "status_code"),
)

# Job Metrics
jobs_started_total = _CounterWrapper(
    "jobs_started_total",
    "Total number of jobs started",
    unit="1",
    expected_labels=("job_type", "tenant_id"),
)

jobs_completed_total = _CounterWrapper(
    "jobs_completed_total",
    "Total number of jobs completed",
    unit="1",
    expected_labels=("job_type", "status", "tenant_id"),
)

jobs_failed_total = _CounterWrapper(
    "jobs_failed_total",
    "Total number of jobs failed",
    unit="1",
    expected_labels=("job_type", "error_code", "tenant_id"),
)

# DQ & Compliance Metrics
dq_runs_total = _CounterWrapper(
    "dq_runs_total",
    "Total number of DQ runs",
    unit="1",
    expected_labels=("status", "engine", "tenant_id"),
)

compliance_runs_total = _CounterWrapper(
    "compliance_runs_total",
    "Total number of compliance runs",
    unit="1",
    expected_labels=("status", "risk_level", "tenant_id"),
)

# Cache Metrics
cache_hits_total = _CounterWrapper(
    "cache_hits_total",
    "Total number of cache hits",
    unit="1",
    expected_labels=("cache_key_prefix",),
)

cache_misses_total = _CounterWrapper(
    "cache_misses_total",
    "Total number of cache misses",
    unit="1",
    expected_labels=("cache_key_prefix",),
)

# File Storage Metrics
file_uploads_total = _CounterWrapper(
    "file_uploads_total",
    "Total number of file uploads",
    unit="1",
    expected_labels=("status", "file_type", "tenant_id"),
)

# Contract Metrics
contract_validations_total = _CounterWrapper(
    "contract_validations_total",
    "Total number of contract validations",
    unit="1",
    expected_labels=("status", "spec_type", "tenant_id"),
)

contract_migrations_total = _CounterWrapper(
    "contract_migrations_total",
    "Total number of contract migrations",
    unit="1",
    expected_labels=("source_version", "target_version", "strategy", "status", "tenant_id"),
)

# Normalization Coverage Metrics (Phase 15)
normalization_coverage_by_object = _HistogramWrapper(
    "normalization_coverage_by_object",
    "Normalization coverage percentage by object type",
    unit="1",
    buckets=(0.0, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 1.0),
    expected_labels=("object_type", "tenant_id"),
)

contract_json_size_bytes = _HistogramWrapper(
    "contract_json_size_bytes",
    "Size of hub_contract_json in bytes",
    unit="By",
    buckets=(1024, 10240, 102400, 1048576, 10485760, 104857600),
    expected_labels=("tenant_id",),
)

contract_missing_objects_total = _CounterWrapper(
    "contract_missing_objects_total",
    "Total number of contracts with missing objects",
    unit="1",
    expected_labels=("object_type", "tenant_id"),
)

contract_broken_lineage_links_total = _CounterWrapper(
    "contract_broken_lineage_links_total",
    "Total number of broken lineage links detected",
    unit="1",
    expected_labels=("link_type", "tenant_id"),
)

# Phase 227 Wave 1 (227.L7.1) — structureless / floor-violation metrics.
#
# Emitted from ``hub.apps.contracts.structural_floor.enforce_structural_floor``
# on every Layer-3 raise so the Grafana dashboard can break down rejection
# rate by code, subcode, and spec_type — the three dimensions ops care
# about during the Wave 3 → Wave 5 rollout.
contract_validation_failed_total = _CounterWrapper(
    "contract_validation_failed_total",
    "Total Layer-3 validation failures (Phase 227 structural floor + "
    "schema validators). Labels: error code, per-cause subcode, "
    "originating spec_type.",
    unit="1",
    expected_labels=("code", "subcode", "spec_type"),
)

contract_structureless_total = _CounterWrapper(
    "contract_structureless_total",
    "Total contracts whose normalised payload is structureless. "
    "``source`` distinguishes WHERE the structureless payload was "
    "observed: ``creation`` (POST), ``update`` (PATCH), ``migration`` "
    "(--apply self-heal pass), ``deprecation_warning`` (legacy / "
    "pre-Wave-1 grace path — kept for backward-compat label space "
    "even though the directive ungated the floor).",
    unit="1",
    expected_labels=("spec_type", "source"),
)

contract_normalization_models_count = _HistogramWrapper(
    "contract_normalization_models_count",
    "Number of ``models[]`` entries produced by a successful "
    "normalisation. Used to track the post-fix model-population "
    "distribution per spec_type.",
    unit="1",
    buckets=(0, 1, 2, 5, 10, 25, 50, 100, 250, 500, 1000),
    expected_labels=("spec_type",),
)

contract_normalization_fields_total_count = _HistogramWrapper(
    "contract_normalization_fields_total_count",
    "Total field count summed across all ``models[*].fields[]`` and "
    "``schema.fields[]`` produced by a successful normalisation.",
    unit="1",
    buckets=(0, 1, 5, 10, 50, 100, 500, 1000, 5000, 10000, 50000),
    expected_labels=("spec_type",),
)

contracts_renormalize_batch_duration_seconds = _HistogramWrapper(
    "contracts_renormalize_batch_duration_seconds",
    "Wall-clock duration of one ``renormalize_contracts --apply`` "
    "batch. ``outcome`` ∈ {``healed``, ``residual``, ``mixed``, "
    "``failed``} per batch-level summary.",
    unit="s",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 300.0),
    expected_labels=("spec_type", "outcome"),
)

contract_structureless_backlog = _UpDownCounterWrapper(
    "contract_structureless_backlog",
    "Current count of structureless contracts (set by the daily cron "
    "via the ``--output=count`` mode of the renormalize command). "
    "Drains to 0 once Wave 3 / Wave 5 finish.",
    unit="1",
    expected_labels=("tenant_id",),
)

# Phase 227 Wave 1 (227.L7.2) — Schema-editor adoption metrics.
#
# Emitted from the frontend ``ModelsEditor.tsx`` via a thin POST to
# ``/api/v1/contracts/schema-editor/metrics`` that increments these
# OTel counters server-side. Letting the backend own the emission
# (rather than embedding an OTLP exporter in the browser bundle)
# keeps the metric inventory consistent with the rest of the codebase
# and avoids a 200KB+ SDK in the SPA.
schema_editor_opened_total = _CounterWrapper(
    "schema_editor_opened_total",
    "Total number of times the Schema editor tab was opened. Drives "
    "the funnel-top of the Schema-editor adoption dashboard panel.",
    unit="1",
    expected_labels=("tenant_id", "spec_type"),
)

schema_editor_save_total = _CounterWrapper(
    "schema_editor_save_total",
    "Total number of Schema-editor save attempts. ``outcome`` ∈ "
    "{``success``, ``conflict``, ``validation_error``, ``error``}.",
    unit="1",
    expected_labels=("tenant_id", "spec_type", "outcome"),
)

schema_editor_time_to_first_save_seconds = _HistogramWrapper(
    "schema_editor_time_to_first_save_seconds",
    "Wall-clock seconds between Schema-editor open and FIRST "
    "successful save in the same session. Buckets target the "
    "expected user-task scale (a few seconds to ~10 minutes).",
    unit="s",
    buckets=(1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0),
    expected_labels=("tenant_id", "spec_type"),
)

# Phase 227 Wave 1 (227.L7 audit follow-up) — generic audit-event counter.
#
# Emitted from ``hub.apps.audit.utils.create_audit_event`` on every
# successful audit-row INSERT. Drives the "Asset Auto-Reverts (Wave 5)"
# dashboard panel via ``increase(audit_events_total{action=...}[24h])``,
# and is generally useful for any downstream that wants to count audit
# events without scraping the audit_events table.
#
# Cardinality is bounded by the small set of action names + result
# values the audit module emits — no user-supplied data in the labels.
audit_events_total = _CounterWrapper(
    "audit_events_total",
    "Total audit events created. Labels: action (e.g., "
    "CONTRACT_STRUCTURELESS_REJECTED, ASSET_AUTO_REVERTED_STRUCTURELESS), "
    "resource_type (CONTRACT, ASSET, ...), result (SUCCESS, FAILURE, "
    "WARNING).",
    unit="1",
    expected_labels=("action", "resource_type", "result"),
)

# ODPS Metrics (Task 6.2.1)
odps_ingestion_total = _CounterWrapper(
    "odps_ingestion_total",
    "Total number of ODPS ingestion operations (marketplace)",
    unit="1",
    expected_labels=("source", "tenant_id"),
)

odps_normalization_total = _CounterWrapper(
    "odps_normalization_total",
    "Total number of ODPS normalization operations",
    unit="1",
    expected_labels=("status", "version", "tenant_id"),
)

odps_ref_resolution_total = _CounterWrapper(
    "odps_ref_resolution_total",
    "Total number of $ref resolution operations",
    unit="1",
    expected_labels=("ref_type", "status", "tenant_id"),
)

odps_ref_resolution_failures_total = _CounterWrapper(
    "odps_ref_resolution_failures_total",
    "Total number of $ref resolution failures",
    unit="1",
    expected_labels=("ref_type", "error_type", "tenant_id"),
)

odps_external_fetch_failures_total = _CounterWrapper(
    "odps_external_fetch_failures_total",
    "Total number of external $ref fetch failures",
    unit="1",
    expected_labels=("error_type", "tenant_id"),
)

odps_version_distribution_total = _CounterWrapper(
    "odps_version_distribution_total",
    "Total number of ODPS documents by version",
    unit="1",
    expected_labels=("version", "tenant_id"),
)

odps_rate_limit_violations_total = _CounterWrapper(
    "odps_rate_limit_violations_total",
    "Total number of ODPS $ref rate limit violations",
    unit="1",
    expected_labels=("level", "tenant_id", "user_id"),
)

odps_ref_cache_hits_total = _CounterWrapper(
    "odps_ref_cache_hits_total",
    "Total number of external $ref cache hits",
    unit="1",
    expected_labels=("tenant_id",),
)

odps_ref_cache_misses_total = _CounterWrapper(
    "odps_ref_cache_misses_total",
    "Total number of external $ref cache misses",
    unit="1",
    expected_labels=("tenant_id",),
)

# Cache hit/miss rate gauges (calculated from counters)
odps_ref_cache_hit_rate = _UpDownCounterWrapper(
    "odps_ref_cache_hit_rate",
    "Cache hit rate (hits / (hits + misses)) for external $ref cache",
    unit="1",
    expected_labels=("ref_type", "tenant_id"),
)

odps_ref_cache_miss_rate = _UpDownCounterWrapper(
    "odps_ref_cache_miss_rate",
    "Cache miss rate (misses / (hits + misses)) for external $ref cache",
    unit="1",
    expected_labels=("ref_type", "tenant_id"),
)

# Cache size gauge (current number of cached entries)
odps_ref_cache_size = _UpDownCounterWrapper(
    "odps_ref_cache_size",
    "Current number of cached external $ref entries",
    unit="1",
    expected_labels=("tenant_id", "ref_type"),
)

# Cache size limit gauge (maximum number of cached entries)
odps_ref_cache_size_limit = _UpDownCounterWrapper(
    "odps_ref_cache_size_limit",
    "Maximum number of cached external $ref entries (limit)",
    unit="1",
    expected_labels=("tenant_id", "ref_type"),
)

# Cache eviction counter (by eviction reason)
odps_ref_cache_eviction_rate = _CounterWrapper(
    "odps_ref_cache_eviction_rate",
    "Total number of cache evictions by reason",
    unit="1",
    expected_labels=("eviction_reason", "tenant_id"),
)

# ODPS Semantic Mapping Metrics (Task 6.6.3)
odps_semantic_mapping_duration_seconds = _HistogramWrapper(
    "odps_semantic_mapping_duration_seconds",
    "ODPS semantic mapping duration in seconds",
    unit="s",
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    expected_labels=("status", "tenant_id"),
)

odps_semantic_mapping_total = _CounterWrapper(
    "odps_semantic_mapping_total",
    "Total number of ODPS semantic mapping operations",
    unit="1",
    expected_labels=("status", "tenant_id"),
)

odps_semantic_mapping_success_rate = _UpDownCounterWrapper(
    "odps_semantic_mapping_success_rate",
    "ODPS semantic mapping success rate (0-1)",
    unit="1",
    expected_labels=("tenant_id",),
)

# ODCS Metrics (Task 6.2.2 - explicit backward compatibility)
odcs_ingestion_total = _CounterWrapper(
    "odcs_ingestion_total",
    "Total number of ODCS ingestion operations (technical)",
    unit="1",
    expected_labels=("source", "tenant_id"),
)

odcs_normalization_total = _CounterWrapper(
    "odcs_normalization_total",
    "Total number of ODCS normalization operations (all versions)",
    unit="1",
    expected_labels=("status", "version", "tenant_id"),
)

odcs_version_distribution_total = _CounterWrapper(
    "odcs_version_distribution_total",
    "Total number of ODCS documents by version (3.1.0, 3.0.2, 3.0.1, 3.0.0, 3.0.0-preview, 2.2.2)",
    unit="1",
    expected_labels=("version", "tenant_id"),
)

odcs_normalization_regression_total = _CounterWrapper(
    "odcs_normalization_regression_total",
    "Total number of ODCS normalization regressions detected",
    unit="1",
    expected_labels=("version", "regression_type", "tenant_id"),
)

# ODCS v3.1.0 specific metrics (Phase 26)
odcs_v310_relationships_count = _UpDownCounterWrapper(
    "odcs_v310_relationships_count",
    "Number of relationships mapped per v3.1.0 normalization",
    unit="1",
    expected_labels=("tenant_id",),
)

odcs_v310_fallback_total = _CounterWrapper(
    "odcs_v310_fallback_total",
    "Number of v3.1.0 contracts that fell back to a non-v3.1.0 normalizer (indicates registration bug)",
    unit="1",
    expected_labels=("fallback_normalizer", "tenant_id"),
)

# Phase 26.17: Backfill progress gauge — set by renormalize_contracts_v310()
# in hub/apps/contracts/tasks.py.  Value = remaining contracts to re-normalize.
normalization_backfill_remaining = _UpDownCounterWrapper(
    "normalization_backfill_remaining",
    "Number of contracts remaining in the v3.1.0 re-normalization backfill (0 = complete)",
    unit="1",
    expected_labels=("tenant_id",),
)

# Phase 26.17: Unified contract export counter with downgrade tracking.
# Incremented by ContractExportMixin in views_export.py on every export.
contract_export_total = _CounterWrapper(
    "contract_export_total",
    "Total contract export operations with downgrade tracking",
    unit="1",
    expected_labels=("status", "downgrade", "tenant_id"),
)

# ODCS Generation Metrics (Task 9.5.4.1.2.1)
odcs_generation_total = _CounterWrapper(
    "odcs_generation_total",
    "Total number of ODCS generation operations (all versions)",
    unit="1",
    expected_labels=("status", "version", "tenant_id"),
)

odcs_generation_duration_seconds = _HistogramWrapper(
    "odcs_generation_duration_seconds",
    "ODCS generation duration in seconds",
    unit="s",
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
    expected_labels=("status", "version", "tenant_id"),
)

odcs_generation_success_rate = _UpDownCounterWrapper(
    "odcs_generation_success_rate",
    "ODCS generation success rate (0-1)",
    unit="1",
    expected_labels=("tenant_id",),
)

# ============================================================================
# Histogram Metrics
# ============================================================================

# HTTP Request Duration
http_request_duration_seconds = _HistogramWrapper(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    unit="s",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    expected_labels=("method", "route", "status_class"),
)

# Job Duration
job_duration_seconds = _HistogramWrapper(
    "job_duration_seconds",
    "Job duration in seconds",
    unit="s",
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0),
    expected_labels=("job_type", "status"),
)

# Database Query Duration
db_query_duration_seconds = _HistogramWrapper(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    unit="s",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    expected_labels=("operation",),
)

# File Upload Size
file_upload_size_bytes = _HistogramWrapper(
    "file_upload_size_bytes",
    "File upload size in bytes",
    unit="By",
    buckets=(1024, 10240, 102400, 1048576, 10485760, 104857600, 1073741824),
    expected_labels=("file_type",),
)

# ODPS $ref Resolution Duration (Task 6.2.1)
# Buckets optimized for p50, p95, p99 percentiles
odps_ref_resolution_duration_seconds = _HistogramWrapper(
    "odps_ref_resolution_duration_seconds",
    "Duration of $ref resolution operations in seconds",
    unit="s",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    expected_labels=("ref_type", "tenant_id"),
)

# ODPS Export Duration (Task 6.6.1)
# Buckets optimized for export operations (typically faster than ref resolution)
odps_export_duration_seconds = _HistogramWrapper(
    "odps_export_duration_seconds",
    "Duration of ODPS export operations in seconds",
    unit="s",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    expected_labels=("format", "size_category", "tenant_id"),
)

# ODPS Export Size (Task 6.6.1)
# Buckets optimized for export sizes (bytes)
odps_export_size_bytes = _HistogramWrapper(
    "odps_export_size_bytes",
    "Size of ODPS export output in bytes",
    unit="By",
    buckets=(1024, 10240, 102400, 1048576, 10485760, 104857600, 1073741824),
    expected_labels=("format", "tenant_id"),
)

# ODPS Export Total (Task 6.6.4)
# Counter to track export attempts with status for failure rate alerts
odps_export_total = _CounterWrapper(
    "odps_export_total",
    "Total number of ODPS export operations",
    unit="1",
    expected_labels=("status", "format", "tenant_id"),
)

# ODCS Export Duration (Task 9.5.4.1.4.1)
# Buckets optimized for export operations (typically faster than ref resolution)
odcs_export_duration_seconds = _HistogramWrapper(
    "odcs_export_duration_seconds",
    "Duration of ODCS export operations in seconds",
    unit="s",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    expected_labels=("format", "size_category", "version", "tenant_id"),
)

# ODCS Export Size (Task 9.5.4.1.4.1)
# Buckets optimized for export sizes (bytes)
odcs_export_size_bytes = _HistogramWrapper(
    "odcs_export_size_bytes",
    "Size of ODCS export output in bytes",
    unit="By",
    buckets=(1024, 10240, 102400, 1048576, 10485760, 104857600, 1073741824),
    expected_labels=("format", "version", "tenant_id"),
)

# ODCS Export Total (Task 9.5.4.1.4.1)
# Counter to track export attempts with status for failure rate alerts
odcs_export_total = _CounterWrapper(
    "odcs_export_total",
    "Total number of ODCS export operations",
    unit="1",
    expected_labels=("status", "format", "version", "tenant_id"),
)

# ODPS Linking Metrics (Task 6.6.2)
odps_linking_total = _CounterWrapper(
    "odps_linking_total",
    "Total number of ODPS linking operations",
    unit="1",
    expected_labels=("direction", "tenant_id"),
)

odps_linking_success_total = _CounterWrapper(
    "odps_linking_success_total",
    "Total number of successful ODPS linking operations",
    unit="1",
    expected_labels=("direction", "tenant_id"),
)

odps_linking_failures_total = _CounterWrapper(
    "odps_linking_failures_total",
    "Total number of failed ODPS linking operations",
    unit="1",
    expected_labels=("direction", "error_code", "tenant_id"),
)

odps_linking_duration_seconds = _HistogramWrapper(
    "odps_linking_duration_seconds",
    "Duration of ODPS linking operations in seconds",
    unit="s",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    expected_labels=("direction", "tenant_id"),
)


# ============================================================================
# Gauge Metrics (using UpDownCounter for settable values)
# ============================================================================

# Database Metrics
db_connections_active = _UpDownCounterWrapper(
    "db_connections_active", "Number of active database connections", unit="1", expected_labels=()
)

# Job Queue Metrics
job_queue_length = _UpDownCounterWrapper(
    "job_queue_length",
    "Current number of jobs in queue",
    unit="1",
    expected_labels=("job_type", "queue_name"),
)

job_queue_depth = _UpDownCounterWrapper(
    "job_queue_depth",
    "Current depth of job queue (total pending jobs)",
    unit="1",
    expected_labels=("job_type", "queue_name"),
)

job_processing_rate = _CounterWrapper(
    "job_processing_rate",
    "Total number of jobs processed per second",
    unit="1",
    expected_labels=("job_type", "status", "queue_name"),
)

job_enqueue_failed_total = _CounterWrapper(
    "job_enqueue_failed_total",
    "Total number of job enqueue failures (Redis unavailable, queue full, etc.)",
    unit="1",
    expected_labels=("job_type",),
)

job_queue_length_by_priority = _UpDownCounterWrapper(
    "job_queue_length_by_priority",
    "Current number of jobs in queue by priority",
    unit="1",
    expected_labels=("priority", "job_type"),
)

job_processing_rate_by_priority = _CounterWrapper(
    "job_processing_rate_by_priority",
    "Total number of jobs processed per second by priority",
    unit="1",
    expected_labels=("priority", "job_type"),
)

job_worker_active = _UpDownCounterWrapper(
    "job_worker_active",
    "Current number of active job workers",
    unit="1",
    expected_labels=("worker_id", "queue_name"),
)

job_worker_throughput = _CounterWrapper(
    "job_worker_throughput",
    "Total number of jobs processed by worker",
    unit="1",
    expected_labels=("worker_id", "job_type"),
)

job_retry_count = _HistogramWrapper(
    "job_retry_count",
    "Number of retries for job processing",
    unit="1",
    buckets=(0.0, 1.0, 2.0, 3.0, 5.0, 10.0),
    expected_labels=("job_type", "queue_name"),
)

job_retry_delay_seconds = _HistogramWrapper(
    "job_retry_delay_seconds",
    "Retry delay duration in seconds",
    unit="s",
    buckets=(30.0, 60.0, 120.0, 300.0, 600.0, 1800.0, 3600.0),
    expected_labels=("job_type",),
)

job_retry_failures_total = _CounterWrapper(
    "job_retry_failures_total",
    "Total number of jobs that failed after retries",
    unit="1",
    expected_labels=("job_type", "error_type"),
)

job_timeout_rate = _CounterWrapper(
    "job_timeout_rate",
    "Total number of jobs that timed out",
    unit="1",
    expected_labels=("job_type", "queue_name"),
)

# Per-tenant job count metrics
tenant_running_jobs = _UpDownCounterWrapper(
    "tenant_running_jobs",
    "Current number of running jobs per tenant",
    unit="1",
    expected_labels=("tenant_id",),
)

tenant_queued_jobs = _UpDownCounterWrapper(
    "tenant_queued_jobs",
    "Current number of queued jobs per tenant",
    unit="1",
    expected_labels=("tenant_id",),
)

# Asset Status Metrics
asset_dq_status = _UpDownCounterWrapper(
    "asset_dq_status_count",
    "Number of assets by DQ status",
    unit="1",
    expected_labels=("status", "tenant_id"),
)

asset_compliance_status = _UpDownCounterWrapper(
    "asset_compliance_status_count",
    "Number of assets by compliance status",
    unit="1",
    expected_labels=("status", "tenant_id"),
)

# Scheduled Ingestion Metrics
scheduled_ingestions_total = _CounterWrapper(
    "scheduled_ingestions_total",
    "Total number of scheduled ingestions",
    unit="1",
    expected_labels=("status", "source_type", "tenant_id"),
)

scheduled_ingestion_runs_total = _CounterWrapper(
    "scheduled_ingestion_runs_total",
    "Total number of scheduled ingestion runs",
    unit="1",
    expected_labels=("status", "scheduled_ingestion_id", "tenant_id"),
)

scheduled_ingestion_files_processed_total = _CounterWrapper(
    "scheduled_ingestion_files_processed_total",
    "Total number of files processed by scheduled ingestions",
    unit="1",
    expected_labels=("scheduled_ingestion_id", "tenant_id"),
)

scheduled_ingestion_files_failed_total = _CounterWrapper(
    "scheduled_ingestion_files_failed_total",
    "Total number of files failed in scheduled ingestions",
    unit="1",
    expected_labels=("scheduled_ingestion_id", "tenant_id"),
)

scheduled_ingestion_datasets_created_total = _CounterWrapper(
    "scheduled_ingestion_datasets_created_total",
    "Total number of datasets created by scheduled ingestions",
    unit="1",
    expected_labels=("scheduled_ingestion_id", "tenant_id"),
)

# Phase 250.2.C.3 (closes Gap 4 / B2-9) — fired by the scheduled-
# ingestion worker when ``AssetService.create_or_get_idempotent``
# refuses an asset bootstrap because the (tenant, key) pair is held
# by a RETIRED Asset row. This is an operator-actionable signal: a
# scheduled-ingestion job cannot proceed until ops either transitions
# the RETIRED asset or reconfigures the schedule with a new key.
# Alert routing: Prometheus alerting rule fires when this counter
# increments faster than 1/hour for any (tenant_id) pair.
scheduled_ingestion_asset_key_retired_total = _CounterWrapper(
    "scheduled_ingestion_asset_key_retired_total",
    "Scheduled-ingestion runs refused because the target asset key "
    "is held by a RETIRED Asset row (Phase 250.2.C / B2-9).",
    unit="1",
    expected_labels=("scheduled_ingestion_id", "tenant_id"),
)

scheduled_ingestion_duration_seconds = _HistogramWrapper(
    "scheduled_ingestion_duration_seconds",
    "Duration of scheduled ingestion runs in seconds",
    unit="s",
    expected_labels=("scheduled_ingestion_id", "status", "tenant_id"),
    buckets=(10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0),
)

scheduled_ingestion_files_per_run = _HistogramWrapper(
    "scheduled_ingestion_files_per_run",
    "Number of files processed per ingestion run",
    unit="1",
    expected_labels=("scheduled_ingestion_id", "tenant_id"),
    buckets=(1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0),
)

scheduled_ingestion_active_count = _UpDownCounterWrapper(
    "scheduled_ingestion_active_count",
    "Current number of active scheduled ingestions",
    unit="1",
    expected_labels=("tenant_id",),
)

scheduled_ingestion_runs_running = _UpDownCounterWrapper(
    "scheduled_ingestion_runs_running",
    "Current number of scheduled ingestion runs in RUNNING state",
    unit="1",
    expected_labels=("scheduled_ingestion_id", "tenant_id"),
)

# Scheduled Export Metrics
scheduled_export_runs_total = _CounterWrapper(
    "scheduled_export_runs_total",
    "Total number of scheduled export runs",
    unit="1",
    expected_labels=("status", "scheduled_export_id", "tenant_id"),
)

scheduled_export_items_exported_total = _CounterWrapper(
    "scheduled_export_items_exported_total",
    "Total number of items exported by scheduled exports",
    unit="1",
    expected_labels=("scheduled_export_id", "tenant_id"),
)

scheduled_export_items_failed_total = _CounterWrapper(
    "scheduled_export_items_failed_total",
    "Total number of items failed in scheduled exports",
    unit="1",
    expected_labels=("scheduled_export_id", "tenant_id"),
)

scheduled_export_duration_seconds = _HistogramWrapper(
    "scheduled_export_duration_seconds",
    "Duration of scheduled export runs in seconds",
    unit="s",
    expected_labels=("scheduled_export_id", "status", "tenant_id"),
    buckets=(10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0),
)

scheduled_export_runs_running = _UpDownCounterWrapper(
    "scheduled_export_runs_running",
    "Current number of scheduled export runs in RUNNING state",
    unit="1",
    expected_labels=("scheduled_export_id", "tenant_id"),
)

# Service Layer Metrics
service_operations_total = _CounterWrapper(
    "service_operations_total",
    "Total number of service operations",
    unit="1",
    expected_labels=("service", "operation", "tenant_id"),
)

service_operation_duration_seconds = _HistogramWrapper(
    "service_operation_duration_seconds",
    "Duration of service operations in seconds",
    unit="s",
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0),
    expected_labels=("service", "operation", "tenant_id"),
)

service_operation_errors_total = _CounterWrapper(
    "service_operation_errors_total",
    "Total number of service operation errors",
    unit="1",
    expected_labels=("service", "operation", "error_code", "tenant_id"),
)

# Cross-Service Communication Metrics
service_calls_total = _CounterWrapper(
    "service_calls_total",
    "Total number of cross-service calls",
    unit="1",
    expected_labels=("source_service", "target_service", "method", "status", "tenant_id"),
)

service_call_duration_seconds = _HistogramWrapper(
    "service_call_duration_seconds",
    "Duration of cross-service calls in seconds",
    unit="s",
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0),
    expected_labels=("source_service", "target_service", "method", "status", "tenant_id"),
)

service_call_errors_total = _CounterWrapper(
    "service_call_errors_total",
    "Total number of cross-service call errors",
    unit="1",
    expected_labels=("source_service", "target_service", "method", "error_type", "tenant_id"),
)

service_call_retries_total = _CounterWrapper(
    "service_call_retries_total",
    "Total number of cross-service call retries",
    unit="1",
    expected_labels=("source_service", "target_service", "method", "retry_count", "tenant_id"),
)

service_call_timeouts_total = _CounterWrapper(
    "service_call_timeouts_total",
    "Total number of cross-service call timeouts",
    unit="1",
    expected_labels=("source_service", "target_service", "method", "tenant_id"),
)

# Service Health Metrics
service_health_checks_total = _CounterWrapper(
    "service_health_checks_total",
    "Total number of service health checks",
    unit="1",
    expected_labels=("service", "status", "check_type"),
)

service_health_check_duration_seconds = _HistogramWrapper(
    "service_health_check_duration_seconds",
    "Duration of service health checks in seconds",
    unit="s",
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
    expected_labels=("service", "check_type"),
)

service_health_status = _UpDownCounterWrapper(
    "service_health_status",
    "Current health status of services (1=healthy, 0=unhealthy)",
    unit="1",
    expected_labels=("service",),
)


# ============================================================================
# Marketplace Integration Metrics
# ============================================================================

# Marketplace Connection Metrics
marketplace_connections_total = _CounterWrapper(
    "marketplace_connections_total",
    "Total number of marketplace connections created",
    unit="1",
    expected_labels=("marketplace_type", "tenant_id", "status"),
)

marketplace_connection_status = _UpDownCounterWrapper(
    "marketplace_connection_status",
    "Current status of marketplace connections (1=active, 0=inactive)",
    unit="1",
    expected_labels=("marketplace_type", "tenant_id", "connection_id"),
)

# Sync Job Metrics
marketplace_sync_jobs_total = _CounterWrapper(
    "marketplace_sync_jobs_total",
    "Total number of marketplace sync jobs started",
    unit="1",
    expected_labels=("marketplace_type", "direction", "tenant_id", "status"),
)

marketplace_sync_job_duration_seconds = _HistogramWrapper(
    "marketplace_sync_job_duration_seconds",
    "Duration of marketplace sync jobs in seconds",
    unit="s",
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0),
    expected_labels=("marketplace_type", "direction", "status"),
)

marketplace_sync_job_success_rate = _CounterWrapper(
    "marketplace_sync_job_success_rate",
    "Success rate of marketplace sync jobs (incremented on success)",
    unit="1",
    expected_labels=("marketplace_type", "direction", "tenant_id"),
)

# Connector Operation Metrics
marketplace_connector_operations_total = _CounterWrapper(
    "marketplace_connector_operations_total",
    "Total number of connector operations performed",
    unit="1",
    expected_labels=("marketplace_type", "operation_type", "status", "tenant_id"),
)

marketplace_connector_operation_duration_seconds = _HistogramWrapper(
    "marketplace_connector_operation_duration_seconds",
    "Duration of connector operations in seconds",
    unit="s",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    expected_labels=("marketplace_type", "operation_type", "status"),
)

marketplace_connector_operation_errors_total = _CounterWrapper(
    "marketplace_connector_operation_errors_total",
    "Total number of connector operation errors",
    unit="1",
    expected_labels=("marketplace_type", "operation_type", "error_type", "tenant_id"),
)

# Marketplace API Call Metrics
marketplace_api_calls_total = _CounterWrapper(
    "marketplace_api_calls_total",
    "Total number of API calls made to marketplaces",
    unit="1",
    expected_labels=("marketplace_type", "endpoint", "method", "status_code", "tenant_id"),
)

marketplace_api_call_duration_seconds = _HistogramWrapper(
    "marketplace_api_call_duration_seconds",
    "Duration of API calls to marketplaces in seconds",
    unit="s",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    expected_labels=("marketplace_type", "endpoint", "method", "status_code"),
)

marketplace_api_call_errors_total = _CounterWrapper(
    "marketplace_api_call_errors_total",
    "Total number of API call errors to marketplaces",
    unit="1",
    expected_labels=("marketplace_type", "endpoint", "method", "error_type", "tenant_id"),
)

# Marketplace Connection Test Metrics
marketplace_connection_tests_total = _CounterWrapper(
    "marketplace_connection_tests_total",
    "Total number of marketplace connection tests performed",
    unit="1",
    expected_labels=("marketplace_type", "tenant_id", "status"),
)

marketplace_connection_test_failures_total = _CounterWrapper(
    "marketplace_connection_test_failures_total",
    "Total number of marketplace connection test failures",
    unit="1",
    expected_labels=("marketplace_type", "tenant_id", "connection_id", "error_type"),
)


# ============================================================================
# Phase 78 — Business Rule Gap Observability Metrics
# ============================================================================

business_rule_validation_failures_total = _CounterWrapper(
    "business_rule_validation_failures_total",
    "Total number of business rule validation failures",
    unit="1",
    expected_labels=("module", "rule_name", "tenant_id"),
)

workflow_compensation_failures_total = _CounterWrapper(
    "workflow_compensation_failures_total",
    "Total number of workflow compensation step failures",
    unit="1",
    expected_labels=("workflow_name", "step_name"),
)

side_effect_failures_total = _CounterWrapper(
    "side_effect_failures_total",
    "Total number of side-effect outbox failures (Phase 76)",
    unit="1",
    expected_labels=("effect_type",),
)

poll_timeout_total = _CounterWrapper(
    "poll_timeout_total",
    "Total number of compliance/DQ polling timeouts",
    unit="1",
    expected_labels=("service",),
)


# ============================================================================
# Phase 116D: Customer Billing Metrics
# ============================================================================

billing_reports_generated_total = _CounterWrapper(
    "billing_reports_generated_total",
    "Total number of billing reports generated",
    unit="1",
    expected_labels=("tenant_id", "customer_id", "currency"),
)

billing_report_generation_seconds = _HistogramWrapper(
    "billing_report_generation_seconds",
    "Billing report generation duration in seconds",
    unit="s",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    expected_labels=("tenant_id",),
)

billing_report_total_amount = _HistogramWrapper(
    "billing_report_total_amount",
    "Billing report total amount (for distribution analysis)",
    unit="1",
    buckets=(0, 10, 50, 100, 500, 1000, 5000, 10000, 50000),
    expected_labels=("tenant_id", "currency"),
)

billing_report_email_sent_total = _CounterWrapper(
    "billing_report_email_sent_total",
    "Total number of billing report emails sent",
    unit="1",
    expected_labels=("tenant_id", "customer_id"),
)

billing_reports_finalized_total = _CounterWrapper(
    "billing_reports_finalized_total",
    "Total number of billing reports finalized",
    unit="1",
    expected_labels=("tenant_id",),
)

billing_reports_voided_total = _CounterWrapper(
    "billing_reports_voided_total",
    "Total number of billing reports voided",
    unit="1",
    expected_labels=("tenant_id",),
)


# ============================================================================
# Metrics View Function
# ============================================================================

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET


# ── Transformation Pipeline Metrics (Phase 115E.1) ──────────────────────

transformation_runs_total = _CounterWrapper(
    "transformation_runs_total",
    "Total transformation pipeline executions",
    unit="1",
    expected_labels=("status", "execution_mode", "tenant_id"),
)

transformation_duration_seconds = _HistogramWrapper(
    "transformation_duration_seconds",
    "Duration of transformation pipeline executions",
    unit="s",
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
    expected_labels=("pipeline_id", "status", "tenant_id"),
)

transformation_rows_processed = _CounterWrapper(
    "transformation_rows_processed",
    "Total rows processed by transformation pipelines",
    unit="1",
    expected_labels=("step_type", "tenant_id"),
)

transformation_errors_total = _CounterWrapper(
    "transformation_errors_total",
    "Total transformation pipeline errors",
    unit="1",
    expected_labels=("error_type", "step_type", "tenant_id"),
)

transformation_memory_bytes = _HistogramWrapper(
    "transformation_memory_bytes",
    "Memory usage of transformation pipeline executions",
    unit="By",
    buckets=(
        1048576, 10485760, 52428800, 104857600,
        268435456, 536870912, 1073741824,
    ),
    expected_labels=("pipeline_id", "tenant_id"),
)

transformation_queue_depth = _UpDownCounterWrapper(
    "transformation_queue_depth",
    "Number of transformation pipeline executions in queue",
    unit="1",
    expected_labels=("tenant_id",),
)


@csrf_exempt
@require_GET
def metrics_view(request):
    """
    Prometheus metrics endpoint using OpenTelemetry Prometheus exporter.

    This endpoint is exempt from authentication as Prometheus scrapers
    typically don't provide authentication credentials.

    Returns:
        HTTP response with Prometheus metrics in text format
    """
    if not OPENTELEMETRY_AVAILABLE or REGISTRY is None:
        return HttpResponse("Metrics not available", status=503, content_type="text/plain")

    try:
        # Generate Prometheus format from the registry
        metrics_data = generate_latest(REGISTRY)
        return HttpResponse(metrics_data, content_type=CONTENT_TYPE_LATEST)
    except (ValueError, AttributeError, RuntimeError) as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            "Failed to generate metrics",
            extra={"error_type": type(e).__name__},
            exc_info=True,
        )
        return HttpResponse("Metrics generation failed", status=500, content_type="text/plain")
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.exception(
            "Unexpected error generating metrics",
            extra={"error_type": type(e).__name__},
        )
        return HttpResponse(
            f"Error generating metrics: {str(e)}", status=500, content_type="text/plain"
        )
