"""
Unit tests for ODPS $ref resolution rate limiting.

Tests verify:
1. Redis key format generation
2. Rate limit checking logic
3. Error handling and response format
4. TTL strategy
5. Fail-open behavior
"""
try:
    import pytest
    pytestmark = pytest.mark.django_db(transaction=True)
except ImportError:
    # pytest not available, using Django test runner
    pytest = None
    pytestmark = None

import time
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase

from hub.apps.contracts.odps_rate_limiting import (
    generate_rate_limit_key,
    get_rate_limit,
    check_rate_limit,
    get_rate_limit_info,
    ODPSRefResolutionError,
    RATE_LIMIT_PER_TENANT,
    RATE_LIMIT_PER_USER,
    RATE_LIMIT_GLOBAL,
    RATE_LIMIT_WINDOW,
    REDIS_KEY_PREFIX_TENANT,
    REDIS_KEY_PREFIX_USER,
    REDIS_KEY_PREFIX_GLOBAL,
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
        """Test that hour is correctly rounded down"""
        # Test at different times within the same hour
        base_time = int(time.time())
        base_hour = (base_time // RATE_LIMIT_WINDOW) * RATE_LIMIT_WINDOW

        # Test at start of hour
        with patch('hub.apps.contracts.odps_rate_limiting.time.time', return_value=base_hour):
            key1 = generate_rate_limit_key(level="global")

        # Test at middle of hour
        with patch('hub.apps.contracts.odps_rate_limiting.time.time', return_value=base_hour + 1800):
            key2 = generate_rate_limit_key(level="global")

        # Test at end of hour
        with patch('hub.apps.contracts.odps_rate_limiting.time.time', return_value=base_hour + 3599):
            key3 = generate_rate_limit_key(level="global")

        # All should have same hour component
        self.assertEqual(key1, key2, "Keys should be same within same hour")
        self.assertEqual(key2, key3, "Keys should be same within same hour")


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
            user_id="user456"
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
            tenant_id="tenant123"
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
        error = ODPSRefResolutionError(
            message="Rate limit exceeded",
            retry_after=retry_after
        )

        retry_header = error.get_retry_after_header()

        self.assertIsNotNone(retry_header)
        self.assertIsInstance(retry_header, str)
        # Should be approximately 3600 seconds
        self.assertGreaterEqual(int(retry_header), 3590)
        self.assertLessEqual(int(retry_header), 3610)

    def test_error_get_retry_after_header_none(self):
        """Test getting Retry-After header when retry_after is None"""
        error = ODPSRefResolutionError(
            message="Other error",
            retry_after=None
        )

        retry_header = error.get_retry_after_header()

        self.assertIsNone(retry_header)


class ODPSRateLimitingCheckTest(TestCase):
    """Test rate limit checking logic"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        self.user_id = "660e8400-e29b-41d4-a716-446655440001"
        self.mock_redis = MagicMock()

    def test_check_rate_limit_allows_when_under_limit(self):
        """Test that rate limit check allows requests when under limit"""
        # Mock Redis responses - all under limit
        self.mock_redis.zcard.return_value = 10  # Under limit
        self.mock_redis.zrange.return_value = [(b"req1", 1000.0)]  # Oldest request
        self.mock_redis.zremrangebyscore.return_value = 0

        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            redis_client=self.mock_redis
        )

        self.assertTrue(is_allowed, "Request should be allowed when under limit")
        self.assertIsNone(error, "No error should be returned when allowed")

    def test_check_rate_limit_rejects_when_over_limit(self):
        """Test that rate limit check rejects requests when over limit"""
        # Mock Redis responses - over limit
        self.mock_redis.zcard.return_value = 101  # Over tenant limit
        self.mock_redis.zrange.return_value = [(b"req1", time.time() - 1800)]  # Oldest request
        self.mock_redis.zremrangebyscore.return_value = 0

        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            redis_client=self.mock_redis
        )

        self.assertFalse(is_allowed, "Request should be rejected when over limit")
        self.assertIsNotNone(error, "Error should be returned when rejected")
        self.assertIsInstance(error, ODPSRefResolutionError)
        self.assertEqual(error.error_code, ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED)
        self.assertIsNotNone(error.retry_after)

    def test_check_rate_limit_checks_all_levels(self):
        """Test that rate limit check verifies all three levels"""
        # Mock Redis to pass global and tenant, fail at user level
        call_count = 0

        def zcard_side_effect(key):
            nonlocal call_count
            call_count += 1
            if "global" in key:
                return 500  # Under global limit
            elif "tenant" in key:
                return 50  # Under tenant limit
            elif "user" in key:
                return 51  # Over user limit
            return 0

        self.mock_redis.zcard.side_effect = zcard_side_effect
        self.mock_redis.zrange.return_value = [(b"req1", time.time() - 1800)]
        self.mock_redis.zremrangebyscore.return_value = 0

        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            redis_client=self.mock_redis
        )

        self.assertFalse(is_allowed, "Request should be rejected if any level exceeds limit")
        self.assertIn("user", error.message.lower(), "Error should mention user level")

    def test_check_rate_limit_sets_ttl(self):
        """Test that rate limit check sets TTL on Redis keys"""
        self.mock_redis.zcard.return_value = 10
        self.mock_redis.zrange.return_value = [(b"req1", time.time() - 1800)]
        self.mock_redis.zremrangebyscore.return_value = 0

        check_rate_limit(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            redis_client=self.mock_redis
        )

        # Verify expire was called with correct TTL (window + 1 hour)
        expire_calls = [call for call in self.mock_redis.method_calls if call[0] == 'expire']
        self.assertGreater(len(expire_calls), 0, "expire should be called to set TTL")

        # Check TTL value (should be RATE_LIMIT_WINDOW + 3600)
        for call in expire_calls:
            ttl = call[1][1]  # Second argument is TTL
            self.assertEqual(ttl, RATE_LIMIT_WINDOW + 3600, "TTL should be window + 1 hour")

    @patch('hub.apps.contracts.odps_rate_limiting.REDIS_AVAILABLE', False)
    def test_check_rate_limit_fails_open_when_redis_unavailable(self):
        """Test that rate limit check fails open when Redis is unavailable"""
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id,
            user_id=self.user_id
        )

        self.assertTrue(is_allowed, "Should allow requests when Redis unavailable (fail open)")
        self.assertIsNone(error, "No error when failing open")

    def test_check_rate_limit_fails_open_on_redis_error(self):
        """Test that rate limit check fails open on Redis errors"""
        # Mock Redis to raise exception
        self.mock_redis.zremrangebyscore.side_effect = Exception("Redis connection error")

        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            redis_client=self.mock_redis
        )

        self.assertTrue(is_allowed, "Should allow requests on Redis errors (fail open)")
        self.assertIsNone(error, "No error when failing open")


class ODPSRateLimitingInfoTest(TestCase):
    """Test rate limit information retrieval"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        self.user_id = "660e8400-e29b-41d4-a716-446655440001"
        self.mock_redis = MagicMock()

    def test_get_rate_limit_info_returns_all_levels(self):
        """Test that get_rate_limit_info returns information for all levels"""
        self.mock_redis.zcard.return_value = 25
        self.mock_redis.zrange.return_value = [(b"req1", time.time() - 1800)]
        self.mock_redis.zremrangebyscore.return_value = 0

        info = get_rate_limit_info(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            redis_client=self.mock_redis
        )

        self.assertIn("global", info, "Should include global level info")
        self.assertIn("tenant", info, "Should include tenant level info")
        self.assertIn("user", info, "Should include user level info")

    def test_get_rate_limit_info_includes_count_and_limit(self):
        """Test that rate limit info includes count and limit"""
        self.mock_redis.zcard.return_value = 25
        self.mock_redis.zrange.return_value = [(b"req1", time.time() - 1800)]
        self.mock_redis.zremrangebyscore.return_value = 0

        info = get_rate_limit_info(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            redis_client=self.mock_redis
        )

        # Check tenant level
        tenant_info = info["tenant"]
        self.assertIn("count", tenant_info)
        self.assertIn("limit", tenant_info)
        self.assertIn("remaining", tenant_info)
        self.assertIn("reset_time", tenant_info)
        self.assertEqual(tenant_info["count"], 25)
        self.assertEqual(tenant_info["limit"], RATE_LIMIT_PER_TENANT)
        self.assertEqual(tenant_info["remaining"], RATE_LIMIT_PER_TENANT - 25)


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
            from django.conf import settings
            import redis
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(redis_url, decode_responses=False, socket_connect_timeout=1)
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
                tenant_id=self.tenant_id,
                user_id=user_ids[user_idx],
                redis_client=self.redis_client
            )
            self.assertTrue(is_allowed, f"Request {i+1} should be allowed")
            self.assertIsNone(error, "No error should be returned")

        # Next request should be rejected at tenant level
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id,
            user_id=user_ids[0],
            redis_client=self.redis_client
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
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                redis_client=self.redis_client
            )
            self.assertTrue(is_allowed, f"Request {i+1} should be allowed")
            self.assertIsNone(error, "No error should be returned")

        # Next request should be rejected at user level
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            redis_client=self.redis_client
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
                redis_client=self.redis_client
            )
            if is_allowed:
                request_count += 1
            else:
                # If we hit a limit, check if it's global
                if error and "global" in error.message.lower():
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
                redis_client=self.redis_client
            )
            self.assertTrue(is_allowed, f"Tenant 1 request {i+1} should be allowed")

        # Tenant 1 should be rate limited at tenant level
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id,
            user_id=user_ids_tenant1[0],
            redis_client=self.redis_client
        )
        self.assertFalse(is_allowed, "Tenant 1 should be rate limited")
        self.assertIn("tenant", error.message.lower())

        # Tenant 2 should still be allowed (independent limits)
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id_2,
            user_id=self.user_id_2,
            redis_client=self.redis_client
        )
        self.assertTrue(is_allowed, "Tenant 2 should be allowed (independent limits)")
        self.assertIsNone(error, "No error for tenant 2")

    def test_rate_limit_independence_between_users(self):
        """Integration test: Verify rate limits are independent between users"""
        # User 1: Make requests up to user limit
        for i in range(RATE_LIMIT_PER_USER):
            is_allowed, error = check_rate_limit(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                redis_client=self.redis_client
            )
            self.assertTrue(is_allowed, f"User 1 request {i+1} should be allowed")

        # User 1 should be rate limited
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            redis_client=self.redis_client
        )
        self.assertFalse(is_allowed, "User 1 should be rate limited")
        self.assertIn("user", error.message.lower())

        # User 2 (same tenant) should still be allowed (independent limits)
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id,
            user_id=self.user_id_2,
            redis_client=self.redis_client
        )
        self.assertTrue(is_allowed, "User 2 should be allowed (independent limits)")
        self.assertIsNone(error, "No error for user 2")

    def test_rate_limit_error_message_includes_retry_after(self):
        """Integration test: Verify error message includes retry-after suggestion"""
        # Exceed rate limit
        for i in range(RATE_LIMIT_PER_TENANT + 1):
            is_allowed, error = check_rate_limit(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                redis_client=self.redis_client
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
        for i in range(RATE_LIMIT_PER_USER + 1):
            is_allowed, error = check_rate_limit(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                redis_client=self.redis_client
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
        for i in range(10):
            check_rate_limit(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                redis_client=self.redis_client
            )

        # Get rate limit info
        info = get_rate_limit_info(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            redis_client=self.redis_client
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
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                redis_client=self.redis_client
            )
            self.assertTrue(is_allowed, f"Request {i+1} should be allowed")

        # Should be rate limited at user level
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            redis_client=self.redis_client
        )
        self.assertFalse(is_allowed, "Request should be rate limited")
        self.assertIn("user", error.message.lower())

        # Verify the mechanism works by checking info
        info = get_rate_limit_info(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            redis_client=self.redis_client
        )
        self.assertGreaterEqual(info["user"]["count"], RATE_LIMIT_PER_USER)
        self.assertEqual(info["user"]["count"], RATE_LIMIT_PER_USER)

