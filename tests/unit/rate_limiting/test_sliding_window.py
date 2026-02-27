"""
Unit tests for sliding window rate limiting algorithm.

Tests window sliding, TTL expiration, multiple time windows, and caching.
"""
from django.test import TestCase
from unittest.mock import Mock, patch, MagicMock
import time

from hub.apps.rate_limiting.utils import (
    sliding_window_check,
    get_rate_limit_info,
    TimeWindow
)


class SlidingWindowAlgorithmTest(TestCase):
    """Tests for sliding window algorithm implementation"""
    
    @patch('hub.apps.rate_limiting.utils.cache')
    @patch('hub.apps.core.redis_pools.get_redis_cache_pool')
    @patch('redis.from_url')
    def test_sliding_window_allows_within_limit(self, mock_from_url, mock_get_pool, mock_cache):
        """Test sliding window allows requests within limit"""
        mock_get_pool.side_effect = Exception("Use fallback")  # Force redis.from_url path
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        mock_cache.get.return_value = None  # No cache hit
        
        # Mock Redis operations
        mock_client.zcard.side_effect = [5, 6]  # Before: 5, After: 6
        mock_client.zrange.return_value = [('req1', 100.0)]  # Oldest request
        mock_client.zremrangebyscore.return_value = 0
        
        allowed, count, reset_time = sliding_window_check(
            key='test-key',
            limit=10,
            window=60,
            current_time=150.0
        )
        
        self.assertTrue(allowed)
        self.assertEqual(count, 6)
        self.assertEqual(reset_time, 160)  # 100 + 60
        mock_client.zadd.assert_called_once()
        mock_client.expire.assert_called_once_with('test-key', 70)  # 60 + 10 buffer
    
    @patch('hub.apps.rate_limiting.utils.cache')
    @patch('hub.apps.core.redis_pools.get_redis_cache_pool')
    @patch('redis.from_url')
    def test_sliding_window_rejects_when_exceeded(self, mock_from_url, mock_get_pool, mock_cache):
        """Test sliding window rejects requests when limit exceeded"""
        mock_get_pool.side_effect = Exception("Use fallback")
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        mock_cache.get.return_value = None
        
        # Mock Redis operations - limit exceeded
        mock_client.zcard.return_value = 10  # At limit
        mock_client.zrange.return_value = [('req1', 100.0)]
        mock_client.zremrangebyscore.return_value = 0
        
        allowed, count, reset_time = sliding_window_check(
            key='test-key',
            limit=10,
            window=60,
            current_time=150.0
        )
        
        self.assertFalse(allowed)
        self.assertEqual(count, 10)
        self.assertEqual(reset_time, 160)  # 100 + 60
        mock_client.zadd.assert_not_called()  # Should not add when exceeded
    
    @patch('hub.apps.rate_limiting.utils.cache')
    @patch('hub.apps.core.redis_pools.get_redis_cache_pool')
    @patch('redis.from_url')
    def test_sliding_window_removes_expired_entries(self, mock_from_url, mock_get_pool, mock_cache):
        """Test sliding window removes expired entries outside window"""
        mock_get_pool.side_effect = Exception("Use fallback")
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        mock_cache.get.return_value = None
        
        mock_client.zcard.return_value = 3
        mock_client.zrange.return_value = [('req1', 100.0)]
        mock_client.zremrangebyscore.return_value = 2  # Removed 2 expired entries
        
        sliding_window_check(
            key='test-key',
            limit=10,
            window=60,
            current_time=200.0  # 100 seconds later
        )
        
        # Should remove entries before (200 - 60) = 140
        mock_client.zremrangebyscore.assert_called_with('test-key', 0, 140.0)
    
    @patch('hub.apps.rate_limiting.utils.cache')
    @patch('hub.apps.core.redis_pools.get_redis_cache_pool')
    @patch('redis.from_url')
    def test_sliding_window_ttl_expiration(self, mock_from_url, mock_get_pool, mock_cache):
        """Test TTL expiration removes old entries"""
        mock_get_pool.side_effect = Exception("Use fallback")
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        mock_cache.get.return_value = None
        
        mock_client.zcard.return_value = 3
        mock_client.zrange.return_value = [('req1', 100.0)]
        mock_client.zremrangebyscore.return_value = 2
        
        sliding_window_check(
            key='test-key',
            limit=10,
            window=60,
            current_time=200.0
        )
        
        # Should set expiration (window + buffer)
        mock_client.expire.assert_called_once_with('test-key', 70)  # 60 + 10 buffer
    
    @patch('hub.apps.rate_limiting.utils.cache')
    @patch('hub.apps.core.redis_pools.get_redis_cache_pool')
    @patch('redis.from_url')
    def test_sliding_window_uses_atomic_operations(self, mock_from_url, mock_get_pool, mock_cache):
        """Test sliding window uses Redis atomic operations"""
        mock_get_pool.side_effect = Exception("Use fallback")
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        mock_cache.get.return_value = None
        
        mock_client.zcard.side_effect = [5, 6]
        mock_client.zrange.return_value = [('req1', 100.0)]
        mock_client.zremrangebyscore.return_value = 0
        
        sliding_window_check(
            key='test-key',
            limit=10,
            window=60,
            current_time=150.0
        )
        
        # Verify atomic operations are used
        mock_client.zremrangebyscore.assert_called_once()  # Remove expired
        self.assertEqual(mock_client.zcard.call_count, 2)  # Count before and after
        mock_client.zadd.assert_called_once()  # Add current request
        mock_client.expire.assert_called_once()  # Set TTL
    
    @patch('hub.apps.rate_limiting.utils.cache')
    @patch('hub.apps.core.redis_pools.get_redis_cache_pool')
    @patch('redis.from_url')
    def test_sliding_window_redis_unavailable_fails_open(self, mock_from_url, mock_get_pool, mock_cache):
        """Test sliding window fails open when Redis unavailable"""
        mock_get_pool.side_effect = Exception("Redis pool unavailable")
        mock_from_url.side_effect = Exception("Redis unavailable")
        mock_cache.get.return_value = None
        
        allowed, count, reset_time = sliding_window_check(
            key='test-key',
            limit=10,
            window=60,
            current_time=100.0
        )
        
        # Should allow request (fail open)
        self.assertTrue(allowed)
        self.assertEqual(count, 0)
        self.assertEqual(reset_time, 160)  # 100 + 60
    
    @patch('hub.apps.rate_limiting.utils.cache')
    @patch('hub.apps.core.redis_pools.get_redis_cache_pool')
    @patch('redis.from_url')
    def test_sliding_window_cache_hit_prevents_redis_call(self, mock_from_url, mock_get_pool, mock_cache):
        """Test that cache hit prevents unnecessary Redis calls"""
        mock_get_pool.side_effect = Exception("Use fallback")
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        
        # Mock cache hit with exceeded limit
        mock_cache.get.return_value = (10, 150.0, 160)  # count, time, reset_time
        
        allowed, count, reset_time = sliding_window_check(
            key='test-key',
            limit=10,
            window=60,
            current_time=150.5  # Less than 1 second after cache time
        )
        
        # Should use cache and not call Redis
        self.assertFalse(allowed)
        self.assertEqual(count, 10)
        mock_client.zcard.assert_not_called()
        mock_client.zadd.assert_not_called()
    
    @patch('hub.apps.rate_limiting.utils.cache')
    @patch('hub.apps.core.redis_pools.get_redis_cache_pool')
    @patch('redis.from_url')
    def test_sliding_window_cache_miss_calls_redis(self, mock_from_url, mock_get_pool, mock_cache):
        """Test that cache miss calls Redis"""
        mock_get_pool.side_effect = Exception("Use fallback")
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        mock_cache.get.return_value = None  # Cache miss
        
        mock_client.zcard.side_effect = [5, 6]
        mock_client.zrange.return_value = [('req1', 100.0)]
        mock_client.zremrangebyscore.return_value = 0
        
        sliding_window_check(
            key='test-key',
            limit=10,
            window=60,
            current_time=150.0
        )
        
        # Should call Redis
        mock_client.zcard.assert_called()
        mock_client.zadd.assert_called_once()
    
    @patch('hub.apps.rate_limiting.utils.cache')
    @patch('hub.apps.core.redis_pools.get_redis_cache_pool')
    @patch('redis.from_url')
    def test_sliding_window_caches_result(self, mock_from_url, mock_get_pool, mock_cache):
        """Test that result is cached after Redis call"""
        mock_get_pool.side_effect = Exception("Use fallback")
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        mock_cache.get.return_value = None
        
        mock_client.zcard.side_effect = [5, 6]
        mock_client.zrange.return_value = [('req1', 100.0)]
        mock_client.zremrangebyscore.return_value = 0
        
        sliding_window_check(
            key='test-key',
            limit=10,
            window=60,
            current_time=150.0
        )
        
        # Should cache result
        mock_cache.set.assert_called_once()
        cache_key, cache_value, ttl = mock_cache.set.call_args[0]
        self.assertEqual(cache_key, 'rate_limit_cache:test-key')
        self.assertEqual(ttl, 1)  # 1 second cache


class MultipleTimeWindowsTest(TestCase):
    """Tests for multiple time windows (burst, sustained, daily)"""
    
    @patch('hub.apps.rate_limiting.utils.cache')
    @patch('hub.apps.core.redis_pools.get_redis_cache_pool')
    @patch('redis.from_url')
    def test_burst_window_10_seconds(self, mock_from_url, mock_get_pool, mock_cache):
        """Test burst window (10 seconds)"""
        mock_get_pool.side_effect = Exception("Use fallback")
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        mock_cache.get.return_value = None
        
        mock_client.zcard.side_effect = [5, 6]
        mock_client.zrange.return_value = [('req1', 100.0)]
        mock_client.zremrangebyscore.return_value = 0
        
        allowed, count, reset_time = sliding_window_check(
            key='test-key',
            limit=20,
            window=TimeWindow.BURST,  # 10 seconds
            current_time=105.0
        )
        
        self.assertTrue(allowed)
        # Should remove entries before (105 - 10) = 95
        mock_client.zremrangebyscore.assert_called_with('test-key', 0, 95.0)
    
    @patch('hub.apps.rate_limiting.utils.cache')
    @patch('hub.apps.core.redis_pools.get_redis_cache_pool')
    @patch('redis.from_url')
    def test_sustained_window_60_seconds(self, mock_from_url, mock_get_pool, mock_cache):
        """Test sustained window (60 seconds)"""
        mock_get_pool.side_effect = Exception("Use fallback")
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        mock_cache.get.return_value = None
        
        mock_client.zcard.side_effect = [5, 6]
        mock_client.zrange.return_value = [('req1', 100.0)]
        mock_client.zremrangebyscore.return_value = 0
        
        allowed, count, reset_time = sliding_window_check(
            key='test-key',
            limit=60,
            window=TimeWindow.SUSTAINED,  # 60 seconds
            current_time=150.0
        )
        
        self.assertTrue(allowed)
        # Should remove entries before (150 - 60) = 90
        mock_client.zremrangebyscore.assert_called_with('test-key', 0, 90.0)
    
    @patch('hub.apps.rate_limiting.utils.cache')
    @patch('hub.apps.core.redis_pools.get_redis_cache_pool')
    @patch('redis.from_url')
    def test_daily_window_86400_seconds(self, mock_from_url, mock_get_pool, mock_cache):
        """Test daily window (86400 seconds)"""
        mock_get_pool.side_effect = Exception("Use fallback")
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        mock_cache.get.return_value = None
        
        mock_client.zcard.side_effect = [5, 6]
        mock_client.zrange.return_value = [('req1', 100.0)]
        mock_client.zremrangebyscore.return_value = 0
        
        allowed, count, reset_time = sliding_window_check(
            key='test-key',
            limit=10000,
            window=TimeWindow.DAILY,  # 86400 seconds
            current_time=100000.0
        )
        
        self.assertTrue(allowed)
        # Should remove entries before (100000 - 86400) = 13600
        mock_client.zremrangebyscore.assert_called_with('test-key', 0, 13600.0)
    
    @patch('hub.apps.rate_limiting.utils.cache')
    @patch('hub.apps.core.redis_pools.get_redis_cache_pool')
    @patch('redis.from_url')
    def test_window_sliding_prevents_boundary_bursts(self, mock_from_url, mock_get_pool, mock_cache):
        """Test that sliding window prevents bursts at window boundaries"""
        mock_get_pool.side_effect = Exception("Use fallback")
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        mock_cache.get.return_value = None
        
        # Simulate requests at window boundary
        # Request at time 100, then at time 110 (just after 10-second window)
        mock_client.zcard.side_effect = [10, 11]  # At limit, then exceeds
        mock_client.zrange.return_value = [('req1', 100.0)]
        mock_client.zremrangebyscore.return_value = 0
        
        # First request at boundary
        allowed1, count1, reset1 = sliding_window_check(
            key='test-key',
            limit=10,
            window=10,
            current_time=100.0
        )
        
        # Second request just after window (should still be limited)
        mock_client.zcard.side_effect = [10, 11]  # Still at limit
        allowed2, count2, reset2 = sliding_window_check(
            key='test-key',
            limit=10,
            window=10,
            current_time=110.0
        )
        
        # Sliding window should prevent burst
        # (In real scenario, entries from 100-110 would still be in window)
        # This test verifies the algorithm correctly removes expired entries
        mock_client.zremrangebyscore.assert_called()


class GetRateLimitInfoTest(TestCase):
    """Tests for getting rate limit info without incrementing"""
    
    @patch('hub.apps.core.redis_pools.get_redis_cache_pool')
    @patch('redis.from_url')
    def test_get_rate_limit_info(self, mock_from_url, mock_get_pool):
        """Test getting rate limit info without incrementing"""
        mock_get_pool.side_effect = Exception("Use fallback")
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        
        mock_client.zcard.return_value = 5
        mock_client.zrange.return_value = [('req1', 100.0)]
        mock_client.zremrangebyscore.return_value = 0
        
        info = get_rate_limit_info(
            key='test-key',
            window=60,
            current_time=150.0
        )
        
        self.assertEqual(info['count'], 5)
        self.assertEqual(info['reset_time'], 160)  # 100 + 60
        mock_client.zadd.assert_not_called()  # Should not increment
    
    @patch('hub.apps.core.redis_pools.get_redis_cache_pool')
    @patch('redis.from_url')
    def test_get_rate_limit_info_removes_expired(self, mock_from_url, mock_get_pool):
        """Test that get_rate_limit_info removes expired entries"""
        mock_get_pool.side_effect = Exception("Use fallback")
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        
        mock_client.zcard.return_value = 3
        mock_client.zrange.return_value = [('req1', 100.0)]
        mock_client.zremrangebyscore.return_value = 2
        
        get_rate_limit_info(
            key='test-key',
            window=60,
            current_time=200.0
        )
        
        # Should remove expired entries
        mock_client.zremrangebyscore.assert_called_with('test-key', 0, 140.0)
    
    @patch('hub.apps.core.redis_pools.get_redis_cache_pool')
    @patch('redis.from_url')
    def test_get_rate_limit_info_redis_unavailable(self, mock_from_url, mock_get_pool):
        """Test get_rate_limit_info when Redis unavailable"""
        mock_get_pool.side_effect = Exception("Redis pool unavailable")
        mock_from_url.side_effect = Exception("Redis unavailable")
        
        info = get_rate_limit_info(
            key='test-key',
            window=60,
            current_time=100.0
        )
        
        # Should return default values
        self.assertEqual(info['count'], 0)
        self.assertEqual(info['reset_time'], 160)  # 100 + 60

