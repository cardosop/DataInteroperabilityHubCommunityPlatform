"""
Phase 227 Wave 1 (227.L8.5) — post-save cache-invalidation cascade.

The 7-step cascade fired by ``ContractService.update_contract`` after
re-normalising a contract:

1. Save ``hub_contract_json`` (caller's responsibility — the
   ``contract.save()`` call must already be on disk before this
   helper is invoked).
2. ``invalidate_contract_cache(contract_id)`` — flush the per-contract
   detail-page cache.
3. ``invalidate_lineage_cache(contract_id)`` — flush this contract's
   own lineage view.
4. **Cascade**: invalidate the lineage cache of every contract that
   references this one (``referenced_by`` set from
   ``LineageTraverser.traverse_bottom_up``). Without this step a
   downstream consumer's view shows a stale snapshot of THIS
   contract's structure until its own TTL expires.
5. Trigger search-index re-ingest.
6. Trigger semantic / AI re-ingest **if** those features are active
   for the tenant.
7. Emit a ``contract.normalized`` event, **rate-limited** to once per
   minute per contract so a burst of edits doesn't flood the bus.

The order matters — see the docstring on
:func:`run_post_save_cascade` for why save-then-invalidate is the
right sequence (vs. invalidate-then-save).

Failures in steps 2-7 SHALL NOT roll back step 1. Each step is wrapped
in fail-soft logging so a flaky search index or unavailable Redis
doesn't block the user's PATCH from completing successfully. Errors
surface in structlog at WARN so SRE can spot drift.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import structlog
from django.core.cache import cache

logger = structlog.get_logger(__name__)


# Phase 227 Wave 1 (227.L8.5) — rate limit for ``contract.normalized``
# events. One emission per contract per minute. Enforced via a
# Django-cache record keyed on contract id with a 60-second TTL.
_NORMALIZED_EVENT_RATE_LIMIT_KEY = "contracts:normalized_event_rate:{contract_id}"
_NORMALIZED_EVENT_RATE_LIMIT_SECONDS = 60


def _safe_invoke(label: str, contract_id: str, fn) -> None:
    """Call ``fn``; on exception, log and continue. The cascade
    SHALL NOT raise — callers have already committed step 1, and
    re-raising here would leave the system in a half-invalidated
    state with the user holding a 500 response for a successful save.
    """
    try:
        fn()
    except Exception as exc:  # pragma: no cover — best-effort cascade
        logger.warning(
            "contract_post_save_cascade_step_failed",
            step=label,
            contract_id=contract_id,
            error=str(exc),
            error_type=type(exc).__name__,
        )


def _invalidate_dependents_lineage_caches(contract) -> List[str]:
    """Step 4 — cascade: invalidate the lineage cache of every contract
    that references this one. Returns the list of contract IDs whose
    cache was flushed (used for telemetry; empty when this contract
    has no dependents)."""
    dependents: List[str] = []
    try:
        from hub.apps.contracts.lineage import LineageTraverser
    except ImportError:
        return dependents
    try:
        traverser = LineageTraverser(contract)
    except Exception as exc:
        logger.warning(
            "contract_post_save_cascade_traverser_init_failed",
            contract_id=str(contract.id),
            error=str(exc),
        )
        return dependents
    try:
        upstream = traverser.traverse_bottom_up()
    except Exception as exc:
        logger.warning(
            "contract_post_save_cascade_traverse_failed",
            contract_id=str(contract.id),
            error=str(exc),
        )
        return dependents
    if not isinstance(upstream, dict):
        return dependents
    referenced_by = upstream.get("referenced_by") or []
    if not isinstance(referenced_by, list):
        return dependents
    from hub.apps.contracts.caching import invalidate_lineage_cache

    for entry in referenced_by:
        # ``referenced_by`` entries are dicts with at least ``contract_id``.
        ref_id = None
        if isinstance(entry, dict):
            ref_id = entry.get("contract_id") or entry.get("id")
        elif isinstance(entry, str):
            ref_id = entry
        if not ref_id:
            continue
        try:
            invalidate_lineage_cache(str(ref_id))
            dependents.append(str(ref_id))
        except Exception as exc:
            logger.warning(
                "contract_post_save_cascade_dependent_invalidate_failed",
                contract_id=str(contract.id),
                dependent_id=str(ref_id),
                error=str(exc),
            )
    return dependents


def _trigger_search_reindex(contract) -> None:
    """Step 5 — request a search-index refresh. Existing post-save
    signal-driven reindex picks up the row automatically, but for
    callers that bypass signals (rare — bulk operations) we kick it
    here too. Best-effort: the search subsystem owns the queue."""
    try:
        from hub.apps.search.indexing import enqueue_contract_reindex  # type: ignore[import-not-found]  # search app is optional at import-time
    except ImportError:
        # Search module may not be installed in this deployment
        # (some test environments). Skip silently.
        return
    enqueue_contract_reindex(contract_id=str(contract.id))


def _trigger_semantic_reingest(contract, tenant_id: Optional[str]) -> None:
    """Step 6 — if semantic / AI features are enabled for the tenant,
    enqueue a re-ingest of this contract into the embeddings index.
    Otherwise skip. The tenant feature-toggle lives on
    ``Tenant.semantic_capabilities_enabled`` (Phase 230 flag); we
    fail-soft if the attribute or the queue helper is absent."""
    if not tenant_id:
        return
    try:
        from hub.apps.tenants.models import Tenant
        tenant = Tenant.objects.only("id").get(id=tenant_id)
    except Exception:
        return
    enabled = bool(getattr(tenant, "semantic_capabilities_enabled", False))
    if not enabled:
        return
    try:
        from hub.apps.semantic.tasks import enqueue_contract_reingest  # type: ignore[import-not-found]  # semantic app is optional at import-time
    except ImportError:
        return
    enqueue_contract_reingest(contract_id=str(contract.id), tenant_id=tenant_id)


def _emit_contract_normalized_event(
    contract,
    tenant_id: Optional[str],
    user_id: Optional[str],
) -> None:
    """Step 7 — emit ``contract.normalized`` rate-limited to 1/min/contract.

    The rate-limit lives in the shared Django cache so a horizontally-
    scaled API replica honours the bound. ``cache.add(key, value, ttl)``
    sets-if-absent and returns False when a recent emission is still in
    its window; we skip the publish in that case.
    """
    contract_id = str(contract.id)
    key = _NORMALIZED_EVENT_RATE_LIMIT_KEY.format(contract_id=contract_id)
    # ``cache.add`` is atomic (Memcached + Redis backends). If it
    # returns False, another emission is in flight within the window.
    try:
        accepted = cache.add(
            key, time.time(), timeout=_NORMALIZED_EVENT_RATE_LIMIT_SECONDS,
        )
    except Exception:
        # Cache backend down — fail open (still publish; event bus has
        # its own dedup key).
        accepted = True
    if not accepted:
        logger.debug(
            "contract_normalized_event_rate_limited",
            contract_id=contract_id,
            window_seconds=_NORMALIZED_EVENT_RATE_LIMIT_SECONDS,
        )
        return
    try:
        from hub.apps.core.events.service_publishers import (
            ContractEventPublisher,
        )
        publisher = ContractEventPublisher()
        publisher.publish_contract_normalized(
            contract_id=contract_id,
            tenant_id=tenant_id,
            user_id=user_id,
            normalization_status=getattr(contract, "normalization_status", None),
            spec_type=getattr(contract, "original_spec_type", None),
            spec_version=getattr(contract, "original_spec_version", None),
        )
    except (ImportError, AttributeError):
        # ``publish_contract_normalized`` may not exist in older
        # publisher versions. Fail-soft.
        return
    except Exception as exc:  # pragma: no cover — best-effort
        logger.warning(
            "contract_normalized_event_publish_failed",
            contract_id=contract_id,
            error=str(exc),
        )


def run_post_save_cascade(
    contract,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the 7-step cascade for ``contract`` after a successful save.

    The caller MUST have already committed the row (step 1). This
    helper covers steps 2-7. Returns a dict with telemetry counts so
    the caller can log a single structured event summarising the
    cascade's outcome.

    Failures are logged but never raised — see module docstring.
    """
    contract_id = str(contract.id)
    summary: Dict[str, Any] = {"contract_id": contract_id}

    # Step 2 — flush the per-contract detail cache.
    from hub.apps.contracts.caching import (
        invalidate_contract_cache,
        invalidate_lineage_cache,
    )
    _safe_invoke(
        "invalidate_contract_cache",
        contract_id,
        lambda: invalidate_contract_cache(contract_id),
    )
    # Step 3 — flush this contract's own lineage cache.
    _safe_invoke(
        "invalidate_lineage_cache",
        contract_id,
        lambda: invalidate_lineage_cache(contract_id),
    )
    # Step 4 — cascade to dependents.
    dependents = _invalidate_dependents_lineage_caches(contract)
    summary["dependents_invalidated"] = len(dependents)

    # Step 5 — search re-index.
    _safe_invoke(
        "search_reindex",
        contract_id,
        lambda: _trigger_search_reindex(contract),
    )
    # Step 6 — semantic / AI re-ingest (gated on tenant flag).
    _safe_invoke(
        "semantic_reingest",
        contract_id,
        lambda: _trigger_semantic_reingest(contract, tenant_id),
    )
    # Step 7 — emit the rate-limited normalized event.
    _safe_invoke(
        "contract_normalized_event",
        contract_id,
        lambda: _emit_contract_normalized_event(contract, tenant_id, user_id),
    )

    logger.info(
        "contract_post_save_cascade_complete",
        contract_id=contract_id,
        dependents_invalidated=summary["dependents_invalidated"],
    )
    return summary
