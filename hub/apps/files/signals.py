"""
File Signals — Phase 260.1.C

pre_delete handler that retires linked Dataset rows before the File row
is hard-deleted, so orphaned Dataset rows carry a ``RETIRED`` status +
``retired_at`` timestamp rather than remaining ``ACTIVE`` with a NULL
file FK.
"""
import logging

from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils import timezone

from hub.apps.datasets.models import Dataset, DatasetStatus

logger = logging.getLogger(__name__)


@receiver(pre_delete, sender="files.File")
def retire_datasets_on_file_hard_delete(sender, instance, **kwargs):
    """Phase 260.1.C.3 — mark linked Datasets RETIRED before the FK is SET_NULL.

    When a File row is hard-deleted, the FK on Dataset is SET_NULL by the
    database.  Without this signal, the Dataset row silently becomes an
    orphan with ``status=ACTIVE`` and ``file=None`` — indistinguishable
    from a transient upload bug.  Retiring the row preserves the lifecycle
    signal: consumers can see the Dataset was *retired because its backing
    file was permanently removed*.
    """
    try:
        updated = (
            Dataset.objects.filter(file_id=instance.pk)
            .exclude(status=DatasetStatus.RETIRED)
            .update(
                status=DatasetStatus.RETIRED,
                retired_at=timezone.now(),
            )
        )
        if updated:
            logger.info(
                "file_hard_delete_retired_datasets",
                extra={
                    "file_id": str(instance.pk),
                    "datasets_retired": updated,
                },
            )
    except Exception:
        logger.warning(
            "file_hard_delete_retire_datasets_failed file_id=%s",
            instance.pk,
            exc_info=True,
        )
