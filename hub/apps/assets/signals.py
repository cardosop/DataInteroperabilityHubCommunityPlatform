"""
Asset post_save signal — enqueues a search vector rebuild (Phase 18.2).

After any Asset save the search_vector field is refreshed asynchronously
via an RQ job on job_low so the hot save path is not blocked.
Failures are logged at WARNING level and never propagate to callers.
"""
from __future__ import annotations

import logging

from django.db import DatabaseError, transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from redis.exceptions import RedisError

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
        except (ConnectionError, TimeoutError, OSError) as exc:
            # Transient infrastructure failure — best-effort tombstone.
            logger.warning(
                "asset_tombstone_dispatch_failed asset_id=%s error=%s",
                instance.pk, exc,
            )
        except DatabaseError as exc:
            # Database error during tombstone dispatch — still
            # best-effort, but log at ERROR.
            logger.error(
                "asset_tombstone_dispatch_db_error asset_id=%s error=%s",
                instance.pk, exc, exc_info=True,
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

    Phase 250.1.F (closes B2-5) — the rebuild is GATED on
    ``status != DRAFT``. DRAFT assets are not searchable, so building a
    vector for them wastes a ``job_low`` slot on every ``asset_create``
    workflow step (Phase 250.1.A). The first enqueue happens on the
    activation save (DRAFT → ACTIVE) inside the asset-activation saga
    at ``hub.apps.orchestration.workflows.asset_activation_saga
    .activate_asset``, sharing the same ``transaction.on_commit`` as
    the activation itself. Subsequent saves of a non-DRAFT asset
    (renames / description edits / domain edits / status transitions
    to PUBLIC or RETIRED) continue to enqueue so the vector tracks
    the searchable text.

    **Rollback to DRAFT clears the stale vector** (audit-pass GAP-A):
    ``compensate_activation`` in the asset-activation saga flips a
    previously-activated asset back to DRAFT via
    ``asset.save(update_fields=['status', 'updated_at'])``. Without an
    explicit clear the asset would be DRAFT in the DB but its
    ``search_vector`` column would still hold the activated-state
    tsvector — and ``hub/apps/search/views.py:614-632`` filters by
    ``search_vector__isnull=False``, so the rolled-back asset would
    keep appearing in search results. We use the prior-status
    captured by the pre_save handler ``_capture_prior_asset_status``
    (``_PRIOR_ASSET_STATUS_ATTR``) to detect non-DRAFT → DRAFT
    transitions and synchronously NULL the column inside the same
    transaction as the rollback save so the post-commit state is
    consistent (no window where status=DRAFT but vector populated).
    """
    from hub.apps.assets.models import Asset, AssetStatus

    new_status = getattr(instance, "status", None)
    if new_status == AssetStatus.DRAFT:
        # Suppress the rebuild while in DRAFT. Once activated the
        # next save (or any later metadata edit) will land here with
        # a non-DRAFT status and the on_commit enqueue will fire.
        prior_status = getattr(instance, _PRIOR_ASSET_STATUS_ATTR, None)
        if (
            prior_status is not None
            and prior_status != AssetStatus.DRAFT
            and instance.pk is not None
        ):
            # Rollback path: prior was ACTIVE/PUBLIC/RETIRED; the
            # row had a populated vector that's now stale. Clear it
            # synchronously (inside the same transaction as the
            # status flip) so the searchability invariant holds the
            # moment the transaction commits. The filter avoids a
            # write when the column is already NULL.
            try:
                Asset.objects.filter(
                    pk=instance.pk,
                    search_vector__isnull=False,
                ).update(search_vector=None)
            except DatabaseError as exc:  # DB error during vector clear — best-effort
                logger.warning(
                    "asset_search_vector_clear_failed "
                    "asset_id=%s prior_status=%s error=%s",
                    instance.pk, prior_status, exc,
                )
        return

    pk = instance.pk

    def _enqueue():
        try:
            from hub.apps.search.tasks import (
                enqueue_asset_search_vector_update,
            )

            enqueue_asset_search_vector_update(str(pk))
        except (ConnectionError, TimeoutError, OSError, ImportError) as exc:
            # Transient infrastructure / import failure — best-effort.
            logger.warning(
                "asset_search_vector_enqueue_failed "
                "asset_id=%s error=%s",
                pk,
                exc,
            )
        except (RedisError, RuntimeError) as exc:
            # Redis/RQ operational error — log at ERROR so SRE can
            # distinguish infra failures from coding errors.
            # Programming errors (AttributeError, TypeError, KeyError,
            # NameError) are NOT caught — they propagate so tests/CI
            # catch bugs before production.
            logger.error(
                "asset_search_vector_enqueue_redis_or_rq_error "
                "asset_id=%s error=%s",
                pk,
                exc,
            )

    transaction.on_commit(_enqueue)
