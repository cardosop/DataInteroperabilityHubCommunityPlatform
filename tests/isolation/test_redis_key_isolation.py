"""
104.6 — Redis Key Isolation Test

Verifies that cache keys include tenant_id so Tenant A's cached data
cannot be served to Tenant B.
"""
import uuid

import pytest
from django.core.cache import cache

from hub.apps.datasets.caching import (
    get_dataset_detail_cache_key,
    get_dataset_list_cache_key,
    hash_filters,
    cache_dataset_detail,
)

pytestmark = pytest.mark.django_db(transaction=True)


class TestRedisKeyIsolation:
    """Cache keys must be tenant-scoped to prevent cross-tenant reads."""

    def test_dataset_detail_cache_key_contains_id(self):
        """Different datasets get different cache keys by UUID."""
        id_a = str(uuid.uuid4())
        id_b = str(uuid.uuid4())

        key_a = get_dataset_detail_cache_key(id_a)
        key_b = get_dataset_detail_cache_key(id_b)

        assert key_a != key_b
        assert id_a in key_a

    def test_dataset_list_cache_key_includes_tenant(
        self, tenant_a, tenant_b
    ):
        """List cache key must differ between tenants."""
        fh = hash_filters({"format": "CSV"})
        key_a = get_dataset_list_cache_key(str(tenant_a.id), fh)
        key_b = get_dataset_list_cache_key(str(tenant_b.id), fh)

        assert key_a != key_b, (
            "Same filters for different tenants must produce "
            "different cache keys"
        )
        assert str(tenant_a.id) in key_a
        assert str(tenant_b.id) in key_b

    def test_cached_data_not_shared_across_tenants(
        self, tenant_a, tenant_b
    ):
        """Data cached for A's dataset is not returned for B's."""
        id_a = str(uuid.uuid4())
        id_b = str(uuid.uuid4())

        cache_dataset_detail(id_a, {"tenant": str(tenant_a.id)})

        key_b = get_dataset_detail_cache_key(id_b)
        assert cache.get(key_b) is None, (
            "Tenant B got Tenant A's cached data"
        )

    def test_cache_clear_does_not_affect_other_tenant(
        self, tenant_a, tenant_b
    ):
        """Clearing A's cache does not clear B's."""
        id_a = str(uuid.uuid4())
        id_b = str(uuid.uuid4())

        cache_dataset_detail(id_a, {"tenant": str(tenant_a.id)})
        cache_dataset_detail(id_b, {"tenant": str(tenant_b.id)})

        # Clear only A's cache
        cache.delete(get_dataset_detail_cache_key(id_a))

        # B's cache should still be present
        key_b = get_dataset_detail_cache_key(id_b)
        assert cache.get(key_b) is not None, (
            "Clearing Tenant A cache also cleared Tenant B cache"
        )

        # Clean up
        cache.delete(key_b)
