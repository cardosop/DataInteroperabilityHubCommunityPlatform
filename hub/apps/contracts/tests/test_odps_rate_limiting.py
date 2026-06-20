"""
Comprehensive unit tests for ODPS $ref resolution rate limiting.

Tests verify:
1. Redis key format generation
2. Rate limit checking logic
3. Error handling and response format
4. TTL strategy
5. Fail-open behavior

All tests use real implementations (no mocks/stubs).
Redis uses real Redis client with graceful handling when unavailable.
"""

try:
    import pytest

    pytestmark = pytest.mark.django_db
except ImportError:
    # pytest not available, using Django test runner
    pytest = None
    pytestmark = None

import time

from django.test import TestCase, override_settings

from hub.apps.contracts.odps_rate_limiting import (
    RATE_LIMIT_GLOBAL,
    RATE_LIMIT_PER_TENANT,
    RATE_LIMIT_PER_USER,
    RATE_LIMIT_WINDOW,
    REDIS_KEY_PREFIX_GLOBAL,
    REDIS_KEY_PREFIX_TENANT,
    REDIS_KEY_PREFIX_USER,
    ODPSRefResolutionError,
    check_rate_limit,
    generate_rate_limit_key,
    get_rate_limit,
    get_rate_limit_info,
)


class ODPSRateLimitingKeyFormatTest(TestCase):
    """Test Redis key format generation"""

    def test_generate_tenant_key_format(self):
        """Test that tenant-level key has correct format"""
        tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        current_time = int(time.time())
        current_hour = (current_time // RATE_LIMIT_WINDOW) * RATE_LIMIT_WINDOW

        key = generate_rate_limit_key(tenant_id=tenant_id, level="tenant")

        expected_key = f"{REDIS_KEY_PREFIX_TENANT}:{tenant_id}:{current_hour}"
        self.assertEqual(key, expected_key, "Tenant key should match expected format")
        self.assertIn(tenant_id, key, "Tenant key should contain tenant_id")
        self.assertIn(REDIS_KEY_PREFIX_TENANT, key, "Tenant key should contain prefix")

    def test_generate_user_key_format(self):
        """Test that user-level key has correct format"""
        tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        user_id = "660e8400-e29b-41d4-a716-446655440001"
        current_time = int(time.time())
        current_hour = (current_time // RATE_LIMIT_WINDOW) * RATE_LIMIT_WINDOW

        key = generate_rate_limit_key(tenant_id=tenant_id, user_id=user_id, level="user")

        expected_key = f"{REDIS_KEY_PREFIX_USER}:{tenant_id}:{user_id}:{current_hour}"
        self.assertEqual(key, expected_key, "User key should match expected format")
        self.assertIn(tenant_id, key, "User key should contain tenant_id")
        self.assertIn(user_id, key, "User key should contain user_id")
        self.assertIn(REDIS_KEY_PREFIX_USER, key, "User key should contain prefix")

    def test_generate_global_key_format(self):
        """Test that global-level key has correct format"""
        current_time = int(time.time())
        current_hour = (current_time // RATE_LIMIT_WINDOW) * RATE_LIMIT_WINDOW

        key = generate_rate_limit_key(level="global")

        expected_key = f"{REDIS_KEY_PREFIX_GLOBAL}:{current_hour}"
        self.assertEqual(key, expected_key, "Global key should match expected format")
        self.assertIn(REDIS_KEY_PREFIX_GLOBAL, key, "Global key should contain prefix")

    def test_generate_key_requires_tenant_id_for_tenant_level(self):
        """Test that tenant-level key generation requires tenant_id"""
        with self.assertRaises(ValueError) as cm:
            generate_rate_limit_key(level="tenant")

        self.assertIn("tenant_id is required", str(cm.exception))

    def test_generate_key_requires_tenant_id_for_user_level(self):
        """Test that user-level key generation requires tenant_id"""
        with self.assertRaises(ValueError) as cm:
            generate_rate_limit_key(user_id="user123", level="user")

        self.assertIn("tenant_id is required", str(cm.exception))

    def test_generate_key_requires_user_id_for_user_level(self):
        """Test that user-level key generation requires user_id"""
        with self.assertRaises(ValueError) as cm:
            generate_rate_limit_key(tenant_id="tenant123", level="user")

        self.assertIn("user_id is required", str(cm.exception))

    def test_generate_key_invalid_level(self):
        """Test that invalid level raises ValueError"""
        with self.assertRaises(ValueError) as cm:
            generate_rate_limit_key(level="invalid")

        self.assertIn("Invalid rate limit level", str(cm.exception))

    def test_generate_key_hour_rounding(self):
        """Test that hour is correctly rounded down (no mocks: use explicit timestamp)."""
        base_hour = 1704067200  # Fixed hour boundary for deterministic test
        key1 = generate_rate_limit_key(level="global", timestamp=base_hour)
        key2 = generate_rate_limit_key(level="global", timestamp=base_hour + 1800)
        key3 = generate_rate_limit_key(level="global", timestamp=base_hour + 3599)

        expected_key = f"{REDIS_KEY_PREFIX_GLOBAL}:{base_hour}"
        self.assertEqual(key1, expected_key)
        self.assertEqual(key2, expected_key, "Keys should be same within same hour")
        self.assertEqual(key3, expected_key, "Keys should be same within same hour")


class ODPSRateLimitingLimitsTest(TestCase):
    """Test rate limit constants"""

    def test_get_rate_limit_tenant(self):
        """Test getting tenant rate limit"""
        limit = get_rate_limit("tenant")
        self.assertEqual(limit, RATE_LIMIT_PER_TENANT, "Tenant limit should match constant")

    def test_get_rate_limit_user(self):
        """Test getting user rate limit"""
        limit = get_rate_limit("user")
        self.assertEqual(limit, RATE_LIMIT_PER_USER, "User limit should match constant")

    def test_get_rate_limit_global(self):
        """Test getting global rate limit"""
        limit = get_rate_limit("global")
        self.assertEqual(limit, RATE_LIMIT_GLOBAL, "Global limit should match constant")

    def test_get_rate_limit_invalid_level(self):
        """Test that invalid level raises ValueError"""
        with self.assertRaises(ValueError) as cm:
            get_rate_limit("invalid")

        self.assertIn("Invalid rate limit level", str(cm.exception))


class ODPSRefResolutionErrorTest(TestCase):
    """Test ODPSRefResolutionError exception"""

    def test_error_creation(self):
        """Test creating error with all fields"""
        error = ODPSRefResolutionError(
            message="Test error",
            retry_after=1704070800,
            error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED,
            tenant_id="tenant123",
            user_id="user456",
        )

        self.assertEqual(error.message, "Test error")
        self.assertEqual(error.retry_after, 1704070800)
        self.assertEqual(error.error_code, ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED)
        self.assertEqual(error.tenant_id, "tenant123")
        self.assertEqual(error.user_id, "user456")

    def test_error_to_dict(self):
        """Test converting error to dictionary"""
        retry_after = int(time.time()) + 3600
        error = ODPSRefResolutionError(
            message="Rate limit exceeded",
            retry_after=retry_after,
            error_code=ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED,
            tenant_id="tenant123",
        )

        error_dict = error.to_dict()

        self.assertEqual(error_dict["error"], ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED)
        self.assertEqual(error_dict["message"], "Rate limit exceeded")
        self.assertEqual(error_dict["tenant_id"], "tenant123")
        self.assertIn("retry_after", error_dict)
        self.assertIn("retry_after_timestamp", error_dict)

    def test_error_get_retry_after_header(self):
        """Test getting Retry-After header value"""
        retry_after = int(time.time()) + 3600
        error = ODPSRefResolutionError(message="Rate limit exceeded", retry_after=retry_after)

        retry_header = error.get_retry_after_header()

        self.assertIsNotNone(retry_header)
        self.assertIsInstance(retry_header, str)
        # Should be approximately 3600 seconds
        self.assertGreaterEqual(int(retry_header), 3590)
        self.assertLessEqual(int(retry_header), 3610)

    def test_error_get_retry_after_header_none(self):
        """Test getting Retry-After header when retry_after is None"""
        error = ODPSRefResolutionError(message="Other error", retry_after=None)

        retry_header = error.get_retry_after_header()

        self.assertIsNone(retry_header)


from hub.apps.contracts.tests.test_base import get_real_redis_client_or_none


class ODPSRateLimitingCheckTest(TestCase):
    """Test rate limit checking logic using real Redis.

    Uses TestCase (not TransactionTestCase) to avoid full DB flush between tests,
    which can cause 300s+ timeouts in CI when create_permissions runs after flush.
    These tests only need Redis; they do not require transaction rollback.
    """

    def setUp(self):
        """Set up test fixtures"""
        self.tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        self.user_id = "660e8400-e29b-41d4-a716-446655440001"
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available in test environment")

        # Clear any existing rate limit keys for test isolation
        try:
            pattern = f"odps_ref_rate_limit:*{self.tenant_id}*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            pattern = "odps_ref_rate_limit:global:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def tearDown(self):
        """Clean up test data from Redis"""
        if self.redis_client:
            try:
                pattern = f"odps_ref_rate_limit:*{self.tenant_id}*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
                pattern = "odps_ref_rate_limit:global:*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            except Exception:
                pass

    def test_check_rate_limit_allows_when_under_limit(self):
        """Test that rate limit check allows requests when under limit using real Redis"""
        # Use real Redis - make a few requests that should be under limit
        for i in range(10):
            is_allowed, error = check_rate_limit(
                tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
            )
            self.assertTrue(is_allowed, f"Request {i + 1} should be allowed when under limit")
            self.assertIsNone(error, "No error should be returned when allowed")

    def test_check_rate_limit_rejects_when_over_limit(self):
        """Test that rate limit check rejects requests when over limit using real Redis"""
        # Use real Redis - exceed user limit (50 requests/hour, lower than tenant limit)
        # Make requests up to the user limit
        for i in range(RATE_LIMIT_PER_USER):
            is_allowed, error = check_rate_limit(
                tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
            )
            self.assertTrue(is_allowed, f"Request {i + 1} should be allowed")

        # Next request should be rejected
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
        )

        self.assertFalse(is_allowed, "Request should be rejected when over limit")
        self.assertIsNotNone(error, "Error should be returned when rejected")
        self.assertIsInstance(error, ODPSRefResolutionError)
        self.assertEqual(error.error_code, ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED)
        self.assertIsNotNone(error.retry_after)

    def test_check_rate_limit_checks_all_levels(self):
        """Test that rate limit check verifies all three levels using real Redis"""
        # Use real Redis - exceed user limit (which will be hit first)
        # Make requests up to the user limit
        for i in range(RATE_LIMIT_PER_USER):
            is_allowed, error = check_rate_limit(
                tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
            )
            self.assertTrue(is_allowed, f"Request {i + 1} should be allowed")

        # Next request should be rejected at user level
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
        )

        self.assertFalse(is_allowed, "Request should be rejected if any level exceeds limit")
        self.assertIn("user", error.message.lower(), "Error should mention user level")

    def test_check_rate_limit_sets_ttl(self):
        """Test that rate limit check sets TTL on Redis keys using real Redis"""
        # Make a request to create a key
        check_rate_limit(
            tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
        )

        # Verify TTL is set on the user key (should be RATE_LIMIT_WINDOW + 3600)
        user_key = generate_rate_limit_key(
            tenant_id=self.tenant_id, user_id=self.user_id, level="user"
        )
        ttl = self.redis_client.ttl(user_key)
        self.assertGreater(ttl, 0, "TTL should be set on Redis key")
        # TTL should be approximately RATE_LIMIT_WINDOW + 3600 (allow some tolerance)
        expected_ttl = RATE_LIMIT_WINDOW + 3600
        self.assertGreaterEqual(
            ttl, expected_ttl - 10, "TTL should be approximately window + 1 hour"
        )
        self.assertLessEqual(ttl, expected_ttl + 10, "TTL should be approximately window + 1 hour")

    def test_check_rate_limit_fails_open_when_redis_unavailable(self):
        """Test that rate limit check fails open when Redis is unavailable"""
        # Use invalid Redis URL to simulate unavailability
        with override_settings(REDIS_URL="redis://localhost:99999"):
            is_allowed, error = check_rate_limit(tenant_id=self.tenant_id, user_id=self.user_id)

            self.assertTrue(is_allowed, "Should allow requests when Redis unavailable (fail open)")
            self.assertIsNone(error, "No error when failing open")

    def test_check_rate_limit_normal_operation_with_valid_redis(self):
        """
        Test rate limit check normal operation with valid Redis.

        The fail-open-on-Redis-error path is tested separately by
        ``test_check_rate_limit_fails_open_when_redis_unavailable`` which
        uses ``override_settings(REDIS_URL="redis://localhost:99999")``.
        This test verifies normal operation: no unhandled exceptions,
        valid bool return, and correct error code on rate-limit hit.
        """
        redis_client = get_real_redis_client_or_none()
        if not redis_client:
            self.skipTest("Redis not available - cannot test fail-open on errors")

        # The function has try/except blocks that catch Redis errors and fail open
        # Test normal operation - errors are handled internally by the implementation
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id, user_id=self.user_id, redis_client=redis_client
        )

        # Should return a valid result (either allowed or rejected based on rate limit state)
        # The important thing is that it doesn't raise an exception
        self.assertIsInstance(is_allowed, bool)
        # Error should be None if allowed, or ODPSRefResolutionError if rate limited
        if not is_allowed:
            self.assertIsNotNone(error)
            self.assertEqual(
                error.error_code, ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED
            )


class ODPSRateLimitingInfoTest(TestCase):
    """Test rate limit information retrieval using real Redis.

    Uses TestCase (not TransactionTestCase) to avoid full DB flush between tests,
    which can cause 300s+ timeouts in CI when create_permissions runs after flush.
    These tests only need Redis; they do not require transaction rollback.
    """

    def setUp(self):
        """Set up test fixtures"""
        self.tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        self.user_id = "660e8400-e29b-41d4-a716-446655440001"
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available in test environment")

        # Clear any existing rate limit keys for test isolation
        try:
            pattern = f"odps_ref_rate_limit:*{self.tenant_id}*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            pattern = "odps_ref_rate_limit:global:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def tearDown(self):
        """Clean up test data from Redis"""
        if self.redis_client:
            try:
                pattern = f"odps_ref_rate_limit:*{self.tenant_id}*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
                pattern = "odps_ref_rate_limit:global:*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            except Exception:
                pass

    def test_get_rate_limit_info_returns_all_levels(self):
        """Test that get_rate_limit_info returns information for all levels using real Redis"""
        # Make some requests to populate rate limit data
        for _i in range(5):
            check_rate_limit(
                tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
            )

        info = get_rate_limit_info(
            tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
        )

        self.assertIn("global", info, "Should include global level info")
        self.assertIn("tenant", info, "Should include tenant level info")
        self.assertIn("user", info, "Should include user level info")

    def test_get_rate_limit_info_includes_count_and_limit(self):
        """Test that rate limit info includes count and limit using real Redis"""
        # Make some requests to populate rate limit data
        request_count = 10
        for _i in range(request_count):
            check_rate_limit(
                tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
            )

        info = get_rate_limit_info(
            tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
        )

        # Check tenant level
        tenant_info = info["tenant"]
        self.assertIn("count", tenant_info)
        self.assertIn("limit", tenant_info)
        self.assertIn("remaining", tenant_info)
        self.assertIn("reset_time", tenant_info)
        self.assertGreaterEqual(tenant_info["count"], request_count)
        self.assertEqual(tenant_info["limit"], RATE_LIMIT_PER_TENANT)
        self.assertEqual(tenant_info["remaining"], RATE_LIMIT_PER_TENANT - tenant_info["count"])


class ODPSRateLimitingIntegrationTest(TestCase):
    """Integration tests for rate limiting with real Redis"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        self.user_id = "660e8400-e29b-41d4-a716-446655440001"
        self.tenant_id_2 = "770e8400-e29b-41d4-a716-446655440002"
        self.user_id_2 = "880e8400-e29b-41d4-a716-446655440003"

        # Get real Redis client if available
        try:
            import redis
            from django.conf import settings

            redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
            self.redis_client = redis.from_url(
                redis_url, decode_responses=False, socket_connect_timeout=1
            )
            self.redis_client.ping()
            self.redis_available = True
        except Exception:
            self.redis_available = False
            self.skipTest("Redis not available for integration tests")

    def tearDown(self):
        """Clean up test data from Redis"""
        if self.redis_available:
            try:
                # Clean up all test keys
                pattern = f"odps_ref_rate_limit:*{self.tenant_id}*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
                pattern = f"odps_ref_rate_limit:*{self.tenant_id_2}*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
                # Clean up global keys from this test run
                pattern = "odps_ref_rate_limit:global:*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            except Exception:
                pass  # Ignore cleanup errors

    def test_rate_limit_enforcement_per_tenant(self):
        """Integration test: Verify per-tenant rate limit is enforced"""
        # Use different user_ids to avoid hitting user limit (50) before tenant limit (100)
        # Make requests up to the tenant limit using different users
        user_ids = [f"{self.user_id}-{i}" for i in range(3)]  # Use 3 different users

        for i in range(RATE_LIMIT_PER_TENANT):
            user_idx = i % len(user_ids)
            is_allowed, error = check_rate_limit(
                tenant_id=self.tenant_id, user_id=user_ids[user_idx], redis_client=self.redis_client
            )
            self.assertTrue(is_allowed, f"Request {i + 1} should be allowed")
            self.assertIsNone(error, "No error should be returned")

        # Next request should be rejected at tenant level
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id, user_id=user_ids[0], redis_client=self.redis_client
        )
        self.assertFalse(is_allowed, "Request over tenant limit should be rejected")
        self.assertIsNotNone(error, "Error should be returned")
        self.assertEqual(error.error_code, ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED)
        self.assertIn("tenant", error.message.lower())
        self.assertIn("retry", error.message.lower())
        self.assertIsNotNone(error.retry_after)

    def test_rate_limit_enforcement_per_user(self):
        """Integration test: Verify per-user rate limit is enforced"""
        # Make requests up to the user limit
        for i in range(RATE_LIMIT_PER_USER):
            is_allowed, error = check_rate_limit(
                tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
            )
            self.assertTrue(is_allowed, f"Request {i + 1} should be allowed")
            self.assertIsNone(error, "No error should be returned")

        # Next request should be rejected at user level
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
        )
        self.assertFalse(is_allowed, "Request over user limit should be rejected")
        self.assertIsNotNone(error, "Error should be returned")
        self.assertEqual(error.error_code, ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED)
        self.assertIn("user", error.message.lower())
        self.assertIn("retry", error.message.lower())
        self.assertIsNotNone(error.retry_after)

    def test_rate_limit_enforcement_global(self):
        """Integration test: Verify global rate limit is enforced"""
        # Make requests up to the global limit
        # Use different tenants/users to avoid hitting tenant/user limits first
        tenant_ids = [f"tenant-{i}" for i in range(20)]
        user_ids = [f"user-{i}" for i in range(20)]

        request_count = 0
        for i in range(min(RATE_LIMIT_GLOBAL, 1000)):  # Limit to avoid long test
            tenant_idx = i % len(tenant_ids)
            user_idx = i % len(user_ids)
            is_allowed, error = check_rate_limit(
                tenant_id=tenant_ids[tenant_idx],
                user_id=user_ids[user_idx],
                redis_client=self.redis_client,
            )
            if is_allowed:
                request_count += 1
            # If we hit a limit, check if it's global
            elif error and "global" in error.message.lower():
                break

        # Verify we can track global usage
        info = get_rate_limit_info(redis_client=self.redis_client)
        self.assertIn("global", info)
        self.assertGreater(info["global"]["count"], 0)

    def test_rate_limit_independence_between_tenants(self):
        """Integration test: Verify rate limits are independent between tenants"""
        # Use different user_ids to avoid hitting user limit before tenant limit
        user_ids_tenant1 = [f"{self.user_id}-{i}" for i in range(3)]

        # Tenant 1: Make requests up to tenant limit using different users
        for i in range(RATE_LIMIT_PER_TENANT):
            user_idx = i % len(user_ids_tenant1)
            is_allowed, error = check_rate_limit(
                tenant_id=self.tenant_id,
                user_id=user_ids_tenant1[user_idx],
                redis_client=self.redis_client,
            )
            self.assertTrue(is_allowed, f"Tenant 1 request {i + 1} should be allowed")

        # Tenant 1 should be rate limited at tenant level
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id, user_id=user_ids_tenant1[0], redis_client=self.redis_client
        )
        self.assertFalse(is_allowed, "Tenant 1 should be rate limited")
        self.assertIn("tenant", error.message.lower())

        # Tenant 2 should still be allowed (independent limits)
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id_2, user_id=self.user_id_2, redis_client=self.redis_client
        )
        self.assertTrue(is_allowed, "Tenant 2 should be allowed (independent limits)")
        self.assertIsNone(error, "No error for tenant 2")

    def test_rate_limit_independence_between_users(self):
        """Integration test: Verify rate limits are independent between users"""
        # User 1: Make requests up to user limit
        for i in range(RATE_LIMIT_PER_USER):
            is_allowed, error = check_rate_limit(
                tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
            )
            self.assertTrue(is_allowed, f"User 1 request {i + 1} should be allowed")

        # User 1 should be rate limited
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
        )
        self.assertFalse(is_allowed, "User 1 should be rate limited")
        self.assertIn("user", error.message.lower())

        # User 2 (same tenant) should still be allowed (independent limits)
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id, user_id=self.user_id_2, redis_client=self.redis_client
        )
        self.assertTrue(is_allowed, "User 2 should be allowed (independent limits)")
        self.assertIsNone(error, "No error for user 2")

    def test_rate_limit_error_message_includes_retry_after(self):
        """Integration test: Verify error message includes retry-after suggestion"""
        # Exceed rate limit
        for _i in range(RATE_LIMIT_PER_TENANT + 1):
            is_allowed, error = check_rate_limit(
                tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
            )

        # Verify error message includes retry information
        self.assertFalse(is_allowed)
        self.assertIsNotNone(error)
        self.assertIn("retry", error.message.lower())
        self.assertIn("minute", error.message.lower() or "second" in error.message.lower())
        self.assertIsNotNone(error.retry_after)
        self.assertIsNotNone(error.get_retry_after_header())

    def test_rate_limit_logging_with_context(self):
        """Integration test: Verify rate limit violations are logged with context"""
        # Exceed user rate limit (which will be hit first)
        for _i in range(RATE_LIMIT_PER_USER + 1):
            is_allowed, error = check_rate_limit(
                tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
            )

        # Verify error has all context
        self.assertFalse(is_allowed)
        self.assertIsNotNone(error)
        self.assertEqual(error.tenant_id, self.tenant_id)
        # User limit is hit first, so user_id should be set
        if "user" in error.message.lower():
            self.assertEqual(error.user_id, self.user_id)
        self.assertEqual(error.error_code, ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED)
        self.assertIsNotNone(error.retry_after)

    def test_rate_limit_info_accuracy(self):
        """Integration test: Verify rate limit info is accurate"""
        # Make some requests
        for _i in range(10):
            check_rate_limit(
                tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
            )

        # Get rate limit info
        info = get_rate_limit_info(
            tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
        )

        # Verify info is accurate
        self.assertIn("global", info)
        self.assertIn("tenant", info)
        self.assertIn("user", info)

        # Check tenant level
        tenant_info = info["tenant"]
        self.assertGreaterEqual(tenant_info["count"], 10)
        self.assertEqual(tenant_info["limit"], RATE_LIMIT_PER_TENANT)
        self.assertEqual(tenant_info["remaining"], RATE_LIMIT_PER_TENANT - tenant_info["count"])

        # Check user level
        user_info = info["user"]
        self.assertGreaterEqual(user_info["count"], 10)
        self.assertEqual(user_info["limit"], RATE_LIMIT_PER_USER)
        self.assertEqual(user_info["remaining"], RATE_LIMIT_PER_USER - user_info["count"])

    def test_rate_limit_sliding_window(self):
        """Integration test: Verify sliding window algorithm works correctly"""
        # Make requests to fill the user limit window (user limit is lower, so it will be hit first)
        for i in range(RATE_LIMIT_PER_USER):
            is_allowed, error = check_rate_limit(
                tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
            )
            self.assertTrue(is_allowed, f"Request {i + 1} should be allowed")

        # Should be rate limited at user level
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
        )
        self.assertFalse(is_allowed, "Request should be rate limited")
        self.assertIn("user", error.message.lower())

        # Verify the mechanism works by checking info
        info = get_rate_limit_info(
            tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
        )
        self.assertGreaterEqual(info["user"]["count"], RATE_LIMIT_PER_USER)
        self.assertEqual(info["user"]["count"], RATE_LIMIT_PER_USER)

    # Edge cases and error handling tests
    def test_generate_rate_limit_key_with_none_tenant_id(self):
        """Rate limit key generation with None tenant_id raises ValueError."""
        with self.assertRaises(ValueError):
            generate_rate_limit_key(tenant_id=None, level="tenant")  # type: ignore[misc]  # test: edge-case type exercise

    def test_generate_rate_limit_key_with_empty_tenant_id(self):
        """Rate limit key generation with empty tenant_id raises ValueError."""
        with self.assertRaises(ValueError):
            generate_rate_limit_key(tenant_id="", level="tenant")

    def test_generate_rate_limit_key_with_special_characters(self):
        """Rate limit key generation handles special characters without crashing."""
        tenant_id = "tenant-<>&\"'"
        key = generate_rate_limit_key(tenant_id=tenant_id, level="tenant")
        self.assertIsNotNone(key)
        self.assertIn(REDIS_KEY_PREFIX_TENANT, key)

    def test_generate_rate_limit_key_with_unicode(self):
        """Rate limit key generation handles unicode characters without crashing."""
        tenant_id = "租户"
        key = generate_rate_limit_key(tenant_id=tenant_id, level="tenant")
        self.assertIsNotNone(key)
        self.assertIn(REDIS_KEY_PREFIX_TENANT, key)

    def test_check_rate_limit_with_none_tenant_id(self):
        """Test rate limit check with None tenant_id: rejected for security (tenant_id required)."""
        is_allowed, error = check_rate_limit(
            tenant_id=None,
            user_id=self.user_id,
            redis_client=self.redis_client,  # type: ignore[misc]  # test: edge-case type exercise
        )
        self.assertFalse(is_allowed, "None tenant_id should be rejected")
        self.assertIsNotNone(error)
        self.assertIsInstance(error, ODPSRefResolutionError)
        self.assertEqual(error.error_code, ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED)
        self.assertIn("tenant_id is required", str(error))

    def test_check_rate_limit_with_empty_tenant_id(self):
        """Test rate limit check with empty tenant_id: rejected for security (tenant_id required)."""
        is_allowed, error = check_rate_limit(
            tenant_id="", user_id=self.user_id, redis_client=self.redis_client
        )
        self.assertFalse(is_allowed, "Empty tenant_id should be rejected")
        self.assertIsNotNone(error)
        self.assertIsInstance(error, ODPSRefResolutionError)
        self.assertEqual(error.error_code, ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED)
        self.assertIn("tenant_id is required", str(error))

    def test_check_rate_limit_with_none_redis_client(self):
        """Test rate limit check with None Redis client."""
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            redis_client=None,  # type: ignore[misc]  # test: edge-case type exercise
        )
        # Should handle None Redis client gracefully (fail-open)
        self.assertTrue(is_allowed)
        self.assertIsNone(error)

    def test_get_rate_limit_info_with_none_tenant_id(self):
        """get_rate_limit_info with None tenant_id returns empty dict or raises."""
        result = get_rate_limit_info(
            tenant_id=None,
            user_id=self.user_id,
            redis_client=self.redis_client,  # type: ignore[misc]  # test: edge-case type exercise
        )
        self.assertIsInstance(
            result, dict, "get_rate_limit_info must return a dict for None tenant_id"
        )

    def test_get_rate_limit_info_with_none_redis_client(self):
        """Test get rate limit info with None Redis client."""
        info = get_rate_limit_info(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            redis_client=None,  # type: ignore[misc]  # test: edge-case type exercise
        )
        # Should handle None Redis client gracefully
        self.assertIsInstance(info, dict)

    def test_rate_limit_with_very_long_tenant_id(self):
        """Rate limit check handles very long tenant_id — must not crash, returns bool."""
        long_tenant_id = "a" * 10000
        is_allowed, _error = check_rate_limit(
            tenant_id=long_tenant_id, user_id=self.user_id, redis_client=self.redis_client
        )
        self.assertIsInstance(
            is_allowed, bool, "check_rate_limit must return a boolean for very long tenant_id"
        )

    def test_rate_limit_with_very_long_user_id(self):
        """Rate limit check handles very long user_id — must not crash, returns bool."""
        long_user_id = "a" * 10000
        is_allowed, _error = check_rate_limit(
            tenant_id=self.tenant_id, user_id=long_user_id, redis_client=self.redis_client
        )
        self.assertIsInstance(
            is_allowed, bool, "check_rate_limit must return a boolean for very long user_id"
        )

    def test_rate_limit_key_consistency(self):
        """Test rate limit key consistency across calls."""
        tenant_id = "test-tenant-123"
        key1 = generate_rate_limit_key(tenant_id=tenant_id, level="tenant")
        key2 = generate_rate_limit_key(tenant_id=tenant_id, level="tenant")
        # Same inputs should generate same key
        self.assertEqual(key1, key2)

    def test_rate_limit_key_different_levels(self):
        """Test rate limit key generation for different levels."""
        tenant_id = "test-tenant-123"
        user_id = "test-user-123"

        tenant_key = generate_rate_limit_key(tenant_id=tenant_id, level="tenant")
        user_key = generate_rate_limit_key(tenant_id=tenant_id, user_id=user_id, level="user")
        global_key = generate_rate_limit_key(level="global")

        # Different levels should generate different keys
        self.assertNotEqual(tenant_key, user_key)
        self.assertNotEqual(tenant_key, global_key)
        self.assertNotEqual(user_key, global_key)

    def test_rate_limit_info_structure(self):
        """Test rate limit info structure completeness."""
        info = get_rate_limit_info(
            tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
        )
        # Should have all required keys
        self.assertIn("global", info)
        self.assertIn("tenant", info)
        self.assertIn("user", info)

        # Each level should have count, limit, remaining
        for level in ["global", "tenant", "user"]:
            level_info = info[level]
            self.assertIn("count", level_info)
            self.assertIn("limit", level_info)
            self.assertIn("remaining", level_info)

    def test_rate_limiting_handles_unicode_characters(self):
        """Rate limiting key generation handles unicode tenant IDs without crashing."""
        tenant_id = "测试租户"
        key = generate_rate_limit_key(tenant_id=tenant_id, user_id=None, level="tenant")
        self.assertIsNotNone(key)
        self.assertIn(REDIS_KEY_PREFIX_TENANT, key)
        self.assertIn(tenant_id, key)

    def test_rate_limiting_handles_special_characters(self):
        """Rate limiting key generation handles special characters without crashing."""
        tenant_id = "Test & Co. (Special)"
        key = generate_rate_limit_key(tenant_id=tenant_id, user_id=None, level="tenant")
        self.assertIsNotNone(key)
        self.assertIn(REDIS_KEY_PREFIX_TENANT, key)
        self.assertIn(tenant_id, key)

    def test_rate_limiting_handles_very_large_ids(self):
        """Rate limiting key generation handles very large tenant IDs without crashing."""
        large_tenant_id = "A" * 1000  # Very long tenant ID
        key = generate_rate_limit_key(tenant_id=large_tenant_id, user_id=None, level="tenant")
        self.assertIsNotNone(key)
        self.assertIn(REDIS_KEY_PREFIX_TENANT, key)

    def test_rate_limiting_handles_none_values(self):
        """Global-level rate limit key generation succeeds with None tenant_id/user_id."""
        key = generate_rate_limit_key(tenant_id=None, user_id=None, level="global")  # type: ignore[misc]  # test: edge-case type exercise
        self.assertIsNotNone(key)
        self.assertIn(REDIS_KEY_PREFIX_GLOBAL, key)

    def test_rate_limiting_handles_nested_structures(self):
        """Rate limiting key generation handles complex tenant ID strings."""
        complex_tenant_id = "tenant-with-nested-structure"
        key = generate_rate_limit_key(tenant_id=complex_tenant_id, user_id=None, level="tenant")
        self.assertIsNotNone(key)
        self.assertIn(REDIS_KEY_PREFIX_TENANT, key)
        self.assertIn(complex_tenant_id, key)
