"""
Phase 275.E.3k — Warehouse connectivity signal handlers.

Wires search indexing + audit events for LIVE_QUERY asset lifecycle.
"""
from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="assets.Asset")
def index_live_query_asset_on_save(sender, instance, **kwargs):
    """Phase 275.E.3k — trigger search reindex when a LIVE_QUERY asset is saved."""
    from hub.apps.assets.models import DataStrategy

    if getattr(instance, "data_strategy", None) != DataStrategy.LIVE_QUERY:
        return

    try:
        from hub.apps.search.indexing import SearchIndexer
        SearchIndexer.index_asset(instance)
        logger.debug(
            "search_index_live_query_asset",
            extra={"asset_id": str(instance.id), "tenant_id": str(instance.tenant_id)},
        )
    except Exception:
        logger.exception("search_index_live_query_asset_failed")
