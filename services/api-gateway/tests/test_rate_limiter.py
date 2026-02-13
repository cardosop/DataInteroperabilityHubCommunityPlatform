"""
Unit tests for rate limiter using real Redis.

These tests require Redis to be available and will skip if Redis is not available.
No mocks or stubs are used - all tests use real Redis connections.
"""
import pytest
import time
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from rate_limiter import RateLimiter, RateLimitTier


@pytest.mark.unit
class TestRateLimiter:
    """Test rate limiter functionality with real Redis"""

    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter instance with real Redis"""
        redis_url = os.getenv('REDIS_CACHE_URL') or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        limiter = RateLimiter(redis_url=redis_url)

        # Skip tests if Redis is not available
        if limiter.redis_client is None:
            pytest.skip("Redis not available - cannot run tests without Redis")

        # Test connection
        try:
            if limiter.redis_client:
                limiter.redis_client.ping()
        except Exception as e:
            pytest.skip(f"Redis connection failed: {e}")

        yield limiter

        # Cleanup: Remove test keys
        if limiter.redis_client:
            try:
                # Clean up any test keys
                test_keys = limiter.redis_client.keys("rate_limit:test_*")
                if test_keys:
                    limiter.redis_client.delete(*test_keys)
            except Exception:
                pass  # Ignore cleanup errors

    def test_rate_limiter_init_with_redis(self, rate_limiter):
        """Test rate limiter initialization with Redis"""
        assert rate_limiter.redis_client is not None
        assert rate_limiter.redis_client.ping() is True

    def test_check_rate_limit_unlimited(self, rate_limiter):
        """Test rate limit check with unlimited limit"""
        # Use a unique key for this test
        test_key = f"rate_limit:test_unlimited_{int(time.time() * 1000000)}"

        allowed, count, reset = rate_limiter.check_rate_limit(test_key, None, window=3600)
        assert allowed is True
        # For unlimited limits, count is 0 (no tracking needed)
        assert count == 0
        assert reset > 0

    def test_check_rate_limit_with_redis(self, rate_limiter):
        """Test rate limit check with Redis - requests within limit"""
        test_key = f"rate_limit:test_within_limit_{int(time.time() * 1000000)}"

        # First request should be allowed
        allowed1, count1, reset1 = rate_limiter.check_rate_limit(test_key, 10, window=3600)
        assert allowed1 is True
        assert count1 == 1
        assert reset1 > 0

        # Second request should be allowed
        allowed2, count2, reset2 = rate_limiter.check_rate_limit(test_key, 10, window=3600)
        assert allowed2 is True
        assert count2 == 2
        assert reset2 > 0

    def test_check_rate_limit_exceeded(self, rate_limiter):
        """Test rate limit check when limit is exceeded"""
        test_key = f"rate_limit:test_exceeded_{int(time.time() * 1000000)}"
        limit = 3  # Small limit for testing

        # Make requests up to limit
        for i in range(limit):
            allowed, count, reset = rate_limiter.check_rate_limit(test_key, limit, window=3600)
            assert allowed is True
            assert count == i + 1

        # Next request should be denied
        allowed, count, reset = rate_limiter.check_rate_limit(test_key, limit, window=3600)
        assert allowed is False
        assert count == limit
        assert reset > 0

    def test_check_tier_limit_free(self, rate_limiter):
        """Test tier limit check for FREE tier"""
        # Use a unique key by including timestamp
        # The tier limit check uses a shared key per tier, so we need to be careful
        # For this test, we'll check that FREE tier has a limit
        allowed, count, reset = rate_limiter.check_tier_limit('FREE')
        assert allowed is True  # Should be within limit
        assert count >= 0
        assert reset > 0

    def test_check_tier_limit_enterprise(self, rate_limiter):
        """Test tier limit check for ENTERPRISE tier (unlimited)"""
        allowed, count, reset = rate_limiter.check_tier_limit('ENTERPRISE')
        assert allowed is True
        assert count >= 0
        assert reset > 0

    def test_check_tier_limit_pro(self, rate_limiter):
        """Test tier limit check for PRO tier"""
        allowed, count, reset = rate_limiter.check_tier_limit('PRO')
        assert allowed is True  # Should be within limit
        assert count >= 0
        assert reset > 0

    def test_sliding_window_algorithm(self, rate_limiter):
        """Test that sliding window algorithm works correctly"""
        test_key = f"rate_limit:test_sliding_{int(time.time() * 1000000)}"
        limit = 5
        window = 2  # 2 second window for faster testing

        # Make requests up to limit
        for i in range(limit):
            allowed, count, reset = rate_limiter.check_rate_limit(test_key, limit, window=window)
            assert allowed is True
            assert count == i + 1

        # Next request should be denied
        allowed, count, reset = rate_limiter.check_rate_limit(test_key, limit, window=window)
        assert allowed is False

        # Wait for window to expire
        time.sleep(window + 0.5)

        # Request should be allowed again (old requests expired)
        allowed, count, reset = rate_limiter.check_rate_limit(test_key, limit, window=window)
        assert allowed is True
        assert count == 1  # Only the new request

    def test_check_tenant_limit(self, rate_limiter):
        """Test tenant limit check within limit"""
        tenant_id = f"test-tenant-{int(time.time() * 1000000)}"
        limit = 10

        allowed, count, reset = rate_limiter.check_tenant_limit(tenant_id, limit=limit)
        assert allowed is True
        assert count == 1
        assert reset > 0

    def test_check_tenant_limit_none_skips(self, rate_limiter):
        """When tenant limit is None, no custom limit at this level (tier only)."""
        tenant_id = f"test-tenant-none-{int(time.time() * 1000000)}"
        allowed, count, reset = rate_limiter.check_tenant_limit(tenant_id, limit=None)
        assert allowed is True
        assert count == 0
        assert reset > 0

    def test_check_tenant_limit_enforced_exceeded(self, rate_limiter):
        """When tenant has custom limit, that limit is enforced (sliding window, Redis)."""
        tenant_id = f"test-tenant-exceed-{int(time.time() * 1000000)}"
        limit = 2
        for i in range(limit):
            allowed, count, reset = rate_limiter.check_tenant_limit(tenant_id, limit=limit)
            assert allowed is True, f"Request {i + 1} should be allowed"
            assert count == i + 1
        allowed, count, reset = rate_limiter.check_tenant_limit(tenant_id, limit=limit)
        assert allowed is False
        assert count == limit
        assert reset > 0

    def test_check_api_key_limit(self, rate_limiter):
        """Test API key limit check within limit"""
        api_key_id = f"test-api-key-{int(time.time() * 1000000)}"
        limit = 10

        allowed, count, reset = rate_limiter.check_api_key_limit(api_key_id, limit=limit)
        assert allowed is True
        assert count == 1
        assert reset > 0

    def test_check_api_key_limit_none_skips(self, rate_limiter):
        """When API key limit is None, no custom limit at this level (tier only)."""
        api_key_id = f"test-apikey-none-{int(time.time() * 1000000)}"
        allowed, count, reset = rate_limiter.check_api_key_limit(api_key_id, limit=None)
        assert allowed is True
        assert count == 0
        assert reset > 0

    def test_check_api_key_limit_enforced_exceeded(self, rate_limiter):
        """When API key has custom limit, that limit is enforced (sliding window, Redis)."""
        api_key_id = f"test-apikey-exceed-{int(time.time() * 1000000)}"
        limit = 2
        for i in range(limit):
            allowed, count, reset = rate_limiter.check_api_key_limit(api_key_id, limit=limit)
            assert allowed is True, f"Request {i + 1} should be allowed"
            assert count == i + 1
        allowed, count, reset = rate_limiter.check_api_key_limit(api_key_id, limit=limit)
        assert allowed is False
        assert count == limit
        assert reset > 0

    def test_get_rate_limit_info(self, rate_limiter):
        """Test getting rate limit info without incrementing"""
        test_key = f"rate_limit:test_info_{int(time.time() * 1000000)}"

        # Get info before any requests
        info1 = rate_limiter.get_rate_limit_info(test_key, window=3600)
        assert info1['count'] == 0
        assert info1['reset_time'] > 0

        # Make a request
        rate_limiter.check_rate_limit(test_key, 10, window=3600)

        # Get info after request
        info2 = rate_limiter.get_rate_limit_info(test_key, window=3600)
        assert info2['count'] == 1
        assert info2['reset_time'] > 0
