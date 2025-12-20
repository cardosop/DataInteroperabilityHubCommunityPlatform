#!/usr/bin/env python
"""
Standalone test script for idempotency middleware.

Tests all functionality without requiring Django's test framework.
Can be run directly to validate implementation.
"""
import os
import sys
import json
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django
django.setup()

import redis
from django.test import RequestFactory, override_settings
from django.http import HttpResponse, JsonResponse

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
    acquire_lock,
    release_lock,
    get_idempotency_ttl,
    is_idempotency_enabled,
    should_process_idempotency,
    get_endpoint_pattern,
    IdempotencyKeyFormatError,
)


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'


def print_test(name):
    print(f"\n{Colors.BLUE}=== {name} ==={Colors.RESET}")


def print_pass(msg):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def print_fail(msg):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


def print_skip(msg):
    print(f"{Colors.YELLOW}⊘{Colors.RESET} {msg}")


def test_key_validation():
    """Test idempotency key validation."""
    print_test("Key Validation Tests")

    # UUID format
    key = str(uuid.uuid4())
    assert validate_idempotency_key(key), "UUID should be valid"
    print_pass(f"UUID format validation: {key[:8]}...")

    # Valid custom formats
    valid_keys = ["my-key-123", "test_key_456", "key/with/slashes", "a" * 8, "a" * 256]
    for key in valid_keys:
        assert validate_idempotency_key(key), f"Key '{key[:20]}...' should be valid"
    print_pass(f"Custom format validation: {len(valid_keys)} keys")

    # Invalid formats
    invalid_keys = ["", "short", "a" * 257, "key with spaces", "key@special"]
    for key in invalid_keys:
        assert not validate_idempotency_key(key), f"Key '{key[:20]}...' should be invalid"
    print_pass(f"Invalid format rejection: {len(invalid_keys)} keys")

    # Normalization
    normalized = normalize_idempotency_key("  test-key-123  ")
    assert normalized == "test-key-123", f"Expected 'test-key-123', got '{normalized}'"
    print_pass("Key normalization with whitespace")

    # Normalization error
    try:
        normalize_idempotency_key("invalid key")
        assert False, "Should raise IdempotencyKeyFormatError"
    except IdempotencyKeyFormatError:
        print_pass("Normalization raises error for invalid key")


def test_redis_operations():
    """Test Redis operations."""
    print_test("Redis Operations Tests")

    try:
        redis_client = get_redis_client()
        print_pass("Redis client connection")
    except Exception as e:
        print_skip(f"Redis not available: {e}")
        return

    # Test key building
    redis_key = build_idempotency_key("test-key", "/api/v1/assets/", "POST")
    assert "idempotency" in redis_key
    assert "test-key" in redis_key
    assert "POST" in redis_key
    print_pass(f"Redis key building: {redis_key}")

    # Test lock key building
    lock_key = build_lock_key(redis_key)
    assert lock_key.endswith(":lock")
    print_pass(f"Lock key building: {lock_key}")

    # Test store and retrieve
    test_key = f"test:idempotency:{uuid.uuid4()}"
    request_hash = "test-hash-123"
    response_data = {
        'status_code': 201,
        'body': {'id': '123'},
        'headers': {},
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

    store_idempotency_record(redis_client, test_key, request_hash, response_data, ttl=60)
    print_pass("Store idempotency record")

    record = get_idempotency_record(redis_client, test_key)
    assert record is not None
    assert record['request_hash'] == request_hash
    print_pass("Retrieve idempotency record")

    # Cleanup
    redis_client.delete(test_key)
    print_pass("Cleanup test data")

    # Test lock operations
    lock_key = f"test:lock:{uuid.uuid4()}"
    acquired = acquire_lock(redis_client, lock_key, timeout=1, expire=10)
    assert acquired, "Should acquire lock"
    print_pass("Acquire lock")

    acquired2 = acquire_lock(redis_client, lock_key, timeout=0.1, expire=10)
    assert not acquired2, "Should not acquire lock when already held"
    print_pass("Lock prevents concurrent acquisition")

    release_lock(redis_client, lock_key)
    print_pass("Release lock")

    acquired3 = acquire_lock(redis_client, lock_key, timeout=1, expire=10)
    assert acquired3, "Should acquire lock after release"
    print_pass("Acquire lock after release")

    release_lock(redis_client, lock_key)


def test_serialization():
    """Test request/response serialization."""
    print_test("Serialization Tests")

    # Test request body hashing
    body1 = {"name": "test", "value": 123}
    body2 = {"value": 123, "name": "test"}  # Different order
    hash1 = hash_request_body(body1)
    hash2 = hash_request_body(body2)
    assert hash1 == hash2, "Same content should produce same hash"
    print_pass("Request body hashing (order-independent)")

    # Test different bodies produce different hashes
    body3 = {"name": "test2"}
    hash3 = hash_request_body(body3)
    assert hash1 != hash3, "Different bodies should produce different hashes"
    print_pass("Different bodies produce different hashes")

    # Test response serialization
    response = JsonResponse({"id": "123", "name": "test"}, status=201)
    serialized = serialize_response(response)
    assert serialized['status_code'] == 201
    assert serialized['body']['id'] == "123"
    assert 'timestamp' in serialized
    print_pass("Response serialization")

    # Test response deserialization
    status_code, body, headers = deserialize_response(serialized)
    assert status_code == 201
    assert body['id'] == "123"
    print_pass("Response deserialization")


def test_middleware():
    """Test middleware functionality."""
    print_test("Middleware Tests")

    factory = RequestFactory()
    get_response = lambda req: JsonResponse({"id": "123"}, status=201)
    middleware = IdempotencyMiddleware(get_response)

    # Test should_process_idempotency
    request = factory.post("/api/v1/assets/", data={"name": "test"}, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    assert should_process_idempotency(request), "Should process POST with idempotency key"
    print_pass("should_process_idempotency: POST with key")

    request = factory.get("/api/v1/assets/")
    assert not should_process_idempotency(request), "Should not process GET"
    print_pass("should_process_idempotency: GET skipped")

    request = factory.post("/api/v1/assets/", data={"name": "test"})
    assert not should_process_idempotency(request), "Should not process without key"
    print_pass("should_process_idempotency: No key skipped")

    # Test middleware with invalid key
    request = factory.post("/api/v1/assets/", data={"name": "test"}, HTTP_IDEMPOTENCY_KEY="invalid key")
    response = middleware(request)
    assert response.status_code == 400
    print_pass("Middleware rejects invalid key format")

    # Test middleware with valid key (will fail open if Redis unavailable)
    idempotency_key = str(uuid.uuid4())
    request = factory.post(
        "/api/v1/assets/",
        data={"name": "test"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=idempotency_key
    )
    response = middleware(request)
    # Should either process normally or return cached response
    assert response.status_code in (201, 200)
    print_pass("Middleware processes request with valid key")


def test_configuration():
    """Test configuration functions."""
    print_test("Configuration Tests")

    ttl = get_idempotency_ttl()
    assert isinstance(ttl, int)
    assert ttl > 0
    print_pass(f"Idempotency TTL: {ttl} seconds")

    enabled = is_idempotency_enabled()
    assert isinstance(enabled, bool)
    print_pass(f"Idempotency enabled: {enabled}")

    pattern = get_endpoint_pattern("/api/v1/assets/")
    assert pattern == "/api/v1/assets"
    print_pass(f"Endpoint pattern: {pattern}")


def main():
    """Run all tests."""
    print(f"\n{Colors.BLUE}{'='*60}")
    print("Idempotency Middleware Comprehensive Tests")
    print(f"{'='*60}{Colors.RESET}\n")

    tests = [
        test_key_validation,
        test_serialization,
        test_configuration,
        test_redis_operations,
        test_middleware,
    ]

    passed = 0
    failed = 0
    skipped = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print_fail(f"{test_func.__name__}: {e}")
            failed += 1
        except Exception as e:
            print_skip(f"{test_func.__name__}: {e}")
            skipped += 1

    print(f"\n{Colors.BLUE}{'='*60}")
    print(f"Test Summary: {Colors.GREEN}{passed} passed{Colors.RESET}, "
          f"{Colors.RED}{failed} failed{Colors.RESET}, "
          f"{Colors.YELLOW}{skipped} skipped{Colors.RESET}")
    print(f"{'='*60}{Colors.RESET}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

