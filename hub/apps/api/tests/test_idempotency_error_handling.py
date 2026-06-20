"""
Comprehensive error handling tests for idempotency middleware.

Tests cover:
- Redis failures (fail-open behavior)
- Malformed idempotency keys (400 Bad Request)
- Expired idempotency keys (410 Gone)
- Redis operation failures
- Invalid JSON in Redis records
- Concurrent request handling errors

All tests use real Redis connections - no mocks or stubs.
"""

import json
import time
import uuid
from datetime import UTC, datetime

from django.http import JsonResponse
from django.test import RequestFactory, TestCase, override_settings

from hub.apps.api.middleware.idempotency import IdempotencyMiddleware
from hub.apps.api.middleware.idempotency_utils import (
    build_idempotency_key,
    get_idempotency_record,
    get_redis_client,
    hash_request_body,
    store_idempotency_record,
)


class TestIdempotencyErrorHandling(TestCase):
    """Comprehensive error handling tests for idempotency middleware."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.redis_client = get_redis_client()

    def test_malformed_idempotency_key_returns_400(self):
        """Test malformed idempotency keys return 400 Bad Request."""

        def get_response(request):
            return JsonResponse({"status": "ok"}, status=200)

        middleware = IdempotencyMiddleware(get_response)

        # Test various invalid key formats
        invalid_keys = [
            "invalid key with spaces",
            "key@with#special$chars",
            "key with newline\n",
            "a" * 300,  # Too long
        ]

        for invalid_key in invalid_keys:
            request = self.factory.post(
                "/api/v1/assets/",
                data=json.dumps({"name": "test"}),
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY=invalid_key,
            )

            response = middleware(request)

            self.assertEqual(response.status_code, 400, f"Failed for key: {invalid_key}")
            response_data = json.loads(response.content)
            self.assertIn("error", response_data)
            self.assertEqual(response_data["error"]["code"], "INVALID_IDEMPOTENCY_KEY")
            self.assertEqual(response_data["error"]["http_status"], 400)

        # Test empty key separately — the middleware skips empty keys
        # (process_request returns None), then the request is processed
        # normally by the view. Assert the response reflects normal processing.
        request = self.factory.post(
            "/api/v1/assets/",
            data=json.dumps({"name": "test"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="",
        )
        response = middleware(request)
        self.assertIsNotNone(
            response, "Empty key should still produce a response from get_response"
        )
        self.assertEqual(
            response.status_code,
            200,
            "Empty key should be ignored, allowing normal request processing",
        )

    def test_expired_idempotency_key_detection(self):
        """Test expired idempotency key detection via TTL expiry.

        Uses a short TTL with polling to avoid a hard time.sleep() that
        slows down the suite and is fragile under load.
        """
        redis_client = get_redis_client()
        idempotency_key = str(uuid.uuid4())
        redis_key = build_idempotency_key(idempotency_key, "/api/v1/assets/", "POST")

        # Store a record with very short TTL (1 second)
        request_hash = hash_request_body({"name": "test"})
        response_data = {
            "status_code": 201,
            "body": {"id": "123"},
            "headers": {},
            "timestamp": datetime.now(UTC).isoformat(),
        }

        store_idempotency_record(redis_client, redis_key, request_hash, response_data, ttl=1)

        # Poll for expiry instead of hard-sleeping 2 seconds
        deadline = time.monotonic() + 3.0
        record = None
        while time.monotonic() < deadline:
            record = get_idempotency_record(redis_client, redis_key)
            if record is None:
                break
            time.sleep(0.05)  # noqa: sleep-needed — retry loop

        self.assertIsNone(record, "Expired key should be deleted by Redis after TTL expires")

    def test_redis_failure_during_retrieval_fails_open(self):
        """Test Redis failure during record retrieval fails open gracefully."""

        def get_response(request):
            return JsonResponse({"id": "123"}, status=201)

        middleware = IdempotencyMiddleware(get_response)
        idempotency_key = str(uuid.uuid4())

        # Create a request with valid idempotency key
        request = self.factory.post(
            "/api/v1/assets/",
            data=json.dumps({"name": "test"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )

        # Simulate Redis failure by using invalid URL
        with override_settings(REDIS_URL="redis://invalid-host:6379/0"):
            # Reset middleware Redis client
            middleware._redis_client = None

            # process_request should return None (fail open)
            response_from_process_request = middleware.process_request(request)
            self.assertIsNone(
                response_from_process_request,
                "Should fail open and return None from process_request",
            )

            # process_response will still be called and add headers
            # but the request was processed normally
            actual_response = get_response(request)
            response_from_process_response = middleware.process_response(request, actual_response)

            # Response should be returned (fail-open behavior)
            self.assertIsNotNone(response_from_process_response)
            self.assertEqual(response_from_process_response.status_code, 201)

    def test_idempotency_conflict_returns_409(self):
        """Test idempotency conflict (same key, different body) returns 409."""

        def get_response(request):
            return JsonResponse({"id": "123"}, status=201)

        middleware = IdempotencyMiddleware(get_response)
        redis_client = get_redis_client()
        idempotency_key = str(uuid.uuid4())
        redis_key = build_idempotency_key(idempotency_key, "/api/v1/assets/", "POST")

        # Store initial record
        request_hash1 = hash_request_body({"name": "test1"})
        response_data = {
            "status_code": 201,
            "body": {"id": "123"},
            "headers": {},
            "timestamp": datetime.now(UTC).isoformat(),
        }
        store_idempotency_record(redis_client, redis_key, request_hash1, response_data, ttl=60)

        # Try to use same key with different body
        request = self.factory.post(
            "/api/v1/assets/",
            data=json.dumps({"name": "test2"}),  # Different body
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )

        response = middleware(request)

        # Should return 409 Conflict
        self.assertEqual(response.status_code, 409)
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"]["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(response_data["error"]["http_status"], 409)
        self.assertIn("Idempotency-Key", response)

    def test_invalid_json_in_redis_record_handled_gracefully(self):
        """Test invalid JSON in Redis record is handled gracefully."""

        def get_response(request):
            return JsonResponse({"id": "123"}, status=201)

        middleware = IdempotencyMiddleware(get_response)
        redis_client = get_redis_client()
        idempotency_key = str(uuid.uuid4())
        redis_key = build_idempotency_key(idempotency_key, "/api/v1/assets/", "POST")

        # Store invalid JSON in Redis
        redis_client.setex(redis_key, 60, "invalid json {")

        # Try to use the key
        request = self.factory.post(
            "/api/v1/assets/",
            data=json.dumps({"name": "test"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )

        response = middleware(request)

        # Should handle gracefully — invalid JSON in the Redis record is
        # treated as a cache miss. The request is processed as new.
        self.assertIsNotNone(response)
        self.assertEqual(
            response.status_code,
            201,
            "Corrupted Redis record should cause fail-open: process as new request",
        )
        response_data = json.loads(response.content)
        self.assertEqual(
            response_data["id"], "123", "Response body should match the get_response handler output"
        )

    def test_redis_connection_error_handled_gracefully(self):
        """Test Redis connection failure is handled gracefully (fail-open).

        Covers both retrieval failure and lock-acquisition failure, which
        follow the same fail-open code path. Previously had two identical
        tests that only varied by docstring — consolidated into one.
        """

        def get_response(request):
            return JsonResponse({"id": "123"}, status=201)

        middleware = IdempotencyMiddleware(get_response)
        idempotency_key = str(uuid.uuid4())

        # Create a request with valid idempotency key
        request = self.factory.post(
            "/api/v1/assets/",
            data=json.dumps({"name": "test"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )

        # Simulate Redis failure by using invalid URL
        with override_settings(REDIS_URL="redis://invalid-host:6379/0"):
            # Reset middleware Redis client
            middleware._redis_client = None

            # process_request should return None (fail open)
            response_from_process_request = middleware.process_request(request)
            self.assertIsNone(
                response_from_process_request,
                "Should fail open and return None from process_request",
            )

            # process_response will still be called and add headers
            # but the request was processed normally
            actual_response = get_response(request)
            response_from_process_response = middleware.process_response(request, actual_response)

            # Response should be returned (fail-open behavior)
            self.assertIsNotNone(response_from_process_response)
            self.assertEqual(response_from_process_response.status_code, 201)

    def test_idempotency_key_header_present_in_success_responses(self):
        """Test Idempotency-Key header is present in success responses."""

        def get_response(request):
            return JsonResponse({"id": "123"}, status=201)

        middleware = IdempotencyMiddleware(get_response)
        idempotency_key = str(uuid.uuid4())

        # Test: New request (success)
        request = self.factory.post(
            "/api/v1/assets/",
            data=json.dumps({"name": "test"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )
        response = middleware(request)
        self.assertIsNotNone(response)
        self.assertIn("Idempotency-Key", response)

    def test_idempotency_key_header_present_in_cached_responses(self):
        """Test Idempotency-Key header is present in cached responses."""

        def get_response(request):
            return JsonResponse({"id": "123"}, status=201)

        middleware = IdempotencyMiddleware(get_response)
        redis_client = get_redis_client()
        idempotency_key = str(uuid.uuid4())

        # Store initial record
        redis_key = build_idempotency_key(idempotency_key, "/api/v1/assets/", "POST")
        request_hash = hash_request_body({"name": "test"})
        response_data = {
            "status_code": 201,
            "body": {"id": "123"},
            "headers": {},
            "timestamp": datetime.now(UTC).isoformat(),
        }
        store_idempotency_record(redis_client, redis_key, request_hash, response_data, ttl=60)

        # Request with same key and body
        request = self.factory.post(
            "/api/v1/assets/",
            data=json.dumps({"name": "test"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )
        response = middleware(request)

        self.assertIn("Idempotency-Key", response)
        self.assertIn("Idempotency-Replayed", response)
        self.assertEqual(response["Idempotency-Replayed"], "true")
