"""
Idempotency Middleware

Middleware for handling idempotency keys in API requests.
Prevents duplicate operations by caching responses for idempotency keys.

Features:
- Extracts Idempotency-Key header from requests
- Validates idempotency key format (UUID or custom format)
- Checks Redis for existing idempotency key
- Returns cached response if key exists (within TTL window)
- Stores request/response in Redis if new key
- Handles concurrent requests with same key (lock mechanism)
"""
import json
import time
from typing import Callable, Optional

import structlog
import redis
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin

from .idempotency_utils import (
    validate_idempotency_key,
    normalize_idempotency_key,
    get_redis_client,
    build_idempotency_key,
    build_lock_key,
    hash_request_body,
    serialize_response,
    deserialize_response,
    store_idempotency_record,
    get_idempotency_record,
    check_idempotency_key_expired,
    acquire_lock,
    release_lock,
    get_idempotency_ttl,
    should_process_idempotency,
    get_endpoint_pattern,
    IdempotencyKeyFormatError,
)

logger = structlog.get_logger(__name__)


class IdempotencyMiddleware(MiddlewareMixin):
    """
    Middleware for handling idempotency keys in API requests.

    Processes requests with Idempotency-Key header:
    1. Validates idempotency key format
    2. Checks Redis for existing cached response
    3. Returns cached response if found
    4. Otherwise processes request and caches response

    Only processes:
    - POST, PUT, PATCH methods
    - API endpoints (/api/v1/)
    - Requests with Idempotency-Key header
    """

    def __init__(self, get_response: Callable):
        """Initialize middleware with get_response callable."""
        super().__init__(get_response)
        self.get_response = get_response
        self._redis_client = None

    @property
    def redis_client(self) -> Optional[redis.Redis]:
        """
        Get Redis client with lazy initialization.

        Returns:
            Redis client instance or None if unavailable
        """
        if self._redis_client is None:
            try:
                self._redis_client = get_redis_client()
            except redis.ConnectionError as e:
                logger.warning(
                    "idempotency_redis_unavailable",
                    error=str(e),
                    message="Idempotency middleware will fail open"
                )
                return None
        return self._redis_client

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Process request for idempotency.

        Args:
            request: HTTP request object

        Returns:
            Cached HttpResponse if idempotency key exists, None otherwise
        """
        # Check if should process this request
        if not should_process_idempotency(request):
            return None

        # Get idempotency key from header
        idempotency_key = request.headers.get('Idempotency-Key')
        if not idempotency_key:
            return None

        # Validate key format
        try:
            normalized_key = normalize_idempotency_key(idempotency_key)
        except IdempotencyKeyFormatError as e:
            logger.warning(
                "idempotency_key_invalid",
                key=idempotency_key,
                error=str(e)
            )
            return JsonResponse(
                {
                    'error': {
                        'code': 'INVALID_IDEMPOTENCY_KEY',
                        'message': str(e),
                        'http_status': 400
                    }
                },
                status=400
            )

        # Get Redis client
        redis_client = self.redis_client
        if redis_client is None:
            # Fail open: process request normally if Redis unavailable
            logger.warning(
                "idempotency_redis_unavailable",
                error="Failed to connect to Redis",
                message="Idempotency middleware will fail open - processing request without idempotency check"
            )
            return None

        # Build Redis keys
        tenant_id = None
        if hasattr(request, 'tenant') and request.tenant:
            tenant_id = str(request.tenant.id)

        endpoint = get_endpoint_pattern(request.path)
        redis_key = build_idempotency_key(
            normalized_key,
            endpoint,
            request.method,
            tenant_id=tenant_id
        )
        lock_key = build_lock_key(redis_key)

        # Check for existing record
        try:
            record = get_idempotency_record(redis_client, redis_key)
        except redis.RedisError as e:
            # Redis operation failed - fail open
            logger.error(
                "idempotency_redis_error",
                error=str(e),
                redis_key=redis_key,
                message="Redis operation failed - processing request without idempotency check"
            )
            return None

        # Check if key was previously used but has expired
        if record is None:
            try:
                # Check if key exists but has expired (for 410 Gone response)
                if check_idempotency_key_expired(redis_client, redis_key):
                    logger.warning(
                        "idempotency_key_expired",
                        idempotency_key=normalized_key,
                        endpoint=endpoint,
                        method=request.method
                    )
                    return JsonResponse(
                        {
                            'error': {
                                'code': 'IDEMPOTENCY_KEY_EXPIRED',
                                'message': (
                                    'Idempotency key has expired. '
                                    'The cached response is no longer available. '
                                    'Use a new idempotency key to retry the request.'
                                ),
                                'http_status': 410
                            }
                        },
                        status=410
                    )
            except redis.RedisError as e:
                # Redis operation failed - fail open
                logger.error(
                    "idempotency_redis_error",
                    error=str(e),
                    redis_key=redis_key,
                    message="Redis TTL check failed - processing request without idempotency check"
                )
                # Continue processing as new request

        if record:
            # Verify request body matches (idempotency key + same body = same response)
            request_hash = hash_request_body(self._get_request_body(request))

            if record.get('request_hash') == request_hash:
                # Return cached response
                logger.info(
                    "idempotency_cache_hit",
                    idempotency_key=normalized_key,
                    endpoint=endpoint,
                    method=request.method
                )

                cached_response = record.get('response', {})
                status_code, body, headers = deserialize_response(cached_response)

                response = JsonResponse(body, status=status_code)

                # Add idempotency headers
                response['Idempotency-Key'] = normalized_key
                response['Idempotency-Replayed'] = 'true'

                # Add cached headers
                for header_name, header_value in headers.items():
                    if header_name.lower() not in ('content-type', 'content-length'):
                        response[header_name] = header_value

                return response
            else:
                # Request body mismatch - conflict error
                logger.warning(
                    "idempotency_conflict",
                    idempotency_key=normalized_key,
                    endpoint=endpoint,
                    method=request.method,
                    message="Request body does not match cached request"
                )
                response = JsonResponse(
                    {
                        'error': {
                            'code': 'IDEMPOTENCY_CONFLICT',
                            'message': (
                                'Idempotency key already used with different request body. '
                                'Use a different key or ensure request body matches.'
                            ),
                            'http_status': 409
                        }
                    },
                    status=409
                )
                # Add Idempotency-Key header even for conflict errors
                response['Idempotency-Key'] = normalized_key
                return response

        # No existing record - acquire lock for concurrent requests
        lock_acquired = acquire_lock(redis_client, lock_key, timeout=10, expire=30)

        if not lock_acquired:
            # Another request is processing - wait and check again
            logger.info(
                "idempotency_lock_wait",
                idempotency_key=normalized_key,
                endpoint=endpoint
            )

            # Wait a bit and check again
            time.sleep(0.5)
            record = get_idempotency_record(redis_client, redis_key)

            if record:
                # Other request completed - return cached response
                cached_response = record.get('response', {})
                status_code, body, headers = deserialize_response(cached_response)

                response = JsonResponse(body, status=status_code)
                response['Idempotency-Key'] = normalized_key
                response['Idempotency-Replayed'] = 'true'

                return response

        # Store lock info in request for cleanup in process_response
        request._idempotency_lock_key = lock_key if lock_acquired else None
        request._idempotency_redis_key = redis_key
        request._idempotency_key = normalized_key

        # Process request normally
        return None

    def process_response(
        self,
        request: HttpRequest,
        response: HttpResponse
    ) -> HttpResponse:
        """
        Process response to cache idempotency result.

        Args:
            request: HTTP request object
            response: HTTP response object

        Returns:
            HTTP response with idempotency headers
        """
        # Check if this request was processed for idempotency
        if not hasattr(request, '_idempotency_redis_key'):
            return response

        redis_key = request._idempotency_redis_key
        idempotency_key = request._idempotency_key
        lock_key = getattr(request, '_idempotency_lock_key', None)

        # Get Redis client
        redis_client = self.redis_client
        if redis_client is None:
            return response

        try:
            # Only cache successful responses (2xx status codes)
            if 200 <= response.status_code < 300:
                # Serialize response
                response_data = serialize_response(response)

                # Hash request body
                request_hash = hash_request_body(self._get_request_body(request))

                # Store idempotency record
                ttl = get_idempotency_ttl()
                try:
                    store_idempotency_record(
                        redis_client,
                        redis_key,
                        request_hash,
                        response_data,
                        ttl=ttl
                    )

                    logger.info(
                        "idempotency_stored",
                        idempotency_key=idempotency_key,
                        endpoint=request.path,
                        method=request.method,
                        status_code=response.status_code,
                        ttl=ttl
                    )
                except redis.RedisError as e:
                    # Redis storage failed - log but don't fail request
                    logger.error(
                        "idempotency_storage_error",
                        error=str(e),
                        idempotency_key=idempotency_key,
                        redis_key=redis_key,
                        message="Failed to store idempotency record - request processed but not cached"
                    )

            # Add idempotency headers
            response['Idempotency-Key'] = idempotency_key

        except Exception as e:
            logger.error(
                "idempotency_storage_error",
                error=str(e),
                idempotency_key=idempotency_key,
                redis_key=redis_key,
                message="Unexpected error during idempotency storage"
            )
            # Don't fail the request if caching fails

        finally:
            # Release lock if acquired
            if lock_key:
                try:
                    release_lock(redis_client, lock_key)
                except Exception as e:
                    logger.error(
                        "idempotency_lock_release_error",
                        error=str(e),
                        lock_key=lock_key
                    )

        return response

    def _get_request_body(self, request: HttpRequest) -> any:
        """
        Get request body for hashing.

        Args:
            request: HTTP request object

        Returns:
            Request body (dict, list, or string)
        """
        # Try to get parsed body from DRF (DRF Request objects have .data)
        if hasattr(request, 'data'):
            return request.data

        # Fallback to raw body (for plain Django requests)
        if hasattr(request, 'body') and request.body:
            try:
                return json.loads(request.body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return request.body.decode('utf-8', errors='replace')

        return None

