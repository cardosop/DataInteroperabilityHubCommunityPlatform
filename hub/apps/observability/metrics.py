"""
Observability: Prometheus Metrics

Custom metrics for request counts, latencies, error rates, and job counts.
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from django.http import HttpResponse
from django.conf import settings
import time


# HTTP Request Metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'route', 'status_class']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'route', 'status_class'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

http_errors_total = Counter(
    'http_errors_total',
    'Total number of HTTP errors',
    ['method', 'route', 'status_code']
)

# Job Metrics
jobs_started_total = Counter(
    'jobs_started_total',
    'Total number of jobs started',
    ['job_type', 'tenant_id']
)

jobs_completed_total = Counter(
    'jobs_completed_total',
    'Total number of jobs completed',
    ['job_type', 'status', 'tenant_id']
)

jobs_failed_total = Counter(
    'jobs_failed_total',
    'Total number of jobs failed',
    ['job_type', 'error_code', 'tenant_id']
)

job_duration_seconds = Histogram(
    'job_duration_seconds',
    'Job duration in seconds',
    ['job_type', 'status'],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0)
)

job_queue_length = Gauge(
    'job_queue_length',
    'Current number of jobs in queue',
    ['job_type', 'queue_name']
)

# DQ & Compliance Metrics
dq_runs_total = Counter(
    'dq_runs_total',
    'Total number of DQ runs',
    ['status', 'engine', 'tenant_id']
)

compliance_runs_total = Counter(
    'compliance_runs_total',
    'Total number of compliance runs',
    ['status', 'risk_level', 'tenant_id']
)

asset_dq_status = Gauge(
    'asset_dq_status_count',
    'Number of assets by DQ status',
    ['status', 'tenant_id']
)

asset_compliance_status = Gauge(
    'asset_compliance_status_count',
    'Number of assets by compliance status',
    ['status', 'tenant_id']
)

# Database Metrics
db_connections_active = Gauge(
    'db_connections_active',
    'Number of active database connections'
)

db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['operation'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

# Cache/Redis Metrics
cache_hits_total = Counter(
    'cache_hits_total',
    'Total number of cache hits',
    ['cache_key_prefix']
)

cache_misses_total = Counter(
    'cache_misses_total',
    'Total number of cache misses',
    ['cache_key_prefix']
)

# File Storage Metrics
file_uploads_total = Counter(
    'file_uploads_total',
    'Total number of file uploads',
    ['status', 'file_type', 'tenant_id']
)

file_upload_size_bytes = Histogram(
    'file_upload_size_bytes',
    'File upload size in bytes',
    ['file_type'],
    buckets=(1024, 10240, 102400, 1048576, 10485760, 104857600, 1073741824)
)

# Contract Metrics
contract_validations_total = Counter(
    'contract_validations_total',
    'Total number of contract validations',
    ['status', 'spec_type', 'tenant_id']
)

contract_migrations_total = Counter(
    'contract_migrations_total',
    'Total number of contract migrations',
    ['source_version', 'target_version', 'strategy', 'status', 'tenant_id']
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


def metrics_view(request):
    """
    Prometheus metrics endpoint.
    
    Returns:
        HTTP response with Prometheus metrics
    """
    metrics_data = generate_latest()
    return HttpResponse(metrics_data, content_type=CONTENT_TYPE_LATEST)

