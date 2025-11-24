"""
API Middleware

Middleware for request ID generation, rate limiting, and request validation.
"""
import uuid
import time
import logging
import structlog
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone

logger = structlog.get_logger(__name__)


class RequestIDMiddleware(MiddlewareMixin):
    """
    Middleware to generate and attach request ID to each request.
    """
    
    def process_request(self, request):
        """Generate request ID if not present"""
        request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        request.id = request_id
        request.request_id = request_id
        
        # Add request_id to structlog context
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            route=request.path,
            method=request.method,
        )
        
        # Add tenant_id and user_id if available (will be set later by auth middleware)
        return None
    
    def process_response(self, request, response):
        """Add request ID to response headers"""
        if hasattr(request, 'request_id'):
            response['X-Request-ID'] = request.request_id
        
        # Add tenant_id and user_id to context if available
        if hasattr(request, 'tenant') and request.tenant:
            structlog.contextvars.bind_contextvars(tenant_id=str(request.tenant.id))
        
        if hasattr(request, 'user') and request.user.is_authenticated:
            structlog.contextvars.bind_contextvars(user_id=str(request.user.id))
        
        return response


class RateLimitMiddleware(MiddlewareMixin):
    """
    Middleware for rate limiting per tenant, per user, and per endpoint.
    """
    
    def process_request(self, request):
        """Check rate limits before processing request"""
        # Skip rate limiting for health checks and admin
        if request.path.startswith('/health/') or request.path.startswith('/admin/'):
            return None
        
        # Skip rate limiting for non-API endpoints
        if not request.path.startswith('/api/v1/'):
            return None
        
        # Get tenant and user from request
        tenant = getattr(request, 'tenant', None)
        tenant_id = str(tenant.id) if tenant and hasattr(tenant, 'id') else (str(tenant) if tenant else None)
        user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None
        
        # Rate limit key components
        endpoint = request.path
        method = request.method
        
        # Build rate limit keys
        keys = []
        if tenant_id:
            keys.append(f'rate_limit:tenant:{tenant_id}:{method}:{endpoint}')
        if user_id:
            keys.append(f'rate_limit:user:{user_id}:{method}:{endpoint}')
        
        # Check rate limits
        for key in keys:
            if not self._check_rate_limit(key, request):
                return JsonResponse(
                    {
                        'error': {
                            'code': 'RATE_LIMIT_EXCEEDED',
                            'message': 'Rate limit exceeded for this endpoint',
                            'http_status': 429,
                            'request_id': getattr(request, 'id', str(uuid.uuid4())),
                            'timestamp': timezone.now().isoformat(),
                            'details': {
                                'limit_type': 'tenant' if 'tenant' in key else 'user',
                                'retry_after': 60
                            }
                        }
                    },
                    status=429
                )
        
        return None
    
    def _check_rate_limit(self, key, request):
        """
        Check if rate limit is exceeded.
        
        Args:
            key: Rate limit cache key
            request: HTTP request object
            
        Returns:
            True if within limit, False if exceeded
        """
        # Get rate limit configuration from settings
        from django.conf import settings
        limit = getattr(settings, 'RATE_LIMIT_PER_TENANT', 100) if 'tenant' in key else getattr(settings, 'RATE_LIMIT_PER_USER', 100)
        window = getattr(settings, 'RATE_LIMIT_WINDOW', 60)
        
        # Check if rate limiting is enabled
        if not getattr(settings, 'RATE_LIMIT_ENABLED', True):
            return True
        
        # Get current count
        count = cache.get(key, 0)
        
        if count >= limit:
            # Rate limit exceeded
            ttl = cache.ttl(key)
            if ttl is None:
                ttl = window
            
            # Add retry-after header
            request.retry_after = ttl
            return False
        
        # Increment counter
        cache.set(key, count + 1, window)
        return True
    
    def process_response(self, request, response):
        """Add rate limit headers to response"""
        if hasattr(request, 'retry_after'):
            response['Retry-After'] = str(request.retry_after)
        
        # Add rate limit headers
        if request.path.startswith('/api/v1/'):
            from django.conf import settings
            
            tenant_id = getattr(request, 'tenant', None)
            if tenant_id:
                tenant_id = str(tenant_id.id) if hasattr(tenant_id, 'id') else str(tenant_id)
            
            user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None
            
            # Always add tenant-level rate limit headers (use default if no tenant)
            limit = getattr(settings, 'RATE_LIMIT_PER_TENANT', 100)
            if tenant_id:
                key = f'rate_limit:tenant:{tenant_id}:{request.method}:{request.path}'
                count = cache.get(key, 0)
            else:
                # Default limit when no tenant (for unauthenticated or system requests)
                count = 0
            response['X-RateLimit-Limit'] = str(limit)
            response['X-RateLimit-Remaining'] = str(max(0, limit - count))
            
            # Add user-level rate limit headers if user is authenticated
            if user_id:
                key = f'rate_limit:user:{user_id}:{request.method}:{request.path}'
                count = cache.get(key, 0)
                limit = getattr(settings, 'RATE_LIMIT_PER_USER', 100)
                response['X-RateLimit-User-Limit'] = str(limit)
                response['X-RateLimit-User-Remaining'] = str(max(0, limit - count))
        
        return response

