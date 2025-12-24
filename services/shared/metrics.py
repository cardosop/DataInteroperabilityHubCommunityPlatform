"""
Shared Prometheus Metrics for FastAPI Services

Provides common metrics collection utilities for all FastAPI services.
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from typing import Optional
import time
from functools import wraps


# HTTP Request Metrics (for FastAPI services)
http_requests_total = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['service', 'method', 'route', 'status_class']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['service', 'method', 'route', 'status_class'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

http_errors_total = Counter(
    'http_errors_total',
    'Total number of HTTP errors',
    ['service', 'method', 'route', 'status_code']
)

# Semantic Service Metrics
sparql_queries_total = Counter(
    'sparql_queries_total',
    'Total number of SPARQL queries',
    ['service', 'status', 'tenant_id']
)

sparql_query_duration_seconds = Histogram(
    'sparql_query_duration_seconds',
    'SPARQL query duration in seconds',
    ['service', 'status'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
)

mapping_operations_total = Counter(
    'mapping_operations_total',
    'Total number of mapping operations',
    ['service', 'operation_type', 'status', 'tenant_id']
)

mapping_operation_duration_seconds = Histogram(
    'mapping_operation_duration_seconds',
    'Mapping operation duration in seconds',
    ['service', 'operation_type', 'status'],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
)

fuseki_interactions_total = Counter(
    'fuseki_interactions_total',
    'Total number of Fuseki interactions',
    ['service', 'operation', 'status']
)

# DQ Service Metrics
dq_runs_total = Counter(
    'dq_runs_total',
    'Total number of DQ runs',
    ['service', 'status', 'engine', 'tenant_id']
)

dq_run_duration_seconds = Histogram(
    'dq_run_duration_seconds',
    'DQ run duration in seconds',
    ['service', 'status', 'engine'],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0)
)

dq_success_rate = Gauge(
    'dq_success_rate',
    'DQ run success rate (0-1)',
    ['service', 'engine']
)

# Compliance Service Metrics
compliance_runs_total = Counter(
    'compliance_runs_total',
    'Total number of compliance runs',
    ['service', 'status', 'risk_level', 'tenant_id']
)

compliance_run_duration_seconds = Histogram(
    'compliance_run_duration_seconds',
    'Compliance run duration in seconds',
    ['service', 'status', 'risk_level'],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0)
)

compliance_success_rate = Gauge(
    'compliance_success_rate',
    'Compliance run success rate (0-1)',
    ['service']
)

# DataContract Service Metrics
contract_validations_total = Counter(
    'contract_validations_total',
    'Total number of contract validations',
    ['service', 'status', 'spec_type', 'tenant_id']
)

contract_validation_duration_seconds = Histogram(
    'contract_validation_duration_seconds',
    'Contract validation duration in seconds',
    ['service', 'status', 'spec_type'],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
)

contract_lint_operations_total = Counter(
    'contract_lint_operations_total',
    'Total number of contract lint operations',
    ['service', 'status', 'tenant_id']
)

contract_convert_operations_total = Counter(
    'contract_convert_operations_total',
    'Total number of contract convert operations',
    ['service', 'status', 'source_format', 'target_format', 'tenant_id']
)

# ODPS Semantic Mapping Metrics (Task 6.6.3)
odps_semantic_mapping_duration_seconds = Histogram(
    'odps_semantic_mapping_duration_seconds',
    'ODPS semantic mapping duration in seconds',
    ['service', 'status'],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
)

odps_semantic_mapping_total = Counter(
    'odps_semantic_mapping_total',
    'Total number of ODPS semantic mapping operations',
    ['service', 'status', 'tenant_id']
)

odps_semantic_mapping_success_rate = Gauge(
    'odps_semantic_mapping_success_rate',
    'ODPS semantic mapping success rate (0-1)',
    ['service', 'tenant_id']
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

