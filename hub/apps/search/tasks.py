"""
Search vector update tasks (Phase 18.2).

Lightweight RQ tasks that rebuild the PostgreSQL tsvector on an Asset or
Contract after a post_save signal fires.  Using an async RQ task keeps the
hot save path free of the SearchVector computation and multi-column JOIN.

Queue: job_low — these are background maintenance jobs that are never
latency-sensitive.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import django_rq

from hub.apps.search.indexing import SearchIndexer

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

_QUEUE = "job_low"


def _run_with_tenant_context[T](
    tenant_id: str | None,
    func: Callable[[], T],
) -> T:
    """Run *func* inside ``tenant_context(tenant_id)`` when *tenant_id*
    is provided, or directly when it is ``None``.

    Worker/signal code that touches tenant-scoped models MUST use this
    helper so that RLS policies (which reference
    ``current_setting('app.current_tenant_id')``) can resolve rows.
    """
    if tenant_id is None:
        return func()
    from hub.apps.tenants.request_tenant import tenant_context

    with tenant_context(tenant_id):
        return func()


def enqueue_asset_search_vector_update(asset_id: str) -> None:
    """Enqueue update_asset_search_vector on the low-priority queue."""
    django_rq.get_queue(_QUEUE).enqueue(
        update_asset_search_vector,
        asset_id,
        job_timeout=120,
    )


def enqueue_dataset_search_vector_update(dataset_id: str) -> None:
    """Enqueue update_dataset_search_vector on the low-priority queue.

    Dataset does not have a search_vector column yet; this is a
    forward-compatible stub so the datasets.signals.rebuild_dataset_search_vector
    signal handler resolves without ImportError.  Once the search_vector field
    is added to Dataset, replace the body with a real enqueue call.
    """
    logger.debug(
        "dataset_search_vector_update_skipped dataset_id=%s reason=no_search_vector_field",
        dataset_id,
    )


def enqueue_contract_search_vector_update(contract_id: str) -> None:
    """Enqueue update_contract_search_vector on the low-priority queue."""
    django_rq.get_queue(_QUEUE).enqueue(
        update_contract_search_vector,
        contract_id,
        job_timeout=120,
    )


def reindex_contract(contract_id: str) -> None:
    """Rebuild the FULL SearchIndex row for Contract <contract_id>.

    W4.2 (R2-B5): the tsvector-only ``update_contract_search_vector``
    refreshes a column the unified search UI does NOT read — the UI reads
    the SearchIndex row (Phase 226 G12), so a renamed/re-shaped contract
    stayed searchable under its stale title until a manual bulk reindex.
    This task refreshes title/description/schema/lineage/search_vector
    and invalidates the unified-search result cache.
    """
    from hub.apps.contracts.models import Contract

    contract = Contract.objects.filter(pk=contract_id).first()
    if contract is None:
        logger.warning("contract_reindex_missing_row contract_id=%s", contract_id)
        return
    _run_with_tenant_context(
        str(contract.tenant_id),
        lambda: SearchIndexer.index_contract(contract),
    )
    _invalidate_search_cache()
    logger.debug("contract_reindexed contract_id=%s", contract_id)


def enqueue_contract_reindex(contract_id: str) -> None:
    """Enqueue reindex_contract on the low-priority queue (W4.2 R2-B5).

    Test note: RQ_QUEUES ASYNC=False under pytest, so enqueued jobs run
    inline — the contract PATCH → search-updated contract is pinned
    synchronously (``hub/apps/search/tests/test_w42_search_reindex.py``).
    """
    django_rq.get_queue(_QUEUE).enqueue(
        reindex_contract,
        contract_id,
        job_timeout=120,
    )


def _invalidate_search_cache() -> None:
    """Invalidate the unified-search result cache after an index write.

    Backend-agnostic: prefix delete on django_redis, registered-key
    delete elsewhere (see
    :mod:`hub.apps.search.cache_invalidation`). A full
    ``cache.clear()`` fallback was removed — it wiped unrelated cache
    state (DRF throttle budgets, rate-limit counters) on every save
    when the search-vector job runs in-process (test-env sync RQ).
    """
    from hub.apps.search.cache_invalidation import invalidate_search_cache

    invalidate_search_cache()


def update_asset_search_vector(asset_id: str) -> None:
    """
    Recompute the search_vector for Asset <asset_id>.

    Weighted vector:
      A — name (highest relevance)
      B — description
      C — domain

    Phase 275.E.3k — LIVE_QUERY assets additionally refresh their
    ``SearchIndex`` row (the search UI reads that row, not the tsvector
    column).  Previously only the bulk reindex command wrote it, so a
    tenant-saved LIVE_QUERY asset stayed invisible in search until a
    manual reindex.
    """
    from django.contrib.postgres.search import SearchVector
    from django.db import transaction

    from hub.apps.assets.models import Asset

    try:
        asset = Asset.objects.filter(pk=asset_id).select_related("tenant").first()
        with transaction.atomic():
            Asset.objects.filter(pk=asset_id).update(
                search_vector=(
                    SearchVector("name", weight="A")
                    + SearchVector("description", weight="B")
                    + SearchVector("domain", weight="C")
                )
            )
        # Phase 226 G12 — EVERY asset (not just LIVE_QUERY) must write
        # its SearchIndex row on the rebuild path. The search UI reads
        # the SearchIndex row, not the tsvector column; the previous
        # LIVE_QUERY-only gating left normal (data-first/metadata)
        # assets invisible in unified search until a manual bulk
        # reindex — silently breaking the "queryable within 20s of
        # create" platform promise.
        if asset is not None:
            _run_with_tenant_context(
                str(asset.tenant_id),
                lambda: SearchIndexer.index_asset(asset),
            )
            _invalidate_search_cache()
        logger.debug("asset_search_vector_updated asset_id=%s", asset_id)
    except Exception:
        logger.exception("asset_search_vector_failed asset_id=%s", asset_id)
        raise


def update_contract_search_vector(contract_id: str) -> None:
    """
    Recompute the search_vector for Contract <contract_id>.

    Weighted vector:
      A — original_spec_type
      B — hub_contract_version
    """
    from django.contrib.postgres.search import SearchVector
    from django.db import transaction

    from hub.apps.contracts.models import Contract

    try:
        with transaction.atomic():
            Contract.objects.filter(pk=contract_id).update(
                search_vector=(
                    SearchVector("original_spec_type", weight="A")
                    + SearchVector("hub_contract_version", weight="B")
                )
            )
        logger.debug("contract_search_vector_updated contract_id=%s", contract_id)
    except Exception:
        logger.exception("contract_search_vector_failed contract_id=%s", contract_id)
        raise
