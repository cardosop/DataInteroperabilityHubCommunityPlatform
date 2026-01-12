"""
Performance tests for API Gateway service.

These tests measure performance of rate limiting operations.
All tests use real Redis - no mocks or stubs.
"""
import pytest
import time
import concurrent.futures
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from rate_limiter import RateLimiter


@pytest.mark.performance
class TestRateLimiterPerformance:
    """Performance tests for rate limiter"""

    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter instance"""
        redis_url = os.getenv('REDIS_CACHE_URL', 'redis://localhost:6379/0')
        limiter = RateLimiter(redis_url=redis_url)

        # Skip if Redis is not available
        if limiter.redis_client is None:
            pytest.skip("Redis not available - cannot run performance tests without Redis")

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
                test_keys = limiter.redis_client.keys("rate_limit:perf_test_*")
                if test_keys:
                    limiter.redis_client.delete(*test_keys)
            except Exception:
                pass

    def test_rate_limit_check_performance(self, rate_limiter):
        """Test rate limit check performance"""
        key = f"rate_limit:perf_test_{int(time.time() * 1000000)}"

        # Measure time for 100 rate limit checks
        start_time = time.time()
        for i in range(100):
            rate_limiter.check_rate_limit(key, 1000, window=3600)
        duration = time.time() - start_time

        # Should complete 100 checks in under 1 second
        assert duration < 1.0, f"100 checks took {duration:.2f}s, expected < 1.0s"

        # Cleanup
        rate_limiter.redis_client.delete(key)

    def test_concurrent_rate_limit_checks(self, rate_limiter):
        """Test concurrent rate limit checks"""
        key = f"rate_limit:perf_test_concurrent_{int(time.time() * 1000000)}"

        def check_limit():
            return rate_limiter.check_rate_limit(key, 1000, window=3600)

        # Run 50 concurrent checks
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_limit) for _ in range(50)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        duration = time.time() - start_time

        # Should complete 50 concurrent checks in under 2 seconds
        assert duration < 2.0, f"50 concurrent checks took {duration:.2f}s, expected < 2.0s"

        # All should be allowed (within limit)
        assert all(r[0] for r in results), "All requests should be allowed"

        # Cleanup
        rate_limiter.redis_client.delete(key)

    def test_tier_limit_check_performance(self, rate_limiter):
        """Test tier limit check performance"""
        start_time = time.time()
        for i in range(100):
            rate_limiter.check_tier_limit('FREE')
        duration = time.time() - start_time

        # Should complete 100 tier limit checks in under 1 second
        assert duration < 1.0, f"100 tier limit checks took {duration:.2f}s, expected < 1.0s"

    def test_get_rate_limit_info_performance(self, rate_limiter):
        """Test get rate limit info performance"""
        key = f"rate_limit:perf_test_info_{int(time.time() * 1000000)}"

        # Add some requests first
        for i in range(10):
            rate_limiter.check_rate_limit(key, 1000, window=3600)

        # Measure time for 100 info requests
        start_time = time.time()
        for i in range(100):
            rate_limiter.get_rate_limit_info(key, window=3600)
        duration = time.time() - start_time

        # Should complete 100 info requests in under 1 second
        assert duration < 1.0, f"100 info requests took {duration:.2f}s, expected < 1.0s"

        # Cleanup
        rate_limiter.redis_client.delete(key)
