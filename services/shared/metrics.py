"""
Shared Prometheus Metrics for FastAPI Services

Provides common metrics collection utilities for all FastAPI services.
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST, REGISTRY
from typing import Optional
import time
from functools import wraps


def _safe_counter(name, description, labelnames):
    """Create a Counter, returning the existing one if already registered."""
    try:
        return Counter(name, description, labelnames)
    except ValueError:
        return REGISTRY._names_to_collectors[name]


def _safe_histogram(name, description, labelnames, buckets=Histogram.DEFAULT_BUCKETS):
    """Create a Histogram, returning the existing one if already registered."""
    try:
        return Histogram(name, description, labelnames, buckets=buckets)
    except ValueError:
        return REGISTRY._names_to_collectors[name]


def _safe_gauge(name, description, labelnames=None):
    """Create a Gauge, returning the existing one if already registered."""
    try:
        if labelnames:
            return Gauge(name, description, labelnames)
        return Gauge(name, description)
    except ValueError:
        return REGISTRY._names_to_collectors[name]


# HTTP Request Metrics (for FastAPI services)
http_requests_total = _safe_counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['service', 'method', 'route', 'status_class']
)

http_request_duration_seconds = _safe_histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['service', 'method', 'route', 'status_class'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

http_errors_total = _safe_counter(
    'http_errors_total',
    'Total number of HTTP errors',
    ['service', 'method', 'route', 'status_code']
)

# Semantic Service Metrics
sparql_queries_total = _safe_counter(
    'sparql_queries_total',
    'Total number of SPARQL queries',
    ['service', 'status', 'tenant_id']
)

sparql_query_duration_seconds = _safe_histogram(
    'sparql_query_duration_seconds',
    'SPARQL query duration in seconds',
    ['service', 'status'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
)

mapping_operations_total = _safe_counter(
    'mapping_operations_total',
    'Total number of mapping operations',
    ['service', 'operation_type', 'status', 'tenant_id']
)

mapping_operation_duration_seconds = _safe_histogram(
    'mapping_operation_duration_seconds',
    'Mapping operation duration in seconds',
    ['service', 'operation_type', 'status'],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
)

fuseki_interactions_total = _safe_counter(
    'fuseki_interactions_total',
    'Total number of Fuseki interactions',
    ['service', 'operation', 'status']
)

fuseki_store_duration_seconds = _safe_histogram(
    'fuseki_store_duration_seconds',
    'Fuseki graph storage duration in seconds (actual commit time)',
    ['service', 'operation'],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
)

# Dataset existence check cache metrics
dataset_existence_cache_hits_total = _safe_counter(
    'dataset_existence_cache_hits_total',
    'Total number of dataset existence cache hits',
    ['service']
)

dataset_existence_cache_misses_total = _safe_counter(
    'dataset_existence_cache_misses_total',
    'Total number of dataset existence cache misses',
    ['service']
)

dataset_existence_check_duration_seconds = _safe_histogram(
    'dataset_existence_check_duration_seconds',
    'Duration of dataset existence checks in seconds',
    ['service', 'cache_status'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

# Phase 29 — Semantic observability: SHACL, tenant isolation, cache
shacl_violations_total = _safe_counter(
    'shacl_violations_total',
    'Total number of SHACL shape validation violations',
    ['service', 'severity', 'shape']
)

tenant_isolation_violations_total = _safe_counter(
    'tenant_isolation_violations_total',
    'Total number of tenant isolation violations detected (SLO: must stay 0)',
    ['service']
)

fuseki_insert_duration_seconds = _safe_histogram(
    'fuseki_insert_duration_seconds',
    'Duration of Fuseki triple insert operations in seconds',
    ['service', 'operation'],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
)

semantic_cache_hit_total = _safe_counter(
    'semantic_cache_hit_total',
    'Total number of semantic service Redis cache hits',
    ['service']
)

semantic_cache_miss_total = _safe_counter(
    'semantic_cache_miss_total',
    'Total number of semantic service Redis cache misses',
    ['service']
)

# Connection Pool Metrics (Task 9.10.2.5.7.1.5)
http_connection_reuse_total = _safe_counter(
    'http_connection_reuse_total',
    'Total number of HTTP connection reuses',
    ['service', 'operation']
)

http_connection_new_total = _safe_counter(
    'http_connection_new_total',
    'Total number of new HTTP connections created',
    ['service', 'operation']
)

http_connection_pool_size = _safe_gauge(
    'http_connection_pool_size',
    'Current HTTP connection pool size',
    ['service']
)

# DQ Service Metrics
dq_runs_total = _safe_counter(
    'dq_runs_total',
    'Total number of DQ runs',
    ['service', 'status', 'engine', 'tenant_id']
)

dq_run_duration_seconds = _safe_histogram(
    'dq_run_duration_seconds',
    'DQ run duration in seconds',
    ['service', 'status', 'engine'],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0)
)

dq_success_rate = _safe_gauge(
    'dq_success_rate',
    'DQ run success rate (0-1)',
    ['service', 'engine']
)

# Phase 240.1.B.5 (REQ-DQ-RETENTION + 240.1.B Grafana panel "S3 payload-bucket
# size trend") — total bytes used by DQ payload artefacts in S3, broken down
# by tenant. Populated by the daily ``collect_dq_s3_metrics`` management
# command (run via the ``collect-dq-s3-metrics`` Kubernetes CronJob). Gauge
# semantics — the value is the OBSERVED current total at last collection,
# NOT a monotonic counter, so the Grafana "S3 payload-bucket size trend"
# panel can plot it directly without ``rate()`` smoothing.
dq_s3_payload_bytes_total = _safe_gauge(
    'dq_s3_payload_bytes_total',
    (
        'Total bytes of DQ payload artefacts in S3 at last collection. '
        'Populated daily by collect_dq_s3_metrics; alerts on >2σ '
        'growth from 7d-baseline trip DQS3PayloadGrowthAnomaly.'
    ),
    ['service', 'tenant_id'],
)

# Phase 240.1.B audit-fix — series referenced by alerts dq.yml + dashboard
# data-quality.json that didn't exist in the codebase prior.  Adding them
# alongside the rest of the DQ family so the alerts can actually fire and
# the panels can actually populate in production.
#
# 1) dq_alert_deliveries_total — used by DQAlertDeliveryFailing alert AND
#    dashboard panel "DQ alert rule firing count by channel".  Incremented
#    at each delivery attempt (success / failure) in
#    ``hub/apps/dq/tasks.py``; ``status`` ∈ {SUCCESS, FAIL}, ``channel`` ∈
#    {email, slack, webhook, pagerduty}.
dq_alert_deliveries_total = _safe_counter(
    'dq_alert_deliveries_total',
    (
        'Total DQ alert delivery attempts split by channel + status. '
        'Drives the DQAlertDeliveryFailing alert (>10% FAIL over 30m).'
    ),
    ['service', 'channel', 'status'],
)

# 2) dq_async_queue_depth — used by DQRunQueueDepth alert.  Sampled
#    periodically from the RQ queue length by the
#    ``sample_dq_queue_depth`` management command (Kubernetes CronJob,
#    every 5 minutes — see helm/templates/cronjob/sample-dq-queue-depth.yaml).
dq_async_queue_depth = _safe_gauge(
    'dq_async_queue_depth',
    (
        'Pending DQ run jobs in the worker queue at last sample. '
        'Drives the DQRunQueueDepth alert (>100 sustained 30m).'
    ),
    ['service', 'queue'],
)

# 3) dq_audit_write_errors_total — used by DQAuditWriteFailing alert.
#    Incremented at every site that catches an exception from
#    ``create_audit_event`` for a DQ-domain action; the audit utils helper
#    is best-effort so the surrounding write doesn't fail, but the metric
#    captures the deny path so oncall can see compliance evidence at risk.
dq_audit_write_errors_total = _safe_counter(
    'dq_audit_write_errors_total',
    (
        'Total DQ-action audit-event write failures.  Pages oncall '
        'when sustained > 1/min for 5m via DQAuditWriteFailing.'
    ),
    ['service', 'action'],
)

# 4) dq_run_quality_score — histogram of quality-score values observed at
#    run completion.  Drives the "DQ score distribution" heat-map panel.
#    Buckets cover the 0..1 quality-score range with finer resolution at
#    the upper end (where most healthy runs sit) and at the lower end
#    (where regressions are most actionable).
dq_run_quality_score = _safe_histogram(
    'dq_run_quality_score',
    'DQ run quality score distribution (0.0-1.0).',
    ['service', 'engine', 'tenant_id'],
    buckets=(0.1, 0.25, 0.5, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0),
)

# Compliance Service Metrics
compliance_runs_total = _safe_counter(
    'compliance_runs_total',
    'Total number of compliance runs',
    ['service', 'status', 'risk_level', 'tenant_id']
)

compliance_run_duration_seconds = _safe_histogram(
    'compliance_run_duration_seconds',
    'Compliance run duration in seconds',
    ['service', 'status', 'risk_level'],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0)
)

compliance_success_rate = _safe_gauge(
    'compliance_success_rate',
    'Compliance run success rate (0-1)',
    ['service']
)

# Phase 19.13.1 — Fine-grained compliance observability metrics

compliance_audit_records_total = _safe_counter(
    'compliance_audit_records_total',
    'Total number of compliance audit records emitted',
    ['service', 'tenant_id']
)

compliance_regulation_triggers_total = _safe_counter(
    'compliance_regulation_triggers_total',
    'Total number of individual regulation triggers detected during compliance scans',
    ['service', 'regulation', 'tenant_id']
)

compliance_pii_categories_detected_total = _safe_counter(
    'compliance_pii_categories_detected_total',
    'Total number of PII category detections across all compliance scans',
    ['service', 'category', 'tenant_id']
)

compliance_cross_border_alerts_total = _safe_counter(
    'compliance_cross_border_alerts_total',
    'Total number of cross-border data transfer alerts raised',
    ['service', 'tenant_id']
)

compliance_localisation_alerts_total = _safe_counter(
    'compliance_localisation_alerts_total',
    'Total number of data localisation requirement alerts raised',
    ['service', 'tenant_id']
)

compliance_async_queue_depth = _safe_gauge(
    'compliance_async_queue_depth',
    'Current number of compliance scan jobs waiting in or being processed by the async queue',
    ['service']
)

# DataContract Service Metrics
contract_validations_total = _safe_counter(
    'contract_validations_total',
    'Total number of contract validations',
    ['service', 'status', 'spec_type', 'tenant_id']
)

contract_validation_duration_seconds = _safe_histogram(
    'contract_validation_duration_seconds',
    'Contract validation duration in seconds',
    ['service', 'status', 'spec_type'],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
)

contract_lint_operations_total = _safe_counter(
    'contract_lint_operations_total',
    'Total number of contract lint operations',
    ['service', 'status', 'tenant_id']
)

contract_convert_operations_total = _safe_counter(
    'contract_convert_operations_total',
    'Total number of contract convert operations',
    ['service', 'status', 'source_format', 'target_format', 'tenant_id']
)

# ODPS Semantic Mapping Metrics (Task 6.6.3)
odps_semantic_mapping_duration_seconds = _safe_histogram(
    'odps_semantic_mapping_duration_seconds',
    'ODPS semantic mapping duration in seconds',
    ['service', 'status'],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
)

odps_semantic_mapping_total = _safe_counter(
    'odps_semantic_mapping_total',
    'Total number of ODPS semantic mapping operations',
    ['service', 'status', 'tenant_id']
)

odps_semantic_mapping_success_rate = _safe_gauge(
    'odps_semantic_mapping_success_rate',
    'ODPS semantic mapping success rate (0-1)',
    ['service', 'tenant_id']
)

# Semantic Service Retry Metrics (Task 9.10.2.5.7.1.1)
semantic_uri_resolution_retries_total = _safe_counter(
    'semantic_uri_resolution_retries_total',
    'Total number of URI resolution retries',
    ['service', 'status_code', 'reason']
)

semantic_uri_resolution_retry_delay_seconds = _safe_histogram(
    'semantic_uri_resolution_retry_delay_seconds',
    'URI resolution retry delay in seconds',
    ['service', 'status_code'],
    buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0)
)

# SPARQL query optimization metrics (Task 9.10.2.5.7.1.7 - ASK instead of SELECT)
sparql_query_optimization_total = _safe_counter(
    'sparql_query_optimization_total',
    'Total number of SPARQL query optimizations applied',
    ['service', 'optimization_type', 'query_type']
)


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


def normalize_route(route: str) -> str:
    """
    Normalize route by replacing UUIDs and IDs with placeholders.

    Args:
        route: Request path

    Returns:
        Normalized route
    """
    import re
    # Replace UUIDs with {id}
    route = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', route, flags=re.IGNORECASE)
    # Replace numeric IDs with {id}
    route = re.sub(r'/\d+', '/{id}', route)
    return route


def track_request_metrics(service_name: str):
    """
    Decorator to track HTTP request metrics for FastAPI endpoints.

    Args:
        service_name: Name of the service (e.g., 'semantic-service', 'dq-service')
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args (FastAPI injects Request as first arg if present)
            request = None
            for arg in args:
                if hasattr(arg, 'method') and hasattr(arg, 'url'):
                    request = arg
                    break

            start_time = time.time()
            status_code = 200
            status_class = '2xx'

            try:
                # Call the actual endpoint
                response = await func(*args, **kwargs)

                # Extract status code from response
                if hasattr(response, 'status_code'):
                    status_code = response.status_code
                elif isinstance(response, dict) and 'status' in response:
                    # Health check endpoints return dict with status
                    status_code = 200

                status_class = get_status_class(status_code)

                # Get route
                route = '/'
                if request:
                    route = normalize_route(str(request.url.path))

                method = request.method if request else 'UNKNOWN'

                # Record metrics
                http_requests_total.labels(
                    service=service_name,
                    method=method,
                    route=route,
                    status_class=status_class
                ).inc()

                duration = time.time() - start_time
                http_request_duration_seconds.labels(
                    service=service_name,
                    method=method,
                    route=route,
                    status_class=status_class
                ).observe(duration)

                # Record errors
                if status_code >= 400:
                    http_errors_total.labels(
                        service=service_name,
                        method=method,
                        route=route,
                        status_code=status_code
                    ).inc()

                return response

            except Exception as e:
                # Record error metrics
                status_code = 500
                status_class = '5xx'

                route = '/'
                if request:
                    route = normalize_route(str(request.url.path))

                method = request.method if request else 'UNKNOWN'

                http_errors_total.labels(
                    service=service_name,
                    method=method,
                    route=route,
                    status_code=500
                ).inc()

                http_requests_total.labels(
                    service=service_name,
                    method=method,
                    route=route,
                    status_class='5xx'
                ).inc()

                raise

        return wrapper
    return decorator


def get_metrics_response():
    """
    Get Prometheus metrics response.

    Returns:
        Tuple of (metrics_data, content_type)
    """
    metrics_data = generate_latest()
    return metrics_data, CONTENT_TYPE_LATEST

