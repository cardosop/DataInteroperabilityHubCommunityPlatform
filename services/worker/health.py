"""
Health check endpoints for worker service.

Implements /healthz (liveness) and /ready (readiness) probes following Kubernetes standards.
"""
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
import redis


def healthz(request=None):
    """
    Liveness probe endpoint.
    
    Returns 200 OK if worker process is running (no deep checks).
    Used by Kubernetes to determine if container should be restarted.
    
    GET /healthz
    
    Args:
        request: Django request object (optional, not used)
    
    Returns:
        If request is None: (status_code, response_data) tuple
        If request is provided: JsonResponse
    """
    response_data = {
        'status': 'ok',
        'service': 'worker-service',
        'timestamp': timezone.now().isoformat()
    }
    # Return tuple for HTTP server, or JsonResponse for Django
    if request is not None:
        return JsonResponse(response_data, status=200)
    return (200, response_data)


def ready(request=None):
    """
    Readiness probe endpoint.
    
    Returns 200 OK if all dependencies are ready (database, Redis).
    Returns 503 if any dependency is unavailable.
    Used by Kubernetes to determine if service can accept traffic.
    
    GET /ready
    
    Args:
        request: Django request object (optional, not used)
    """
    checks = {}
    all_ready = True
    
    # Check database connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks['database'] = 'ok'
    except Exception as e:
        checks['database'] = f'unhealthy: {str(e)}'
        all_ready = False
    
    # Check Redis connection (required for job queues)
    try:
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        checks['redis'] = 'ok'
    except Exception as e:
        checks['redis'] = f'unhealthy: {str(e)}'
        all_ready = False
    
    # Check cache backend (may be same as Redis)
    try:
        cache.get('health_check_test', None)
        checks['cache'] = 'ok'
    except Exception as e:
        checks['cache'] = f'unhealthy: {str(e)}'
        all_ready = False
    
    if all_ready:
        response_data = {
            'status': 'ready',
            'service': 'worker-service',
            'checks': checks,
            'timestamp': timezone.now().isoformat()
        }
        if request is not None:
            return JsonResponse(response_data, status=200)
        return (200, response_data)
    else:
        error_msg = "; ".join([f"{k}: {v}" for k, v in checks.items() if "unhealthy" in v])
        response_data = {
            'status': 'not_ready',
            'service': 'worker-service',
            'checks': checks,
            'error': error_msg,
            'timestamp': timezone.now().isoformat()
        }
        if request is not None:
            return JsonResponse(response_data, status=503)
        return (503, response_data)

