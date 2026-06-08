"""
Dataset Signals — Phase 91.13

post_save / post_delete handlers that invalidate the dataset caches
when a Dataset record is created, updated, or deleted.

Follows the existing contracts/signals.py pub/sub pattern:
best-effort, failures logged at WARNING, never propagate.
"""
import logging

from django.db import transaction
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="datasets.Dataset")
def invalidate_dataset_cache_on_save(sender, instance, **kwargs):
    """Invalidate dataset caches when a dataset is saved."""
    try:
        from hub.apps.datasets.caching import invalidate_dataset_caches

        dataset_id = str(instance.pk)
        tenant_id = str(instance.tenant_id) if instance.tenant_id else None
        invalidate_dataset_caches(dataset_id, tenant_id)
        logger.debug(
            "dataset_cache_invalidated_on_save dataset_id=%s",
            dataset_id,
        )
    except Exception as exc:
        logger.warning(
            "dataset_cache_invalidation_failed dataset_id=%s error=%s",
            instance.pk,
            exc,
        )


@receiver(post_delete, sender="datasets.Dataset")
def invalidate_dataset_cache_on_delete(sender, instance, **kwargs):
    """Invalidate dataset caches when a dataset is deleted."""
    try:
        from hub.apps.datasets.caching import invalidate_dataset_caches

        dataset_id = str(instance.pk)
        tenant_id = str(instance.tenant_id) if instance.tenant_id else None
        invalidate_dataset_caches(dataset_id, tenant_id)
        logger.debug(
            "dataset_cache_invalidated_on_delete dataset_id=%s",
            dataset_id,
        )
    except Exception as exc:
        logger.warning(
            "dataset_cache_invalidation_failed dataset_id=%s error=%s",
            instance.pk,
            exc,
        )


@receiver(post_delete, sender="datasets.Dataset")
def schedule_orphan_file_check_on_dataset_delete(sender, instance, **kwargs):
    """Phase 260.1.B — enqueue orphan-file soft-delete eligibility check."""
    try:
        from hub.apps.datasets.orphan_file_reconcile import (
            schedule_orphan_file_check_after_dataset_delete,
        )
        schedule_orphan_file_check_after_dataset_delete(
            tenant_id=instance.tenant_id,
            file_id=instance.file_id,
            dataset_asset_id=instance.asset_id,
        )
    except Exception as exc:
        logger.warning(
            "orphan_file_schedule_failed dataset_id=%s error=%s",
            instance.pk,
            exc,
        )


# ---------------------------------------------------------------------------
# Phase 230.3.7 (REQ-SEM-TOMBSTONE-001) — Dataset archive → semantic tombstone
# ---------------------------------------------------------------------------
#
# Dataset has a soft-archive field ``archived_at`` (DateTimeField,
# nullable).  When the value transitions from NULL → non-NULL the
# spec mandates the corresponding SemanticResource flips to
# TOMBSTONED.  We capture the prior value in pre_save and diff in
# post_save to fire exactly once on the transition.

_PRIOR_DATASET_ARCHIVED_ATTR = "_pre_save_archived_at_for_tombstone"


def _capture_prior_dataset_archived_at(sender, instance, **kwargs):
    """pre_save listener — record ``archived_at`` from the DB row
    so post_save can detect a NULL → non-NULL transition exactly
    once."""
    if not instance.pk:
        setattr(instance, _PRIOR_DATASET_ARCHIVED_ATTR, None)
        return
    try:
        prior = sender.objects.only("archived_at").get(pk=instance.pk)
    except sender.DoesNotExist:
        setattr(instance, _PRIOR_DATASET_ARCHIVED_ATTR, None)
        return
    setattr(instance, _PRIOR_DATASET_ARCHIVED_ATTR, prior.archived_at)


@receiver(post_save, sender="datasets.Dataset")
def fire_dataset_tombstone_on_archive(sender, instance, **kwargs):
    """post_save listener — fires the canonical tombstone path when
    ``archived_at`` flips from NULL to non-NULL.

    Idempotent: subsequent saves with ``archived_at`` already set
    do not re-tombstone (the canonical path also short-circuits on
    already-TOMBSTONED rows, but we add the early exit here so the
    common no-op save doesn't even enqueue an on_commit callback).
    """
    new_archived = getattr(instance, "archived_at", None)
    if new_archived is None:
        return
    prior_archived = getattr(instance, _PRIOR_DATASET_ARCHIVED_ATTR, None)
    if prior_archived is not None:
        # Already archived; no transition.
        return

    dataset_id = instance.pk

    def _dispatch():
        try:
            from hub.apps.semantic.tombstone import (
                REASON_DATASET_ARCHIVED, tombstone_resource,
            )
            tombstone_resource(
                resource_type="DATASET",
                resource_id=dataset_id,
                reason=REASON_DATASET_ARCHIVED,
            )
        except Exception as exc:
            logger.warning(
                "dataset_tombstone_dispatch_failed "
                "dataset_id=%s error=%s",
                dataset_id, exc,
            )

    transaction.on_commit(_dispatch)


# Wire pre_save at import time (parallel to assets/signals.py pattern).
def _connect_dataset_tombstone_pre_save():
    pre_save.connect(
        _capture_prior_dataset_archived_at,
        sender="datasets.Dataset",
        dispatch_uid="phase_230_3_capture_prior_dataset_archived_at",
    )


_connect_dataset_tombstone_pre_save()


@receiver(post_save, sender="datasets.Dataset")
def rebuild_dataset_search_vector(sender, instance, **kwargs):
    """Enqueue a search vector rebuild for the saved Dataset."""
    try:
        from hub.apps.search.tasks import (
            enqueue_dataset_search_vector_update,
        )

        enqueue_dataset_search_vector_update(str(instance.pk))
    except Exception as exc:
        logger.warning(
            "dataset_search_vector_enqueue_failed "
            "dataset_id=%s error=%s",
            instance.pk,
            exc,
        )
