from django.http import JsonResponse
from django.db import connection
import redis
from django.conf import settings

def health_check(request):
    """Health check endpoint for Docker and load balancers"""
    status = {
        'status': 'healthy',
        'database': 'unknown',
        'redis': 'unknown',
    }
    
    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        status['database'] = 'connected'
    except Exception as e:
        status['database'] = f'error: {str(e)}'
        status['status'] = 'unhealthy'
    
    # Check Redis
    try:
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        status['redis'] = 'connected'
    except Exception as e:
        status['redis'] = f'error: {str(e)}'
        status['status'] = 'unhealthy'
    
    http_status = 200 if status['status'] == 'healthy' else 503
    return JsonResponse(status, status=http_status)

