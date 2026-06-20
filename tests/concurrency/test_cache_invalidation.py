"""Phase 103: Cache invalidation correctness.

Skipped when Redis cache is unavailable (test containers may not have
cache connectivity).
"""

import uuid

from django.test import TestCase


class CacheInvalidationTest(TestCase):
    """Verify cache operations are correct."""

    def _get_cache(self):
        from django.core.cache import cache

        try:
            cache.set("_probe", 1, 5)
            cache.delete("_probe")
            return cache
        except Exception:
            self.skipTest("Redis cache not available")

    def test_cache_write_visible_to_subsequent_read(self):
        c = self._get_cache()
        key = f"cache-{uuid.uuid4().hex[:8]}"
        c.set(key, "original", 60)
        self.assertEqual(c.get(key), "original")
        c.set(key, "updated", 60)
        self.assertEqual(c.get(key), "updated")
        c.delete(key)
