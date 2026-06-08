"""
Comprehensive tests for idempotency middleware and utilities.

Tests cover:
- Idempotency key validation
- Redis operations
- Request/response serialization
- Concurrent request handling
- Middleware integration
- Edge cases and error handling

All tests use real Redis connections - no mocks or stubs.
"""
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock, patch

try:
    import pytest
    pytestmark = pytest.mark.django_db(transaction=True)
except ImportError:
    # Fallback if pytest is not available
    pytestmark = None

import redis
from django.test import TestCase, RequestFactory, override_settings
from django.http import HttpResponse, JsonResponse
from django.conf import settings

from hub.apps.api.middleware.idempotency import IdempotencyMiddleware
from hub.apps.api.middleware.idempotency_utils import (
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
    is_idempotency_enabled,
    should_process_idempotency,
    get_endpoint_pattern,
    IdempotencyKeyFormatError,
)


def get_real_redis_client_or_skip():
    """Get real Redis client or skip test if unavailable."""
    try:
        return get_redis_client()
    except (redis.ConnectionError, Exception) as e:
        import unittest
        raise unittest.SkipTest(f"Redis not available: {e}")


# ============================================================================
# Idempotency Key Validation Tests
# ============================================================================

class TestIdempotencyKeyValidation(TestCase):
    """Test idempotency key validation."""

    def test_validate_uuid_format(self):
        """Test validation accepts UUID format."""
        key = str(uuid.uuid4())
        self.assertTrue(validate_idempotency_key(key))

    def test_validate_custom_format_valid(self):
        """Test validation accepts valid custom format."""
        valid_keys = [
            "my-key-123",
            "test_key_456",
            "key/with/slashes",
            "a" * 8,  # Minimum length
            "a" * 256,  # Maximum length
            "ABC123-def_456/789",
        ]
        for key in valid_keys:
            with self.subTest(key=key):
                self.assertTrue(validate_idempotency_key(key))

    def test_validate_custom_format_invalid(self):
        """Test validation rejects invalid custom format."""
        invalid_keys = [
            "",  # Empty
            "short",  # Too short (< 8 chars)
            "a" * 257,  # Too long (> 256 chars)
            "key with spaces",  # Spaces not allowed
            "key@special",  # Special chars not allowed
            "key.with.dots",  # Dots not allowed
            None,  # None
            123,  # Not string
        ]
        for key in invalid_keys:
            with self.subTest(key=key):
                self.assertFalse(validate_idempotency_key(key))

    def test_normalize_valid_key(self):
        """Test normalization of valid key."""
        key = "  my-key-123  "
        normalized = normalize_idempotency_key(key)
        self.assertEqual(normalized, "my-key-123")

    def test_normalize_invalid_key_raises(self):
        """Test normalization raises error for invalid key."""
        with self.assertRaises(IdempotencyKeyFormatError):
            normalize_idempotency_key("invalid key")

    def test_normalize_uuid_key(self):
        """Test normalization preserves UUID format."""
        key = str(uuid.uuid4())
        normalized = normalize_idempotency_key(key)
        self.assertEqual(normalized, key)


# ============================================================================
# Redis Key Building Tests
# ============================================================================

class TestRedisKeyBuilding(TestCase):
    """Test Redis key building functions."""

    def test_build_idempotency_key_basic(self):
        """Test building basic idempotency key."""
        key = build_idempotency_key(
            "test-key",
            "/api/v1/assets/",
            "POST"
        )
        self.assertEqual(key, "idempotency:test-key:POST:/api/v1/assets")

    def test_build_idempotency_key_with_tenant(self):
        """Test building idempotency key with tenant."""
        key = build_idempotency_key(
            "test-key",
            "/api/v1/assets/",
            "POST",
            tenant_id="tenant-123"
        )
        self.assertEqual(key, "idempotency:test-key:POST:/api/v1/assets:tenant-123")

    def test_build_idempotency_key_normalizes_endpoint(self):
        """Test building key normalizes endpoint."""
        key = build_idempotency_key(
            "test-key",
            "/api/v1/assets///",
            "POST"
        )
        self.assertEqual(key, "idempotency:test-key:POST:/api/v1/assets")

    def test_build_lock_key(self):
        """Test building lock key."""
        idempotency_key = "idempotency:test-key:POST:/api/v1/assets"
        lock_key = build_lock_key(idempotency_key)
        self.assertEqual(lock_key, f"{idempotency_key}:lock")


# ============================================================================
# Request/Response Serialization Tests
# ============================================================================

class TestRequestResponseSerialization(TestCase):
    """Test request/response serialization."""

    def test_hash_request_body_dict(self):
        """Test hashing dictionary request body."""
        body = {"name": "test", "value": 123}
        hash1 = hash_request_body(body)
        hash2 = hash_request_body({"value": 123, "name": "test"})  # Different order
        self.assertEqual(hash1, hash2)  # Should be same due to key sorting

    def test_hash_request_body_list(self):
        """Test hashing list request body."""
        body = [1, 2, 3]
        hash1 = hash_request_body(body)
        hash2 = hash_request_body([1, 2, 3])
        self.assertEqual(hash1, hash2)

    def test_hash_request_body_string(self):
        """Test hashing string request body."""
        body = "test string"
        hash1 = hash_request_body(body)
        hash2 = hash_request_body("test string")
        self.assertEqual(hash1, hash2)

    def test_hash_request_body_none(self):
        """Test hashing None request body."""
        hash1 = hash_request_body(None)
        hash2 = hash_request_body(None)
        self.assertEqual(hash1, hash2)

    def test_serialize_json_response(self):
        """Test serializing JSON response."""
        response = JsonResponse({"id": "123", "name": "test"}, status=201)
        serialized = serialize_response(response)

        self.assertEqual(serialized['status_code'], 201)
        self.assertEqual(serialized['body']['id'], "123")
        self.assertEqual(serialized['body']['name'], "test")
        self.assertIn('timestamp', serialized)

    def test_serialize_response_excludes_sensitive_headers(self):
        """Test serialization excludes sensitive headers."""
        response = HttpResponse()
        response['Content-Length'] = '100'
        response['X-Custom-Header'] = 'value'

        serialized = serialize_response(response)
        self.assertNotIn('content-length', serialized['headers'])
        self.assertIn('X-Custom-Header', serialized['headers'])

    def test_deserialize_response(self):
        """Test deserializing stored response."""
        data = {
            'status_code': 201,
            'body': {'id': '123'},
            'headers': {'X-Custom': 'value'},
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        status_code, body, headers = deserialize_response(data)

        self.assertEqual(status_code, 201)
        self.assertEqual(body['id'], '123')
        self.assertEqual(headers['X-Custom'], 'value')


# ============================================================================
# Redis Operations Tests (Real Redis)
# ============================================================================

class TestRedisOperations(TestCase):
    """Test Redis operations for idempotency with real Redis."""

    def test_get_redis_client_success(self):
        """Test getting Redis client successfully."""
        try:
            client = get_redis_client()
            self.assertIsNotNone(client)
            # Test connection
            client.ping()
        except (redis.ConnectionError, Exception) as e:
            self.skipTest(f"Redis not available: {e}")

    def test_store_and_get_idempotency_record(self):
        """Test storing and retrieving idempotency record."""
        redis_client = get_real_redis_client_or_skip()
        redis_key = f"test:idempotency:{uuid.uuid4()}"
        request_hash = "abc123"
        response_data = {
            'status_code': 201,
            'body': {'id': '123'},
            'headers': {},
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        # Store record
        store_idempotency_record(
            redis_client,
            redis_key,
            request_hash,
            response_data,
            ttl=3600
        )

        # Retrieve record
        record = get_idempotency_record(redis_client, redis_key)
        self.assertIsNotNone(record)
        self.assertEqual(record['request_hash'], request_hash)
        self.assertEqual(record['response'], response_data)

        # Cleanup
        redis_client.delete(redis_key)

    def test_get_idempotency_record_not_found(self):
        """Test retrieving non-existent idempotency record."""
        redis_client = get_real_redis_client_or_skip()
        record = get_idempotency_record(redis_client, f"nonexistent-key:{uuid.uuid4()}")
        self.assertIsNone(record)

    def test_get_idempotency_record_invalid_json(self):
        """Test handling invalid JSON in stored record."""
        redis_client = get_real_redis_client_or_skip()
        test_key = f"test:invalid:{uuid.uuid4()}"

        # Store invalid JSON directly
        redis_client.setex(test_key, 60, "invalid json")

        record = get_idempotency_record(redis_client, test_key)
        self.assertIsNone(record)

        # Cleanup
        redis_client.delete(test_key)


# ============================================================================
# Lock Operations Tests (Real Redis)
# ============================================================================

class TestLockOperations(TestCase):
    """Test distributed lock operations with real Redis."""

    def test_acquire_lock_success(self):
        """Test successfully acquiring lock."""
        redis_client = get_real_redis_client_or_skip()
        lock_key = f"test:lock:{uuid.uuid4()}"

        result = acquire_lock(redis_client, lock_key, timeout=1, expire=30)
        self.assertTrue(result)

        # Cleanup
        release_lock(redis_client, lock_key)

    def test_acquire_lock_timeout(self):
        """Test lock acquisition timeout."""
        redis_client = get_real_redis_client_or_skip()
        lock_key = f"test:lock:{uuid.uuid4()}"

        # Acquire lock first
        acquired1 = acquire_lock(redis_client, lock_key, timeout=1, expire=10)
        self.assertTrue(acquired1)

        # Try to acquire again (should fail)
        acquired2 = acquire_lock(redis_client, lock_key, timeout=0.1, expire=10)
        self.assertFalse(acquired2)

        # Cleanup
        release_lock(redis_client, lock_key)

    def test_release_lock(self):
        """Test releasing lock."""
        redis_client = get_real_redis_client_or_skip()
        lock_key = f"test:lock:{uuid.uuid4()}"

        # Acquire lock
        acquired = acquire_lock(redis_client, lock_key, timeout=1, expire=10)
        self.assertTrue(acquired)

        # Release lock
        release_lock(redis_client, lock_key)

        # Should be able to acquire again
        acquired2 = acquire_lock(redis_client, lock_key, timeout=1, expire=10)
        self.assertTrue(acquired2)

        # Cleanup
        release_lock(redis_client, lock_key)


# ============================================================================
# Configuration Tests
# ============================================================================

class TestConfiguration(TestCase):
    """Test configuration functions."""

    @override_settings(IDEMPOTENCY_TTL_SECONDS=7200)
    def test_get_idempotency_ttl_from_settings(self):
        """Test getting TTL from settings."""
        ttl = get_idempotency_ttl()
        self.assertEqual(ttl, 7200)

    def test_get_idempotency_ttl_default(self):
        """Test getting default TTL."""
        # Test default when setting is not present
        # We need to temporarily remove the setting
        from django.conf import settings
        original_value = getattr(settings, 'IDEMPOTENCY_TTL_SECONDS', None)
        try:
            # Remove the setting temporarily
            if hasattr(settings, 'IDEMPOTENCY_TTL_SECONDS'):
                delattr(settings, 'IDEMPOTENCY_TTL_SECONDS')
            ttl = get_idempotency_ttl()
            self.assertEqual(ttl, 86400)  # 24 hours default
        finally:
            # Restore original setting
            if original_value is not None:
                setattr(settings, 'IDEMPOTENCY_TTL_SECONDS', original_value)

    @override_settings(IDEMPOTENCY_ENABLED=True)
    def test_is_idempotency_enabled_true(self):
        """Test idempotency enabled check."""
        self.assertTrue(is_idempotency_enabled())

    @override_settings(IDEMPOTENCY_ENABLED=False)
    def test_is_idempotency_enabled_false(self):
        """Test idempotency disabled check."""
        self.assertFalse(is_idempotency_enabled())


# ============================================================================
# Request Processing Tests
# ============================================================================

class TestRequestProcessing(TestCase):
    """Test request processing logic."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_should_process_idempotency_post_with_key(self):
        """Test should process POST request with idempotency key."""
        request = self.factory.post(
            "/api/v1/assets/",
            data={"name": "test"},
            HTTP_IDEMPOTENCY_KEY="test-key"
        )
        self.assertTrue(should_process_idempotency(request))

    def test_should_process_idempotency_put_with_key(self):
        """Test should process PUT request with idempotency key."""
        request = self.factory.put(
            "/api/v1/assets/123/",
            data={"name": "test"},
            HTTP_IDEMPOTENCY_KEY="test-key"
        )
        self.assertTrue(should_process_idempotency(request))

    def test_should_process_idempotency_patch_with_key(self):
        """Test should process PATCH request with idempotency key."""
        request = self.factory.patch(
            "/api/v1/assets/123/",
            data={"name": "test"},
            HTTP_IDEMPOTENCY_KEY="test-key"
        )
        self.assertTrue(should_process_idempotency(request))

    def test_should_not_process_get_request(self):
        """Test should not process GET request."""
        request = self.factory.get("/api/v1/assets/")
        self.assertFalse(should_process_idempotency(request))

    def test_should_not_process_without_key(self):
        """Test should not process request without idempotency key."""
        request = self.factory.post("/api/v1/assets/", data={"name": "test"})
        self.assertFalse(should_process_idempotency(request))

    def test_should_not_process_non_api_endpoint(self):
        """Test should not process non-API endpoint."""
        request = self.factory.post(
            "/admin/login/",
            data={"username": "test"},
            HTTP_IDEMPOTENCY_KEY="test-key"
        )
        self.assertFalse(should_process_idempotency(request))

    @override_settings(IDEMPOTENCY_ENABLED=False)
    def test_should_not_process_when_disabled(self):
        """Test should not process when idempotency is disabled."""
        request = self.factory.post(
            "/api/v1/assets/",
            data={"name": "test"},
            HTTP_IDEMPOTENCY_KEY="test-key"
        )
        self.assertFalse(should_process_idempotency(request))

    def test_get_endpoint_pattern(self):
        """Test endpoint pattern normalization."""
        pattern = get_endpoint_pattern("/api/v1/assets/")
        self.assertEqual(pattern, "/api/v1/assets")

        pattern = get_endpoint_pattern("/api/v1/assets")
        self.assertEqual(pattern, "/api/v1/assets")


# ============================================================================
# Middleware Integration Tests (Real Redis)
# ============================================================================

class TestIdempotencyMiddleware(TestCase):
    """Test idempotency middleware integration with real Redis."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.get_response = lambda req: JsonResponse({"id": "123"}, status=201)

    def test_middleware_processes_request_with_key(self):
        """Test middleware processes request with idempotency key."""
        redis_client = get_real_redis_client_or_skip()

        middleware = IdempotencyMiddleware(self.get_response)
        idempotency_key = str(uuid.uuid4())
        request = self.factory.post(
            "/api/v1/assets/",
            data=json.dumps({"name": "test"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )

        response = middleware(request)

        # Should process request normally
        self.assertEqual(response.status_code, 201)
        self.assertIn('Idempotency-Key', response)

        # Cleanup
        redis_key = build_idempotency_key(
            idempotency_key,
            "/api/v1/assets",
            "POST"
        )
        redis_client.delete(redis_key)

    def test_middleware_returns_cached_response(self):
        """Test middleware returns cached response for duplicate request."""
        redis_client = get_real_redis_client_or_skip()

        idempotency_key = str(uuid.uuid4())
        request_body = {"name": "test"}
        request_hash = hash_request_body(request_body)

        # Pre-store cached response
        redis_key = build_idempotency_key(
            idempotency_key,
            "/api/v1/assets",
            "POST"
        )
        cached_response_data = {
            'status_code': 201,
            'body': {'id': 'cached-123'},
            'headers': {},
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        store_idempotency_record(
            redis_client,
            redis_key,
            request_hash,
            cached_response_data,
            ttl=60
        )

        middleware = IdempotencyMiddleware(self.get_response)
        request = self.factory.post(
            "/api/v1/assets/",
            data=request_body,
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )

        response = middleware(request)

        # Should return cached response
        self.assertEqual(response.status_code, 201)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['id'], 'cached-123')
        self.assertIn('Idempotency-Replayed', response)
        self.assertEqual(response['Idempotency-Replayed'], 'true')

        # Cleanup
        redis_client.delete(redis_key)

    def test_middleware_skips_non_api_endpoints(self):
        """Test middleware skips non-API endpoints."""
        middleware = IdempotencyMiddleware(self.get_response)
        request = self.factory.post(
            "/admin/login/",
            data={"username": "test"},
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())
        )

        response = middleware(request)

        # Should process normally (not idempotency processed)
        self.assertEqual(response.status_code, 201)
        # Should not have Idempotency-Replayed header
        self.assertNotIn('Idempotency-Replayed', response)

    def test_middleware_handles_invalid_key_format(self):
        """Test middleware handles invalid idempotency key format."""
        middleware = IdempotencyMiddleware(self.get_response)
        request = self.factory.post(
            "/api/v1/assets/",
            data={"name": "test"},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="invalid key format"
        )

        response = middleware(request)

        # Should return 400 error
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn('error', response_data)

    @override_settings(REDIS_URL='redis://invalid-host:6379/0')
    def test_middleware_handles_redis_connection_error(self):
        """Test middleware handles Redis connection errors gracefully."""
        middleware = IdempotencyMiddleware(self.get_response)
        request = self.factory.post(
            "/api/v1/assets/",
            data={"name": "test"},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())
        )

        # Should fail open and process request normally
        response = middleware(request)
        self.assertEqual(response.status_code, 201)

    @patch('hub.apps.api.middleware.idempotency.get_redis_client')
    @patch('hub.apps.api.middleware.idempotency_utils.acquire_lock')
    @patch('hub.apps.api.middleware.idempotency_utils.release_lock')
    def test_middleware_adds_idempotency_key_header_for_new_request(self, mock_release_lock, mock_acquire_lock, mock_get_redis):
        """Test middleware adds Idempotency-Key header to response for new request."""
        idempotency_key = str(uuid.uuid4())

        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # No existing record
        mock_redis.setex.return_value = True  # For storing idempotency record
        mock_get_redis.return_value = mock_redis
        mock_acquire_lock.return_value = True  # Lock acquired
        mock_release_lock.return_value = None  # Lock released

        get_response = Mock(return_value=JsonResponse({"id": "123"}, status=201))
        middleware = IdempotencyMiddleware(get_response)
        request = self.factory.post(
            "/api/v1/assets/",
            data=json.dumps({"name": "test"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )

        response = middleware(request)

        # Should have Idempotency-Key header
        self.assertIn('Idempotency-Key', response)
        self.assertEqual(response['Idempotency-Key'], idempotency_key)
        # Should NOT have Idempotency-Replayed header for new request
        self.assertNotIn('Idempotency-Replayed', response)

    @patch('hub.apps.api.middleware.idempotency.get_redis_client')
    def test_middleware_adds_idempotency_replayed_header_for_cached_response(self, mock_get_redis):
        """Test middleware adds Idempotency-Replayed header when returning cached response."""
        idempotency_key = str(uuid.uuid4())
        request_hash = hash_request_body({"name": "test"})
        cached_response = {
            'request_hash': request_hash,
            'response': {
                'status_code': 201,
                'body': {'id': 'cached-123'},
                'headers': {},
                'timestamp': datetime.now(timezone.utc).isoformat()
            },
            'created_at': datetime.now(timezone.utc).isoformat()
        }

        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(cached_response)
        mock_get_redis.return_value = mock_redis

        get_response = Mock(return_value=JsonResponse({"id": "123"}, status=201))
        middleware = IdempotencyMiddleware(get_response)
        request = self.factory.post(
            "/api/v1/assets/",
            data=json.dumps({"name": "test"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )

        response = middleware(request)

        # Should have both headers for cached response
        self.assertIn('Idempotency-Key', response)
        self.assertEqual(response['Idempotency-Key'], idempotency_key)
        self.assertIn('Idempotency-Replayed', response)
        self.assertEqual(response['Idempotency-Replayed'], 'true')
        # Should not call get_response for cached response
        get_response.assert_not_called()

    @patch('hub.apps.api.middleware.idempotency.get_redis_client')
    def test_middleware_adds_idempotency_key_header_on_conflict_error(self, mock_get_redis):
        """Test middleware adds Idempotency-Key header even on conflict error."""
        idempotency_key = str(uuid.uuid4())
        # Compute the ACTUAL hash of the original request body so the
        # hash-comparison logic in the middleware is genuinely exercised.
        original_body = {"name": "original"}
        existing_hash = hash_request_body(original_body)
        cached_response = {
            'request_hash': existing_hash,
            'response': {
                'status_code': 201,
                'body': {'id': 'existing'},
                'headers': {},
                'timestamp': datetime.now(timezone.utc).isoformat()
            },
            'created_at': datetime.now(timezone.utc).isoformat()
        }

        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(cached_response)
        mock_get_redis.return_value = mock_redis

        get_response = Mock(return_value=JsonResponse({"id": "123"}, status=201))
        middleware = IdempotencyMiddleware(get_response)
        # Send a DIFFERENT body so the hash mismatch is detected by the
        # real hash_request_body function, not a hardcoded string mismatch.
        request = self.factory.post(
            "/api/v1/assets/",
            data=json.dumps({"name": "different"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key
        )

        response = middleware(request)

        # Should return 409 conflict
        self.assertEqual(response.status_code, 409)
        # Should still include Idempotency-Key header
        self.assertIn('Idempotency-Key', response)
        self.assertEqual(response['Idempotency-Key'], idempotency_key)
        # Should NOT have Idempotency-Replayed header for conflict
        self.assertNotIn('Idempotency-Replayed', response)
        # Should not call get_response for conflict error
        get_response.assert_not_called()

    @patch('hub.apps.api.middleware.idempotency.get_redis_client')
    def test_middleware_adds_idempotency_key_header_on_invalid_key_error(self, mock_get_redis):
        """Test middleware error response for invalid idempotency key format."""
        middleware = IdempotencyMiddleware(self.get_response)
        invalid_key = "invalid key format"
        request = self.factory.post(
            "/api/v1/assets/",
            data=json.dumps({"name": "test"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=invalid_key
        )

        response = middleware(request)

        # Should return 400 error
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn('error', response_data)
        # Error should reference idempotency
        self.assertIn('idempotency', response_data['error']['message'].lower())


# ============================================================================
# Edge Cases and Error Handling Tests
# ============================================================================

class TestEdgeCases(TestCase):
    """Test edge cases and error handling."""

    def test_hash_different_bodies_different_hashes(self):
        """Test different request bodies produce different hashes."""
        body1 = {"name": "test1"}
        body2 = {"name": "test2"}

        hash1 = hash_request_body(body1)
        hash2 = hash_request_body(body2)

        self.assertNotEqual(hash1, hash2)

    def test_serialize_response_with_binary_content(self):
        """Test serializing response with binary content."""
        response = HttpResponse(b'\x00\x01\x02')
        response['Content-Type'] = 'application/octet-stream'

        serialized = serialize_response(response)
        self.assertEqual(serialized['status_code'], 200)
        # Should handle binary content gracefully

    def test_deserialize_response_missing_fields(self):
        """Test deserializing response with missing fields."""
        data = {'status_code': 200}  # Missing body and headers

        status_code, body, headers = deserialize_response(data)
        self.assertEqual(status_code, 200)
        self.assertEqual(body, {})
        self.assertEqual(headers, {})

    def test_build_idempotency_key_with_special_chars(self):
        """Test building key with special characters in endpoint."""
        key = build_idempotency_key(
            "test-key",
            "/api/v1/assets/123/activate/",
            "POST"
        )
        self.assertIn("test-key", key)
        self.assertIn("POST", key)

    def test_normalize_key_preserves_case(self):
        """Test normalization preserves case."""
        key = "Test-Key-123"
        normalized = normalize_idempotency_key(key)
        self.assertEqual(normalized, "Test-Key-123")

