"""
Search vector update tasks (Phase 18.2).

Lightweight RQ tasks that rebuild the PostgreSQL tsvector on an Asset or
Contract after a post_save signal fires.  Using an async RQ task keeps the
hot save path free of the SearchVector computation and multi-column JOIN.

Queue: job_low — these are background maintenance jobs that are never
latency-sensitive.
"""
from __future__ import annotations

import contextlib
import logging
from typing import Any, Callable, Optional, TypeVar

import django_rq

logger = logging.getLogger(__name__)

_QUEUE = "job_low"

_T = TypeVar("_T")


def _run_with_tenant_context(
    tenant_id: Optional[str],
    func: Callable[[], _T],
) -> _T:
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


def update_asset_search_vector(asset_id: str) -> None:
    """
    Recompute the search_vector for Asset <asset_id>.

    Weighted vector:
      A — name (highest relevance)
      B — description
      C — domain
    """
    from django.contrib.postgres.search import SearchVector
    from django.db import transaction

    from hub.apps.assets.models import Asset

    try:
        with transaction.atomic():
            Asset.objects.filter(pk=asset_id).update(
                search_vector=(
                    SearchVector("name", weight="A")
                    + SearchVector("description", weight="B")
                    + SearchVector("domain", weight="C")
                )
            )
        logger.debug(
            "asset_search_vector_updated asset_id=%s", asset_id
        )
    except Exception:
        logger.exception(
            "asset_search_vector_failed asset_id=%s", asset_id
        )
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
        logger.debug(
            "contract_search_vector_updated contract_id=%s", contract_id
        )
    except Exception:
        logger.exception(
            "contract_search_vector_failed contract_id=%s", contract_id
        )
        raise
