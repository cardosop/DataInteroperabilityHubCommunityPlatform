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


# ---------------------------------------------------------------------------
# Phase 228.F3.2 (REQ-LIN-F3-001) — contract.updated event publication
# ---------------------------------------------------------------------------


def _hash_lineage(hub_contract_json) -> str:
    """SHA-256 of the canonical-JSON lineage subtree.

    Pure function, no I/O — the dispatcher hashes both the pre-save
    snapshot and the new state to decide whether to fire.  ``None``
    or missing lineage hashes the same as ``{}`` so we don't fire
    on save-with-empty-lineage churn.
    """
    if not isinstance(hub_contract_json, dict):
        return hashlib.sha256(b"{}").hexdigest()
    lineage = hub_contract_json.get("lineage") or {}
    canonical = json.dumps(lineage, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# pre_save snapshot side-channel: stash the prior lineage hash on the
# instance so post_save can diff against it without an extra DB read.
# We use a private attribute name to avoid clashes with user code.
_PRIOR_LINEAGE_HASH_ATTR = "_f3_prior_lineage_hash"


def _capture_prior_lineage_hash(sender, instance, **kwargs):
    """``pre_save`` listener — fetch the unsaved row's prior lineage
    hash so the post_save handler can decide whether the lineage
    subtree actually changed.

    For new contracts (no PK yet) we record the empty-lineage hash;
    the post_save handler then compares against the new state and
    fires only when the new state has non-empty lineage.
    """
    from hub.apps.contracts.models import Contract

    if not instance.pk:
        # Newly-created Contract — prior is the empty-lineage hash so
        # any non-empty lineage on the first save is a change.
        setattr(instance, _PRIOR_LINEAGE_HASH_ATTR, _hash_lineage({}))
        return

    try:
        prior = Contract.objects.only("hub_contract_json").get(pk=instance.pk)
    except Contract.DoesNotExist:
        setattr(instance, _PRIOR_LINEAGE_HASH_ATTR, _hash_lineage({}))
        return
    setattr(
        instance, _PRIOR_LINEAGE_HASH_ATTR,
        _hash_lineage(prior.hub_contract_json),
    )


@receiver(post_save, sender="contracts.Contract")
def publish_contract_updated_for_lineage(sender, instance, created, **kwargs):
    """REQ-LIN-F3-001 — emit a ``contract.updated`` event when the
    lineage subtree of ``hub_contract_json`` changes.

    Behaviour:

    * Compute ``new_hash = SHA-256(canonical(hub_contract_json.lineage))``.
    * Read ``old_hash`` from the pre_save side-channel attribute.
    * Skip if the hashes match — F3 is lineage-only; non-lineage
      saves (e.g. status flip) must NOT fire the dispatcher.
    * Otherwise enqueue ``LineageImpactDispatcher.handle_contract_updated``
      via the project's job-system (django-rq) **after commit** so a
      rolled-back transaction never produces a phantom event.

    Errors in the dispatch path are logged and swallowed — the event
    bus is best-effort; a contract save must not be blocked by a
    notifier outage.
    """
    new_hash = _hash_lineage(instance.hub_contract_json)
    old_hash = getattr(instance, _PRIOR_LINEAGE_HASH_ATTR, None)
    if old_hash is None:
        # pre_save didn't run for some reason — fall back to "always
        # emit on create".  This is conservative: the dispatcher's
        # debounce key prevents notification storms.
        old_hash = _hash_lineage({})

    if old_hash == new_hash:
        return  # No lineage change.

    contract_id = instance.pk
    tenant_id = getattr(instance, "tenant_id", None)
    version = getattr(instance, "version", None)
    # actor_user_id is a best-effort lookup — Django signals don't
    # carry the request user; ops set it via a thread-local in the
    # view layer before saving (see lineage_edit_service).
    actor_user_id = getattr(instance, "_f3_actor_user_id", None)

    def _enqueue():
        try:
            from hub.apps.contracts.lineage_impact_dispatcher import (
                handle_contract_updated,
            )
            handle_contract_updated(
                contract_id=str(contract_id),
                tenant_id=str(tenant_id) if tenant_id else "",
                old_lineage_hash=old_hash,
                new_lineage_hash=new_hash,
                version=version,
                actor_user_id=str(actor_user_id) if actor_user_id else "",
            )
        except Exception as exc:
            logger.warning(
                "lineage_impact_dispatch_enqueue_failed "
                "contract_id=%s error=%s",
                contract_id, exc,
            )

    transaction.on_commit(_enqueue)


# Wire the pre_save listener.  Imported lazily inside ready() to keep
# Django's migration/apps loading order clean.
def _connect_lineage_pre_save():
    from django.db.models.signals import pre_save
    pre_save.connect(
        _capture_prior_lineage_hash,
        sender="contracts.Contract",
        dispatch_uid="f3_capture_prior_lineage_hash",
    )


_connect_lineage_pre_save()


# ---------------------------------------------------------------------------
# Phase 230.3.6 (REQ-SEM-TOMBSTONE-001) — Contract delete → semantic tombstone
# ---------------------------------------------------------------------------
#
# Contract has hard CASCADE semantics — there's no soft-delete shim,
# so we hook ``post_delete`` directly.  Dispatches the canonical
# ``tombstone_resource`` path: mark TOMBSTONED + purge Fuseki +
# emit audit.

from django.db.models.signals import post_delete  # noqa: E402


@receiver(post_delete, sender="contracts.Contract")
def fire_contract_tombstone_on_delete(sender, instance, **kwargs):
    """Fire the canonical tombstone path on Contract deletion.

    Runs inside ``transaction.on_commit`` so a rolled-back delete
    does NOT produce a phantom tombstone — the spec mandates the DB
    transition is the canonical signal; we honour it.
    """
    contract_id = instance.pk

    def _dispatch():
        try:
            from hub.apps.semantic.tombstone import (
                REASON_CONTRACT_DELETED, tombstone_resource,
            )
            tombstone_resource(
                resource_type="CONTRACT",
                resource_id=contract_id,
                reason=REASON_CONTRACT_DELETED,
            )
        except Exception as exc:
            logger.warning(
                "contract_tombstone_dispatch_failed "
                "contract_id=%s error=%s",
                contract_id, exc,
            )

    transaction.on_commit(_dispatch)
