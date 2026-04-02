"""
Asset post_save signal — enqueues a search vector rebuild (Phase 18.2).

After any Asset save the search_vector field is refreshed asynchronously
via an RQ job on job_low so the hot save path is not blocked.
Failures are logged at WARNING level and never propagate to callers.
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="assets.Asset")
def rebuild_asset_search_vector(sender, instance, **kwargs):
    """Enqueue a search vector rebuild for the saved Asset after commit.

    Deferring to on_commit avoids enqueue (and synchronous RQ in tests) while
    the request or TestCase outer transaction still holds DB locks — the same
    pattern as datacontract cache invalidation in contracts/signals.py.
    """
    pk = instance.pk

    def _enqueue():
        try:
            from hub.apps.search.tasks import (
                enqueue_asset_search_vector_update,
            )

            enqueue_asset_search_vector_update(str(pk))
        except Exception as exc:
            logger.warning(
                "asset_search_vector_enqueue_failed "
                "asset_id=%s error=%s",
                pk,
                exc,
            )

    transaction.on_commit(_enqueue)
