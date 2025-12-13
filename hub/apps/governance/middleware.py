"""
Access Logging Middleware

Middleware for automatic access logging.
"""
from typing import Optional
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, HttpResponse
from .access_analytics import AccessAnalyticsService, AccessLog
from .abac import ABACEngine
import structlog

logger = structlog.get_logger(__name__)


class AccessLoggingMiddleware(MiddlewareMixin):
    """
    Middleware for automatic access logging.
    """
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Log access attempt"""
        # Only log API requests
        if not request.path.startswith('/api/v1/'):
            return response
        
        # Skip logging for analytics endpoints to avoid recursion
        if '/access/analytics' in request.path:
            return response
        
        # Get tenant and user
        tenant_id = None
        user_id = None
        
        if hasattr(request, 'tenant_id') and request.tenant_id:
            tenant_id = str(request.tenant_id)
        elif hasattr(request, 'tenant') and request.tenant:
            tenant_id = str(request.tenant.id)
        
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = str(request.user.id)
        
        if not tenant_id:
            return response  # Skip if no tenant
        
        # Determine resource type and ID from path
        resource_type, resource_id = self._extract_resource_from_path(request.path)
        
        if not resource_type:
            return response  # Skip if can't determine resource
        
        # Determine action from HTTP method
        action = self._get_action_from_method(request.method)
        
        # Determine result from response status
        result = self._get_result_from_status(response.status_code)
        
        # Get IP address and user agent
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        # Log access
        try:
            AccessAnalyticsService.log_access(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                result=result,
                ip_address=ip_address,
                user_agent=user_agent
            )
        except Exception as e:
            logger.warning(
                "access_logging_error",
                error=str(e),
                path=request.path
            )
        
        return response
    
    def _extract_resource_from_path(self, path: str) -> tuple[Optional[str], Optional[str]]:
        """Extract resource type and ID from API path"""
        # Parse common API patterns
        # /api/v1/assets/{id}/
        # /api/v1/datasets/{id}/
        # /api/v1/contracts/{id}/
        # etc.
        
        import re
        parts = path.strip('/').split('/')
        
        if len(parts) >= 3 and parts[0] == 'api' and parts[1] == 'v1':
            resource_type = parts[2].upper().rstrip('S')  # Remove plural 's'
            
            # Try to extract ID from path
            resource_id = None
            if len(parts) >= 4:
                # Check if next part looks like a UUID
                uuid_pattern = re.compile(
                    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
                    re.IGNORECASE
                )
                if uuid_pattern.match(parts[3]):
                    resource_id = parts[3]
            
            if resource_type and resource_id:
                return resource_type, resource_id
        
        return None, None
    
    def _get_action_from_method(self, method: str) -> str:
        """Map HTTP method to action"""
        mapping = {
            'GET': 'READ',
            'POST': 'WRITE',
            'PUT': 'WRITE',
            'PATCH': 'WRITE',
            'DELETE': 'DELETE',
        }
        return mapping.get(method.upper(), 'READ')
    
    def _get_result_from_status(self, status_code: int) -> str:
        """Map HTTP status code to access result"""
        if 200 <= status_code < 300:
            return 'ALLOWED'
        elif status_code == 403:
            return 'DENIED'
        elif status_code == 401:
            return 'DENIED'
        else:
            return 'ALLOWED'  # Other status codes are still considered allowed
    
    def _get_client_ip(self, request: HttpRequest) -> Optional[str]:
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

