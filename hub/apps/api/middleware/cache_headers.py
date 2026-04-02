"""
HTTP Cache Headers Middleware

Middleware for adding HTTP cache headers to API responses:
- ETag headers (from resource version/timestamp)
- Last-Modified headers (from updated_at timestamp)
- Cache-Control headers (public/private, max-age, no-cache)

Supports conditional requests:
- If-None-Match header for 304 Not Modified responses
- If-Modified-Since header for 304 Not Modified responses

Features:
- Automatic ETag generation from resource data
- Configurable cache directives per endpoint/resource type
- Support for public/private caching
- Max-age configuration
- No-cache for sensitive data
"""
import hashlib
import json
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog
from django.http import HttpRequest, HttpResponse, HttpResponseNotModified
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from django.utils.http import http_date, parse_http_date
from django.conf import settings

logger = structlog.get_logger(__name__)

# Default cache control settings
DEFAULT_CACHE_MAX_AGE = getattr(settings, 'CACHE_MAX_AGE', 300)  # 5 minutes
DEFAULT_PUBLIC_CACHE_MAX_AGE = getattr(settings, 'PUBLIC_CACHE_MAX_AGE', 120)  # 2 minutes
DEFAULT_PRIVATE_CACHE_MAX_AGE = getattr(settings, 'PRIVATE_CACHE_MAX_AGE', 300)  # 5 minutes

# Cache control directives per resource type
CACHE_CONTROL_CONFIG = getattr(settings, 'CACHE_CONTROL_CONFIG', {
    'public': {
        'datasets': {'max-age': 300, 'public': True},
        'marketplace/listings': {'max-age': 120, 'public': True},
        'assets': {'max-age': 300, 'public': True},
    },
    'private': {
        'contracts': {'max-age': 300, 'private': True},
        'users': {'max-age': 0, 'no-cache': True, 'private': True},
        'tenants': {'max-age': 0, 'no-cache': True, 'private': True},
    }
})


def generate_etag(data: Any) -> str:
    """
    Generate ETag from resource data.

    Args:
        data: Resource data (dict, list, or serializable object)

    Returns:
        ETag string (weak ETag format: W/"hash")
    """
    try:
        # Serialize data to JSON string
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data, sort_keys=True, default=str)
        else:
            data_str = str(data)

        # Generate MD5 hash
        hash_value = hashlib.md5(data_str.encode('utf-8')).hexdigest()

        # Return weak ETag (W/"hash") - allows for minor variations
        return f'W/"{hash_value}"'
    except Exception as e:
        logger.warning(
            "etag_generation_error",
            error=str(e),
            message="Failed to generate ETag, using timestamp-based fallback"
        )
        # Fallback: use timestamp-based ETag
        timestamp = int(timezone.now().timestamp())
        hash_value = hashlib.md5(str(timestamp).encode('utf-8')).hexdigest()
        return f'W/"{hash_value}"'


def generate_etag_from_model(instance) -> str:
    """
    Generate ETag from Django model instance.

    Uses updated_at timestamp and version fields if available.

    Args:
        instance: Django model instance

    Returns:
        ETag string
    """
    try:
        # Build ETag components
        components = []

        # Use updated_at timestamp if available
        if hasattr(instance, 'updated_at') and instance.updated_at:
            components.append(str(instance.updated_at.timestamp()))

        # Use version fields if available
        if hasattr(instance, 'version_hash') and instance.version_hash:
            components.append(instance.version_hash)
        elif hasattr(instance, 'version') and instance.version:
            components.append(str(instance.version))
        elif hasattr(instance, 'semantic_version') and instance.semantic_version:
            components.append(instance.semantic_version)

        # Use ID as fallback
        if hasattr(instance, 'id'):
            components.append(str(instance.id))

        # Generate hash from components
        if components:
            data_str = ':'.join(components)
            hash_value = hashlib.md5(data_str.encode('utf-8')).hexdigest()
            return f'W/"{hash_value}"'
        else:
            # Fallback: use current timestamp
            timestamp = int(timezone.now().timestamp())
            hash_value = hashlib.md5(str(timestamp).encode('utf-8')).hexdigest()
            return f'W/"{hash_value}"'
    except Exception as e:
        logger.warning(
            "etag_generation_error",
            error=str(e),
            model=instance.__class__.__name__ if hasattr(instance, '__class__') else 'Unknown',
            message="Failed to generate ETag from model"
        )
        # Fallback: use current timestamp
        timestamp = int(timezone.now().timestamp())
        hash_value = hashlib.md5(str(timestamp).encode('utf-8')).hexdigest()
        return f'W/"{hash_value}"'


def get_last_modified(instance) -> Optional[datetime]:
    """
    Get Last-Modified timestamp from model instance.

    Args:
        instance: Django model instance

    Returns:
        datetime object or None
    """
    if hasattr(instance, 'updated_at') and instance.updated_at:
        return instance.updated_at
    elif hasattr(instance, 'created_at') and instance.created_at:
        return instance.created_at
    return None


def get_cache_control_for_path(path: str, is_public: bool = False) -> str:
    """
    Get Cache-Control header value for a given path.

    Args:
        path: Request path
        is_public: Whether resource is public (default: False)

    Returns:
        Cache-Control header value
    """
    # Determine resource type from path
    resource_type = None
    if '/api/v1/datasets/' in path:
        resource_type = 'datasets'
    elif '/api/v1/marketplace/listings/' in path:
        resource_type = 'marketplace/listings'
    elif '/api/v1/assets/' in path:
        resource_type = 'assets'
    elif '/api/v1/contracts/' in path:
        resource_type = 'contracts'
    elif '/api/v1/users/' in path:
        resource_type = 'users'
    elif '/api/v1/tenants/' in path:
        resource_type = 'tenants'

    # Get cache control config (reload from settings to get test overrides)
    cache_control_config = getattr(settings, 'CACHE_CONTROL_CONFIG', CACHE_CONTROL_CONFIG)
    cache_config = None
    if is_public and resource_type in cache_control_config.get('public', {}):
        cache_config = cache_control_config['public'][resource_type]
    elif resource_type in cache_control_config.get('private', {}):
        cache_config = cache_control_config['private'][resource_type]

    # Build Cache-Control directive
    directives = []

    if cache_config:
        if cache_config.get('no-cache'):
            directives.append('no-cache')
        if cache_config.get('private'):
            directives.append('private')
        elif cache_config.get('public'):
            directives.append('public')
        if 'max-age' in cache_config:
            directives.append(f"max-age={cache_config['max-age']}")
    else:
        # Default: private cache with default max-age
        if is_public:
            directives.append('public')
            directives.append(f"max-age={DEFAULT_PUBLIC_CACHE_MAX_AGE}")
        else:
            directives.append('private')
            directives.append(f"max-age={DEFAULT_PRIVATE_CACHE_MAX_AGE}")

    return ', '.join(directives)


def check_if_none_match(request: HttpRequest, etag: str) -> bool:
    """
    Check If-None-Match header against ETag.

    Args:
        request: HTTP request
        etag: Current ETag value

    Returns:
        True if resource is not modified (should return 304)
    """
    if_none_match = request.META.get('HTTP_IF_NONE_MATCH', '')
    if not if_none_match:
        return False

    # Remove weak ETag prefix (W/") if present
    clean_etag = etag.replace('W/"', '').replace('"', '')
    clean_if_none_match = if_none_match.replace('W/"', '').replace('"', '')

    # Check if any of the provided ETags match
    if_none_match_list = [tag.strip() for tag in clean_if_none_match.split(',')]
    return clean_etag in if_none_match_list


def check_if_modified_since(request: HttpRequest, last_modified: datetime) -> bool:
    """
    Check If-Modified-Since header against Last-Modified timestamp.

    Args:
        request: HTTP request
        last_modified: Last-Modified datetime

    Returns:
        True if resource is not modified (should return 304)
    """
    if_modified_since = request.META.get('HTTP_IF_MODIFIED_SINCE', '')
    if not if_modified_since:
        return False

    try:
        if_modified_since_timestamp = parse_http_date(if_modified_since)
        # Parse HTTP date returns UTC timestamp, convert to timezone-aware datetime
        if_modified_since_dt = datetime.fromtimestamp(if_modified_since_timestamp, tz=ZoneInfo('UTC'))
        # Ensure last_modified is timezone-aware (should already be from Django models)
        if timezone.is_naive(last_modified):
            last_modified = timezone.make_aware(last_modified)
        # Convert to UTC for comparison
        if last_modified.tzinfo is None:
            last_modified = timezone.make_aware(last_modified)
        # Resource is not modified if last_modified <= if_modified_since
        return last_modified <= if_modified_since_dt
    except (ValueError, TypeError, AttributeError):
        return False


class CacheHeadersMiddleware(MiddlewareMixin):
    """
    Middleware for adding HTTP cache headers to API responses.

    Features:
    - ETag generation from resource data or model instances
    - Last-Modified headers from updated_at timestamps
    - Cache-Control headers with appropriate directives
    - Support for conditional requests (304 Not Modified)
    """

    def process_response(
        self,
        request: HttpRequest,
        response: HttpResponse
    ) -> HttpResponse:
        """
        Process response to add cache headers.

        Args:
            request: HTTP request object
            response: HTTP response object

        Returns:
            HTTP response with cache headers (or 304 Not Modified if applicable)
        """
        # Only process API GET requests
        if not request.path.startswith('/api/'):
            return response

        if request.method != 'GET':
            return response

        # Skip if response is already 304 or error status
        if response.status_code in (304, 204, 301, 302, 303, 307, 308):
            return response

        # Skip if response is an error
        if response.status_code >= 400:
            return response

        # Try to extract resource data from response
        resource_data = None
        resource_instance = None

        # Try to get model instance from request (set by views)
        if hasattr(request, '_resource_instance'):
            resource_instance = request._resource_instance

        # Check if response has resource data (DRF Response)
        if hasattr(response, 'data'):
            resource_data = response.data

        # Generate ETag
        etag = None
        if resource_instance:
            etag = generate_etag_from_model(resource_instance)
        elif resource_data:
            etag = generate_etag(resource_data)
        else:
            # Fallback: generate ETag from response content
            if hasattr(response, 'content') and response.content:
                try:
                    content_str = response.content.decode('utf-8') if isinstance(response.content, bytes) else str(response.content)
                    etag = generate_etag(content_str)
                except Exception as exc:
                    logger.debug(
                        "cache_etag_content_encode_error",
                        error=str(exc),
                    )

        # Get Last-Modified timestamp
        last_modified = None
        if resource_instance:
            last_modified = get_last_modified(resource_instance)
            # Ensure it's timezone-aware
            if last_modified and timezone.is_naive(last_modified):
                last_modified = timezone.make_aware(last_modified)

        # Check conditional requests
        if etag:
            # Check If-None-Match
            if check_if_none_match(request, etag):
                logger.debug(
                    "cache_conditional_request_not_modified",
                    path=request.path,
                    etag=etag,
                    reason="If-None-Match matched"
                )
                return HttpResponseNotModified()

        if last_modified:
            # Check If-Modified-Since
            if check_if_modified_since(request, last_modified):
                logger.debug(
                    "cache_conditional_request_not_modified",
                    path=request.path,
                    last_modified=last_modified.isoformat(),
                    reason="If-Modified-Since matched"
                )
                return HttpResponseNotModified()

        # Determine if resource is public (for marketplace/public endpoints)
        is_public = (
            '/api/v1/marketplace/listings/' in request.path or
            '/api/v1/marketplace/search' in request.path
        )

        # Add cache headers
        if etag:
            response['ETag'] = etag

        if last_modified:
            response['Last-Modified'] = http_date(last_modified.timestamp())

        # Add Cache-Control header
        cache_control = get_cache_control_for_path(request.path, is_public=is_public)
        if cache_control:
            response['Cache-Control'] = cache_control

        logger.debug(
            "cache_headers_added",
            path=request.path,
            etag=etag,
            last_modified=last_modified.isoformat() if last_modified else None,
            cache_control=cache_control
        )

        return response

