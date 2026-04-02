"""
Contract post_save signal — publishes a cache-invalidation message to Redis.

When a Contract record is saved (created or updated) the SHA-256 of its
``original_raw`` spec content is published to the ``datacontract:invalidate``
pub/sub channel so that every datacontract-service replica can evict the
matching Redis cache entries (15.2).

Message format:  {"spec_hash": "<sha256hex>"}

Publishing is best-effort: failures are logged at WARNING level and never
propagate back to the caller so that a Redis outage cannot break contract
saves.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

_INVALIDATION_CHANNEL = "datacontract:invalidate"

# Module-level singleton for the direct redis-py fallback.
# Reusing one pool avoids spawning a new ConnectionPool on every contract save.
_fallback_redis_client = None


def _get_redis_client():
    """
    Return a synchronous Redis client.

    Priority:
    1. django-redis connection pool (already managed by Django, zero overhead).
    2. A module-level singleton redis-py pool constructed once from env vars.

    Returns None when Redis is not configured.
    """
    global _fallback_redis_client

    # Preferred path: reuse the Django cache's connection pool (django-redis).
    # Use getattr to avoid type-checker errors on BaseCache; the AttributeError
    # is caught by the broad except so this is safe at runtime.
    try:
        from django.core.cache import cache as django_cache
        pool_client = getattr(django_cache, "client", None)
        if pool_client is not None:
            return pool_client.get_client()
    except Exception:
        pass

    # Fallback: one-time creation of a dedicated pool
    if _fallback_redis_client is None:
        try:
            import redis as sync_redis
            url = os.getenv("REDIS_CACHE_URL") or os.getenv("REDIS_URL", "")
            if not url:
                return None
            _fallback_redis_client = sync_redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=False,
            )
        except Exception:
            return None

    return _fallback_redis_client


@receiver(post_save, sender="contracts.Contract")
def invalidate_datacontract_cache(sender, instance, **kwargs):
    """
    Publish the spec hash of the saved contract to the invalidation channel.

    Safe to call in any context: logs warnings on failure, never raises.
    """
    raw: str = getattr(instance, "original_raw", None) or ""
    if not raw:
        return

    spec_hash = hashlib.sha256(raw.encode()).hexdigest()

    def _publish():
        payload = json.dumps({"spec_hash": spec_hash})
        try:
            client = _get_redis_client()
            if client is None:
                logger.debug(
                    "datacontract_cache_invalidation_skipped: no Redis client available"
                )
                return
            client.publish(_INVALIDATION_CHANNEL, payload)
            logger.debug(
                "datacontract_cache_invalidation_published spec_hash=%s contract_id=%s",
                spec_hash,
                instance.pk,
            )
        except Exception as exc:
            logger.warning(
                "datacontract_cache_invalidation_failed contract_id=%s error=%s",
                instance.pk,
                exc,
            )

    transaction.on_commit(_publish)


# ---------------------------------------------------------------------------
# Search vector rebuild (Phase 18.2)
# ---------------------------------------------------------------------------

@receiver(post_save, sender="contracts.Contract")
def rebuild_contract_search_vector(sender, instance, **kwargs):
    """
    Enqueue a search vector rebuild for the saved Contract after commit.

    Deferred enqueue avoids heavy SearchVector work while the writer
    transaction still holds locks (mirrors Asset signal behavior).
    """
    pk = instance.pk

    def _enqueue():
        try:
            from hub.apps.search.tasks import (
                enqueue_contract_search_vector_update,
            )

            enqueue_contract_search_vector_update(str(pk))
        except Exception as exc:
            logger.warning(
                "contract_search_vector_enqueue_failed "
                "contract_id=%s error=%s",
                pk,
                exc,
            )

    transaction.on_commit(_enqueue)
