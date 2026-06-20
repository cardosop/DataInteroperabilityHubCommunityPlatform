"""
Reusable model mixins (Phase 92).

Provides SoftDeleteMixin for consistent soft-delete across models.
"""

import logging

from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet that filters soft-deleted rows.

    NOTE: ``delete()`` is intentionally NOT overridden.  Django's cascade
    delete, test teardown, and admin actions all call ``QuerySet.delete()``
    and expect real SQL ``DELETE``.  Overriding it to ``UPDATE deleted_at``
    silently breaks cascade integrity and leaves orphaned rows.

    Use ``soft_delete()`` for explicit soft-deletion of querysets.
    """

    def soft_delete(self):
        """Soft-delete all rows in the queryset."""
        return self.update(deleted_at=timezone.now())

    def alive(self):
        """Return only non-deleted rows."""
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        """Return only soft-deleted rows."""
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager):
    """Default manager that excludes soft-deleted rows."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class AllObjectsManager(models.Manager):
    """Manager that includes ALL rows (including soft-deleted)."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteMixin(models.Model):
    """Mixin that adds soft-delete support to any model.

    Adds a ``deleted_at`` DateTimeField.  The default manager
    (``objects``) excludes rows where ``deleted_at`` is set.
    Use ``all_objects`` to include soft-deleted rows.

    Usage::

        class MyModel(SoftDeleteMixin, models.Model):
            name = models.CharField(max_length=255)

            class Meta(SoftDeleteMixin.Meta):
                db_table = "my_table"
    """

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        db_index=True,
        help_text="Timestamp when this record was soft-deleted",
    )

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def soft_delete(self):
        """Mark this instance as soft-deleted."""
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def restore(self):
        """Restore a soft-deleted instance."""
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])

    @property
    def is_deleted(self):
        """Return True if this instance is soft-deleted."""
        return self.deleted_at is not None
