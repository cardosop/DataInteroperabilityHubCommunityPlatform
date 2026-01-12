from django.http import JsonResponse
from django.db import connection
from django.conf import settings
from hub.apps.core.redis_pools import health_check_all_redis_instances


def health_check(request):
    """Health check endpoint for Docker and load balancers"""
    status = {
        'status': 'healthy',
        'database': 'unknown',
        'redis': {
            'cache': 'unknown',
            'queue': 'unknown',
            'events': 'unknown',
            'channels': 'unknown',
        },
    }

    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        status['database'] = 'connected'
    except Exception as e:
        status['database'] = f'error: {str(e)}'
        status['status'] = 'unhealthy'

    # Check all Redis instances
    redis_health = health_check_all_redis_instances()
    all_redis_healthy = True
    for instance_name, instance_status in redis_health.items():
        if instance_status['status'] == 'healthy':
            status['redis'][instance_name] = 'connected'
        else:
            status['redis'][instance_name] = f"error: {instance_status.get('error', 'unknown')}"
            all_redis_healthy = False

    if not all_redis_healthy:
        status['status'] = 'unhealthy'

    http_status = 200 if status['status'] == 'healthy' else 503
    return JsonResponse(status, status=http_status)


def circuit_breaker_status(request):
    """
    Circuit breaker status endpoint for monitoring.

    Returns status of all circuit breakers or a specific one if service_name is provided.

    Query parameters:
        service_name: Optional service name to get status for specific circuit breaker
    """
    from hub.apps.core.resilience.circuit_breaker import get_circuit_breaker_status

    service_name = request.GET.get('service_name', None)

    try:
        status = get_circuit_breaker_status(service_name=service_name)

        # Determine overall health based on circuit breaker states
        if isinstance(status, dict) and 'error' in status:
            # Single breaker not found
            return JsonResponse(status, status=404)

        if service_name:
            # Single breaker status
            breaker_status = status
            overall_healthy = breaker_status.get('state') != 'OPEN'
            http_status = 200 if overall_healthy else 503
            return JsonResponse({
                'status': 'healthy' if overall_healthy else 'degraded',
                'circuit_breaker': breaker_status
            }, status=http_status)
        else:
            # All breakers status
            breakers = status
            open_breakers = [
                name for name, breaker_status in breakers.items()
                if breaker_status.get('state') == 'OPEN'
            ]
            overall_healthy = len(open_breakers) == 0

            return JsonResponse({
                'status': 'healthy' if overall_healthy else 'degraded',
                'total_breakers': len(breakers),
                'open_breakers': len(open_breakers),
                'open_breaker_names': open_breakers,
                'circuit_breakers': breakers
            }, status=200)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)

