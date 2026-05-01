"""
Asset post_save signal — enqueues a search vector rebuild (Phase 18.2).

After any Asset save the search_vector field is refreshed asynchronously
via an RQ job on job_low so the hot save path is not blocked.
Failures are logged at WARNING level and never propagate to callers.
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 230.3.5 (REQ-SEM-TOMBSTONE-001) — Asset retire → semantic tombstone
# ---------------------------------------------------------------------------
#
# The dispatch path is:
#
#   pre_save: capture instance.status BEFORE the save (so post_save can
#             diff against the new value).
#   post_save: when the saved value is RETIRED AND the prior value was
#              NOT RETIRED, fire the canonical tombstone path.
#
# We use a private attribute on the instance (``_pre_save_status``) to
# carry the prior value across the two signal handlers.  Same pattern
# as the contracts.signals lineage-hash flow.

_PRIOR_ASSET_STATUS_ATTR = "_pre_save_status_for_tombstone"


def _capture_prior_asset_status(sender, instance, **kwargs):
    """pre_save listener — record the prior status so the post_save
    handler can detect ACTIVE→RETIRED transitions exactly once.

    For brand-new Assets (no PK yet) the prior is recorded as
    ``None`` so the first save WITH ``status=RETIRED`` is treated
    as a transition (a tenant could legitimately create an
    already-retired Asset; we still tombstone its SR if one exists).
    """
    if not instance.pk:
        setattr(instance, _PRIOR_ASSET_STATUS_ATTR, None)
        return
    try:
        prior = sender.objects.only("status").get(pk=instance.pk)
    except sender.DoesNotExist:
        setattr(instance, _PRIOR_ASSET_STATUS_ATTR, None)
        return
    setattr(instance, _PRIOR_ASSET_STATUS_ATTR, prior.status)


def _fire_asset_tombstone_if_retired(sender, instance, **kwargs):
    """post_save listener — fires ``tombstone_resource`` when status
    flipped to RETIRED.

    Skipped when:
      * status didn't change (renames, metadata edits).
      * the prior status was already RETIRED (idempotent re-saves).
    """
    from hub.apps.assets.models import AssetStatus

    new_status = getattr(instance, "status", None)
    if new_status != AssetStatus.RETIRED:
        return
    prior = getattr(instance, _PRIOR_ASSET_STATUS_ATTR, None)
    if prior == AssetStatus.RETIRED:
        return

    def _dispatch():
        try:
            from hub.apps.semantic.tombstone import (
                REASON_ASSET_RETIRED, tombstone_resource,
            )
            tombstone_resource(
                resource_type="ASSET",
                resource_id=instance.pk,
                reason=REASON_ASSET_RETIRED,
            )
        except Exception as exc:  # pragma: no cover — best-effort
            logger.warning(
                "asset_tombstone_dispatch_failed asset_id=%s error=%s",
                instance.pk, exc,
            )

    transaction.on_commit(_dispatch)


# Wire both signals at module import time.  The contracts AppConfig
# pattern is to import the signals module from ``ready()``; we mirror
# that here.
def _connect_asset_tombstone_signals():
    pre_save.connect(
        _capture_prior_asset_status,
        sender="assets.Asset",
        dispatch_uid="phase_230_3_capture_prior_asset_status",
    )
    post_save.connect(
        _fire_asset_tombstone_if_retired,
        sender="assets.Asset",
        dispatch_uid="phase_230_3_fire_asset_tombstone",
    )


_connect_asset_tombstone_signals()


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
