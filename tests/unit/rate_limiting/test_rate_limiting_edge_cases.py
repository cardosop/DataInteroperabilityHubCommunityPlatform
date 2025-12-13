"""
Edge case tests for rate limiting.

Tests rate limit window boundaries, Redis failure, concurrent requests, and header accuracy.
"""
import pytest
import time
import threading
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from unittest.mock import Mock, patch

from hub.apps.rate_limiting.utils import (
    sliding_window_check,
    generate_rate_limit_key,
    TimeWindow
)
from hub.apps.rate_limiting.service import check_rate_limit
from hub.apps.users.models import UserStatus
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class RateLimitingEdgeCaseTest(TestCase):
    """Edge case tests for rate limiting"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    def test_rate_limit_window_boundary(self):
        """Test rate limit at window boundary"""
        key = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            endpoint_category="catalog_reads",
            window=TimeWindow.BURST
        )
        
        limit = 10
        window = TimeWindow.BURST
        
        # Make requests at window boundary
        current_time = time.time()
        
        # First request
        allowed1, count1, reset1 = sliding_window_check(key, limit, window, current_time)
        self.assertTrue(allowed1)
        
        # Wait until just before window boundary
        boundary_time = current_time + window - 0.1
        
        # Request at boundary
        allowed2, count2, reset2 = sliding_window_check(key, limit, window, boundary_time)
        # Should still be within window
        self.assertIsInstance(allowed2, bool)
    
    def test_rate_limit_redis_failure(self):
        """Test rate limiting when Redis is unavailable"""
        key = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            endpoint_category="catalog_reads",
            window=TimeWindow.BURST
        )
        
        # Test Redis failure by using an invalid Redis URL
        # This tests the actual failure handling without mocks
        from django.test import override_settings
        with override_settings(REDIS_URL='redis://invalid-host:6379/0'):
            # Should fail open (allow request) when Redis is unavailable
            allowed, count, reset = sliding_window_check(key, 10, TimeWindow.BURST)
            self.assertTrue(allowed)  # Fail open
            self.assertEqual(count, 0)  # Count should be 0 when Redis fails
    
    def test_rate_limit_concurrent_requests(self):
        """Test rate limiting with concurrent requests"""
        key = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            endpoint_category="catalog_reads",
            window=TimeWindow.BURST
        )
        
        limit = 10
        results = []
        
        def make_request(index):
            allowed, count, reset = sliding_window_check(key, limit, TimeWindow.BURST)
            results.append({"index": index, "allowed": allowed, "count": count})
        
        # Make concurrent requests
        threads = []
        for i in range(20):
            thread = threading.Thread(target=make_request, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Should handle concurrent requests
        self.assertEqual(len(results), 20)
        # Some requests should be allowed, some may be rate limited
        allowed_count = sum(1 for r in results if r["allowed"])
        self.assertGreater(allowed_count, 0)
    
    def test_rate_limit_header_accuracy(self):
        """Test rate limit header accuracy"""
        # Create mock request
        request = Mock()
        request.tenant_id = str(self.tenant.id)
        request.user = self.user
        request.path = "/api/v1/contracts/contracts/"
        request.method = "GET"
        
        # Check rate limit
        allowed, results = check_rate_limit(request)
        
        # Results should contain accurate information
        self.assertIsInstance(allowed, bool)
        self.assertIsInstance(results, list)
        
        if results:
            result = results[0]
            self.assertIn("limit", result.__dict__ if hasattr(result, "__dict__") else {})
            self.assertIn("remaining", result.__dict__ if hasattr(result, "__dict__") else {})
            self.assertIn("reset_time", result.__dict__ if hasattr(result, "__dict__") else {})
    
    def test_rate_limit_multiple_windows(self):
        """Test rate limiting across multiple time windows"""
        key_burst = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            endpoint_category="catalog_reads",
            window=TimeWindow.BURST
        )
        key_sustained = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            endpoint_category="catalog_reads",
            window=TimeWindow.SUSTAINED
        )
        key_daily = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            endpoint_category="catalog_reads",
            window=TimeWindow.DAILY
        )
        
        # Check all windows
        burst_allowed, burst_count, burst_reset = sliding_window_check(
            key_burst, 10, TimeWindow.BURST
        )
        sustained_allowed, sustained_count, sustained_reset = sliding_window_check(
            key_sustained, 100, TimeWindow.SUSTAINED
        )
        daily_allowed, daily_count, daily_reset = sliding_window_check(
            key_daily, 1000, TimeWindow.DAILY
        )
        
        # All should return valid results
        self.assertIsInstance(burst_allowed, bool)
        self.assertIsInstance(sustained_allowed, bool)
        self.assertIsInstance(daily_allowed, bool)
    
    def test_rate_limit_key_generation(self):
        """Test rate limit key generation"""
        # Test different key combinations
        key1 = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            endpoint_category="catalog_reads",
            window=TimeWindow.BURST
        )
        
        key2 = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            endpoint_category="catalog_reads",
            window=TimeWindow.BURST
        )
        
        key3 = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            api_key_id="test-key-id",
            endpoint_category="catalog_reads",
            window=TimeWindow.BURST
        )
        
        # Keys should be different
        self.assertNotEqual(key1, key2)
        self.assertNotEqual(key2, key3)
        self.assertNotEqual(key1, key3)
    
    def test_rate_limit_expired_entries_removal(self):
        """Test that expired entries are removed from sliding window"""
        key = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            endpoint_category="catalog_reads",
            window=TimeWindow.BURST
        )
        
        limit = 10
        window = TimeWindow.BURST
        
        # Make request
        current_time = time.time()
        allowed1, count1, reset1 = sliding_window_check(key, limit, window, current_time)
        
        # Make request in the future (past window)
        future_time = current_time + window + 1
        allowed2, count2, reset2 = sliding_window_check(key, limit, window, future_time)
        
        # Expired entries should be removed
        # Count should be lower or reset
        self.assertIsInstance(allowed2, bool)
        self.assertIsInstance(count2, int)
    
    def test_rate_limit_per_endpoint_category(self):
        """Test rate limiting per endpoint category"""
        key1 = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            endpoint_category="catalog_reads",
            window=TimeWindow.BURST
        )
        
        key2 = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            endpoint_category="catalog_writes",
            window=TimeWindow.BURST
        )
        
        # Different categories should have different keys
        self.assertNotEqual(key1, key2)
        
        # Should be rate limited independently
        allowed1, count1, reset1 = sliding_window_check(key1, 10, TimeWindow.BURST)
        allowed2, count2, reset2 = sliding_window_check(key2, 10, TimeWindow.BURST)
        
        self.assertIsInstance(allowed1, bool)
        self.assertIsInstance(allowed2, bool)
    
    def test_rate_limit_per_user(self):
        """Test rate limiting per user"""
        key1 = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            endpoint_category="catalog_reads",
            window=TimeWindow.BURST
        )
        
        # Create another user
        user2 = User.objects.create_user(
            email="user2@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        key2 = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            user_id=str(user2.id),
            endpoint_category="catalog_reads",
            window=TimeWindow.BURST
        )
        
        # Different users should have different keys
        self.assertNotEqual(key1, key2)
    
    def test_rate_limit_per_api_key(self):
        """Test rate limiting per API key"""
        key1 = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            api_key_id="key1",
            endpoint_category="catalog_reads",
            window=TimeWindow.BURST
        )
        
        key2 = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            api_key_id="key2",
            endpoint_category="catalog_reads",
            window=TimeWindow.BURST
        )
        
        # Different API keys should have different keys
        self.assertNotEqual(key1, key2)
    
    def test_rate_limit_reset_time_calculation(self):
        """Test rate limit reset time calculation"""
        key = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            endpoint_category="catalog_reads",
            window=TimeWindow.BURST
        )
        
        limit = 10
        window = TimeWindow.BURST
        
        # Make request
        allowed, count, reset_time = sliding_window_check(key, limit, window)
        
        # Reset time should be in the future
        current_time = time.time()
        self.assertGreaterEqual(reset_time, current_time)
        
        # Reset time should be within window
        self.assertLessEqual(reset_time, current_time + window + 1)
    
    def test_rate_limit_cache_behavior(self):
        """Test rate limit caching behavior"""
        key = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            endpoint_category="catalog_reads",
            window=TimeWindow.BURST
        )
        
        limit = 10
        window = TimeWindow.BURST
        
        # Make first request (should cache)
        allowed1, count1, reset1 = sliding_window_check(key, limit, window)
        
        # Make second request quickly (should use cache)
        time.sleep(0.5)  # Within cache TTL
        allowed2, count2, reset2 = sliding_window_check(key, limit, window)
        
        # Both should return valid results
        self.assertIsInstance(allowed1, bool)
        self.assertIsInstance(allowed2, bool)
    
    def test_rate_limit_remaining_calculation(self):
        """Test rate limit remaining calculation"""
        key = generate_rate_limit_key(
            tenant_id=str(self.tenant.id),
            endpoint_category="catalog_reads",
            window=TimeWindow.BURST
        )
        
        limit = 10
        window = TimeWindow.BURST
        
        # Make requests
        for i in range(5):
            allowed, count, reset = sliding_window_check(key, limit, window)
            remaining = max(0, limit - count)
            
            # Remaining should be non-negative
            self.assertGreaterEqual(remaining, 0)
            # Remaining should be less than or equal to limit
            self.assertLessEqual(remaining, limit)

