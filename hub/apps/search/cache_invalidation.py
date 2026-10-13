"""
Search result cache registration + invalidation (Phase 226 G12).

The unified-search endpoint caches results for 300s keyed by
``search_{md5}``; without invalidation, a poll that observed the
pre-index state poisons every subsequent poll.

Backend strategy:

* Backends with ``delete_pattern`` (django_redis): prefix delete
  ``search_*`` — covers result keys and suggestion keys.
* Backends without key enumeration (LocMem in tests/dev): delete the
  keys registered by :func:`register_search_cache_key`. A full
  ``cache.clear()`` is FORBIDDEN here — the search-vector update runs
  in-process under test-env RQ (sync jobs), so a full clear wipes
  unrelated cache state on every asset/contract save (DRF throttle
  budgets, login rate-limit counters, tenant subscription checks) and
  silently disables rate limiting.
"""

import logging

logger = logging.getLogger(__name__)

# Deliberately does NOT start with "search_" — on django_redis the
# ``delete_pattern("search_*")`` invalidation would wipe the registry
# itself on every index write.
_SEARCH_KEY_REGISTRY = "registered_search_cache_keys"


def register_search_cache_key(cache_key: str) -> None:
    """Best-effort registration of an emitted search-result cache key.

    Only needed on backends without ``delete_pattern``; skipped
    elsewhere (the registry would be dead weight). Never raises — cache
    bookkeeping must not block the search response.
    """
    try:
        from django.core.cache import cache

        if hasattr(cache, "delete_pattern"):
            return
        keys = cache.get(_SEARCH_KEY_REGISTRY)
        current = set(keys) if keys else set()
        if cache_key not in current:
            current.add(cache_key)
            # Outlives the search-cache TTL (300s) so a registered key
            # is never silently dropped before its entry expires.
            cache.set(_SEARCH_KEY_REGISTRY, current, timeout=600)
    except Exception:
        logger.warning("search_cache_key_registration_failed", exc_info=True)


def invalidate_search_cache() -> None:
    """Invalidate the unified-search result cache after an index write.

    Never raises — cache invalidation must never break indexing or the
    save that triggered it.
    """
    try:
        from django.core.cache import cache

        if hasattr(cache, "delete_pattern"):
            cache.delete_pattern("search_*")
            return

        keys = cache.get(_SEARCH_KEY_REGISTRY)
        if keys:
            cache.delete_many(list(keys))
        cache.delete(_SEARCH_KEY_REGISTRY)
    except Exception:
        logger.warning("search_cache_invalidation_failed", exc_info=True)
