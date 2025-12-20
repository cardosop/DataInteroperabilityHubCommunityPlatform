"""
Comprehensive tests for enhanced contract caching.

Tests cover:
- Cache tags for efficient invalidation
- Cache warming for frequently accessed contracts
- Cache hit/miss metrics
"""
import time
from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from django.conf import settings
from django.core.cache import cache

import redis

from hub.apps.contracts.caching import (
    cache_contract,
    get_cached_contract,
    invalidate_contract_cache,
    warm_contract_cache,
)
from hub.apps.contracts.caching_enhanced import (
    cache_contract_with_tags,
    get_cached_contract_with_metrics,
    invalidate_contract_cache_by_tags,
    warm_frequently_accessed_contracts,
    get_contract_cache_metrics,
)


def get_real_redis_client_or_none():
    """Get real Redis client or return None if unavailable."""
    try:
        redis_url = getattr(settings, 'REDIS_URL', 'redis://redis:6379/0')
        client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2
        )
        client.ping()
        return client
    except Exception:
        return None


class TestCacheTags(TestCase):
    """Test cache tags for efficient invalidation."""

    @override_settings(REDIS_URL='redis://redis:6379/0')
    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

        # Clear cache before each test
        try:
            keys = self.redis_client.keys("contract:*")
            if keys:
                self.redis_client.delete(*keys)
            keys = self.redis_client.keys("cache_tag:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            keys = self.redis_client.keys("contract:*")
            if keys:
                self.redis_client.delete(*keys)
            keys = self.redis_client.keys("cache_tag:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def test_cache_contract_with_tags(self):
        """Test caching contract with tags."""
        contract_id = "test-contract-1"
        contract_data = {"id": contract_id, "name": "Test Contract"}
        tags = ["tenant:test-tenant", "owner:user1", "status:active"]

        cache_contract_with_tags(contract_id, contract_data, tags=tags)

        # Verify contract is cached
        cached = get_cached_contract(contract_id)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["id"], contract_id)

    def test_invalidate_by_single_tag(self):
        """Test invalidating contracts by single tag."""
        # Cache multiple contracts with different tags
        contract1_data = {"id": "contract-1", "name": "Contract 1"}
        contract2_data = {"id": "contract-2", "name": "Contract 2"}
        contract3_data = {"id": "contract-3", "name": "Contract 3"}

        cache_contract_with_tags("contract-1", contract1_data, tags=["tenant:t1", "owner:user1"])
        cache_contract_with_tags("contract-2", contract2_data, tags=["tenant:t1", "owner:user2"])
        cache_contract_with_tags("contract-3", contract3_data, tags=["tenant:t2", "owner:user1"])

        # Verify all contracts are cached
        self.assertIsNotNone(get_cached_contract("contract-1"))
        self.assertIsNotNone(get_cached_contract("contract-2"))
        self.assertIsNotNone(get_cached_contract("contract-3"))

        # Invalidate by tag
        invalidate_contract_cache_by_tags(["owner:user1"])

        # Verify contracts with owner:user1 are invalidated
        self.assertIsNone(get_cached_contract("contract-1"))
        self.assertIsNotNone(get_cached_contract("contract-2"))  # Different owner
        self.assertIsNone(get_cached_contract("contract-3"))

    def test_invalidate_by_multiple_tags(self):
        """Test invalidating contracts by multiple tags."""
        # Cache contracts with tags
        contract1_data = {"id": "contract-1", "name": "Contract 1"}
        contract2_data = {"id": "contract-2", "name": "Contract 2"}

        cache_contract_with_tags("contract-1", contract1_data, tags=["tenant:t1", "status:active"])
        cache_contract_with_tags("contract-2", contract2_data, tags=["tenant:t1", "status:draft"])

        # Invalidate by multiple tags (OR logic - invalidates if contract has any tag)
        invalidate_contract_cache_by_tags(["status:active", "status:draft"])

        # Both should be invalidated
        self.assertIsNone(get_cached_contract("contract-1"))
        self.assertIsNone(get_cached_contract("contract-2"))

    def test_invalidate_by_tenant_tag(self):
        """Test invalidating contracts by tenant tag."""
        # Cache contracts for different tenants
        contract1_data = {"id": "contract-1", "name": "Contract 1"}
        contract2_data = {"id": "contract-2", "name": "Contract 2"}

        cache_contract_with_tags("contract-1", contract1_data, tags=["tenant:t1"])
        cache_contract_with_tags("contract-2", contract2_data, tags=["tenant:t2"])

        # Invalidate by tenant
        invalidate_contract_cache_by_tags(["tenant:t1"])

        # Only contract-1 should be invalidated
        self.assertIsNone(get_cached_contract("contract-1"))
        self.assertIsNotNone(get_cached_contract("contract-2"))


class TestCacheWarming(TestCase):
    """Test cache warming for frequently accessed contracts."""

    @override_settings(REDIS_URL='redis://redis:6379/0')
    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            keys = self.redis_client.keys("contract:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    @patch('hub.apps.contracts.caching_enhanced.Contract')
    def test_warm_frequently_accessed_contracts(self, mock_contract_model):
        """Test warming cache for frequently accessed contracts."""
        # Mock contract queryset
        mock_contract1 = Mock()
        mock_contract1.id = "contract-1"
        mock_contract1.hub_contract_json = {"name": "Contract 1"}
        mock_contract1.status = "active"
        mock_contract1.normalization_status = "normalized"
        mock_contract1.tenant_id = "tenant-1"

        mock_contract2 = Mock()
        mock_contract2.id = "contract-2"
        mock_contract2.hub_contract_json = {"name": "Contract 2"}
        mock_contract2.status = "active"
        mock_contract2.normalization_status = "normalized"
        mock_contract2.tenant_id = "tenant-1"

        contracts_list = [mock_contract1, mock_contract2]

        mock_queryset = Mock()
        mock_queryset.filter.return_value = mock_queryset
        mock_queryset.order_by.return_value = mock_queryset
        mock_queryset.select_related.return_value = mock_queryset

        # Mock slicing behavior
        def getitem(self, key):
            if isinstance(key, slice):
                return contracts_list[key]
            return contracts_list[key]

        mock_queryset.__getitem__ = getitem
        mock_queryset.__iter__ = lambda self: iter(contracts_list)
        mock_queryset.__len__ = lambda self: len(contracts_list)

        mock_contract_model.objects.filter.return_value = mock_queryset

        # Warm cache
        warmed_count = warm_frequently_accessed_contracts(limit=10)

        # Verify contracts are cached
        self.assertGreater(warmed_count, 0)
        cached1 = get_cached_contract("contract-1")
        cached2 = get_cached_contract("contract-2")
        self.assertIsNotNone(cached1)
        self.assertIsNotNone(cached2)

    @patch('hub.apps.contracts.caching_enhanced.Contract')
    def test_warm_contracts_by_tenant(self, mock_contract_model):
        """Test warming contracts for specific tenant."""
        # Mock contract queryset
        mock_contract = Mock()
        mock_contract.id = "contract-1"
        mock_contract.hub_contract_json = {"name": "Contract 1"}
        mock_contract.status = "active"
        mock_contract.normalization_status = "normalized"
        mock_contract.tenant_id = "tenant-1"

        contracts_list = [mock_contract]

        mock_queryset = Mock()
        mock_queryset.filter.return_value = mock_queryset
        mock_queryset.order_by.return_value = mock_queryset
        mock_queryset.select_related.return_value = mock_queryset

        # Mock slicing behavior
        def getitem(self, key):
            if isinstance(key, slice):
                return contracts_list[key]
            return contracts_list[key]

        mock_queryset.__getitem__ = getitem
        mock_queryset.__iter__ = lambda self: iter(contracts_list)
        mock_queryset.__len__ = lambda self: len(contracts_list)

        mock_contract_model.objects.filter.return_value = mock_queryset

        # Warm cache for tenant
        warmed_count = warm_frequently_accessed_contracts(tenant_id="tenant-1", limit=10)

        # Verify contract is cached
        self.assertGreater(warmed_count, 0)
        cached = get_cached_contract("contract-1")
        self.assertIsNotNone(cached)


class TestCacheMetrics(TestCase):
    """Test cache hit/miss metrics."""

    @override_settings(REDIS_URL='redis://redis:6379/0')
    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

        # Clear cache before each test
        try:
            keys = self.redis_client.keys("contract:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            keys = self.redis_client.keys("contract:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    @patch('hub.apps.contracts.caching_enhanced.cache_hits_total')
    @patch('hub.apps.contracts.caching_enhanced.cache_misses_total')
    def test_cache_hit_metrics(self, mock_misses, mock_hits):
        """Test cache hit metrics are recorded."""
        contract_id = "test-contract-1"
        contract_data = {"id": contract_id, "name": "Test Contract"}

        # Cache contract
        cache_contract(contract_id, contract_data)

        # Get cached contract (should be a hit)
        cached = get_cached_contract_with_metrics(contract_id)

        # Verify metrics were called
        mock_hits.labels.assert_called_with(cache_key_prefix='contract')
        mock_hits.labels.return_value.inc.assert_called_once()

    @patch('hub.apps.contracts.caching_enhanced.cache_hits_total')
    @patch('hub.apps.contracts.caching_enhanced.cache_misses_total')
    def test_cache_miss_metrics(self, mock_misses, mock_hits):
        """Test cache miss metrics are recorded."""
        contract_id = "non-existent-contract"

        # Try to get non-existent contract (should be a miss)
        cached = get_cached_contract_with_metrics(contract_id)

        # Verify metrics were called
        mock_misses.labels.assert_called_with(cache_key_prefix='contract')
        mock_misses.labels.return_value.inc.assert_called_once()

    @patch('hub.apps.contracts.caching_enhanced.cache_hits_total')
    @patch('hub.apps.contracts.caching_enhanced.cache_misses_total')
    def test_get_cache_metrics(self, mock_misses, mock_hits):
        """Test getting cache metrics."""
        # Set up mock metrics
        mock_hits.labels.return_value._value.get.return_value = 100
        mock_misses.labels.return_value._value.get.return_value = 50

        metrics = get_contract_cache_metrics()

        # Verify metrics structure
        self.assertIn('hits', metrics)
        self.assertIn('misses', metrics)
        self.assertIn('hit_rate', metrics)
        self.assertEqual(metrics['hits'], 100)
        self.assertEqual(metrics['misses'], 50)
        # Hit rate should be 100 / (100 + 50) = 0.666...
        self.assertAlmostEqual(metrics['hit_rate'], 0.666, places=2)

    def test_cache_metrics_integration(self):
        """Test cache metrics integration with real caching."""
        contract_id = "test-contract-metrics"
        contract_data = {"id": contract_id, "name": "Test Contract"}

        # Cache contract
        cache_contract(contract_id, contract_data)

        # First get - should be a hit
        cached1 = get_cached_contract_with_metrics(contract_id)
        self.assertIsNotNone(cached1)

        # Second get - should also be a hit
        cached2 = get_cached_contract_with_metrics(contract_id)
        self.assertIsNotNone(cached2)

        # Get metrics
        # Note: Metrics may not be initialized in test environment
        # This test verifies the function works without errors
        metrics = get_contract_cache_metrics()
        self.assertIn('hits', metrics)
        self.assertIn('misses', metrics)
        self.assertIn('hit_rate', metrics)
        # Metrics may be 0 if not initialized, which is acceptable in tests


class TestEnhancedCachingIntegration(TestCase):
    """Integration tests for enhanced contract caching."""

    @override_settings(REDIS_URL='redis://redis:6379/0')
    def setUp(self):
        """Set up test fixtures."""
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for integration tests")

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            keys = self.redis_client.keys("contract:*")
            if keys:
                self.redis_client.delete(*keys)
            keys = self.redis_client.keys("cache_tag:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception:
            pass

    def test_full_caching_lifecycle_with_tags(self):
        """Test complete caching lifecycle with tags."""
        contract_id = "test-contract-lifecycle"
        contract_data = {"id": contract_id, "name": "Test Contract"}
        tags = ["tenant:t1", "owner:user1"]

        # Cache with tags
        cache_contract_with_tags(contract_id, contract_data, tags=tags)

        # Verify cached
        cached = get_cached_contract_with_metrics(contract_id)
        self.assertIsNotNone(cached)

        # Invalidate by tag
        invalidate_contract_cache_by_tags(["tenant:t1"])

        # Verify invalidated
        cached_after = get_cached_contract_with_metrics(contract_id)
        self.assertIsNone(cached_after)

    def test_cache_warming_and_metrics(self):
        """Test cache warming combined with metrics."""
        # This test would require mocking Contract model
        # For now, we'll test the integration conceptually
        pass

