"""
Dataset Signals — Phase 91.13

post_save / post_delete handlers that invalidate the dataset caches
when a Dataset record is created, updated, or deleted.

Follows the existing contracts/signals.py pub/sub pattern:
best-effort, failures logged at WARNING, never propagate.
"""
import logging

from django.db.models.signals import post_save, post_delete
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
