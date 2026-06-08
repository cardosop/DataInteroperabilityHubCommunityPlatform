"""
Test-only fixtures for the ``datasets`` app.

Migrated for Phase 260.5.A to present era (post-migration-0110).

Migration 0110 removed the ``unique_dataset_file_purpose_per_tenant``
DB-level unique constraint on ``(tenant_id, file_id, file_handle_purpose)``.
Multiple ``PRIMARY`` datasets on the same file are now allowed at the
database layer.  Application-level enforcement may be re-added later.

This conftest installs a ``pre_save`` signal — **only loaded under
pytest** — that auto-rotates ``file_handle_purpose`` for the second
and third rows on the same ``(tenant, file)``.  The rotation produces
realistic multi-purpose test data (``PRIMARY`` + ``SAMPLE`` +
``SCHEMA_ONLY``) without requiring every test to explicitly set
purposes.  Behavior matrix:

* No prior row for ``(tenant, file)`` → keep ``PRIMARY``.
* Prior ``PRIMARY`` → assign ``SAMPLE``.
* Prior ``PRIMARY`` + ``SAMPLE`` → assign ``SCHEMA_ONLY``.
* Beyond 3 rows → keep the provided default.

The signal is gated on ``settings.ENVIRONMENT == "test"`` so a
production deploy can never silently rotate purposes — the rotation
exists purely as a test-fixture convenience.
"""
from __future__ import annotations
import pytest

from django.conf import settings
from django.core.exceptions import AppRegistryNotReady
from django.db.models.signals import pre_save


_SKIP_ROTATION_ATTR = "_skip_test_purpose_rotation"


def _rotate_purpose(sender, instance, **_kwargs) -> None:
    if getattr(settings, "ENVIRONMENT", "").lower() != "test":
        return
    # Tests that deliberately exercise the unique-constraint-fires
    # branch set ``instance._skip_test_purpose_rotation = True`` so
    # the constraint surfaces as ``IntegrityError`` per the
    # production contract.  Without the opt-out the rotation here
    # absorbs the collision and the test's ``with assertRaises``
    # never trips.
    if getattr(instance, _SKIP_ROTATION_ATTR, False):
        return
    # Only rotate on a freshly-created row; updates keep their existing purpose.
    # ``Dataset.id`` is a ``UUIDField(default=uuid.uuid4)`` so ``instance.pk``
    # is pre-populated at ``__init__`` time — the canonical
    # "is this a create?" check is ``instance._state.adding``, which Django
    # sets False on rows materialised from a DB query.
    if not getattr(instance._state, "adding", True):
        return
    if instance.file_id is None or instance.tenant_id is None:
        return
    from hub.apps.datasets.models import Dataset, DatasetFileHandlePurpose

    if instance.file_handle_purpose != DatasetFileHandlePurpose.PRIMARY:
        return
    used = set(
        Dataset.objects.filter(
            tenant_id=instance.tenant_id,
            file_id=instance.file_id,
        ).values_list("file_handle_purpose", flat=True)
    )
    rotation = (
        DatasetFileHandlePurpose.PRIMARY,
        DatasetFileHandlePurpose.SAMPLE,
        DatasetFileHandlePurpose.SCHEMA_ONLY,
    )
    for choice in rotation:
        if choice not in used:
            instance.file_handle_purpose = choice
            return
    # All three taken — let the constraint fire so tests that exercise
    # the over-subscription path still see the legitimate 409 case.


def _connect_signal() -> None:
    """Idempotently connect the rotation signal."""
    from hub.apps.datasets.models import Dataset

    pre_save.connect(
        _rotate_purpose,
        sender=Dataset,
        dispatch_uid="datasets_tests_auto_rotate_file_handle_purpose",
    )


# Wire on import so collection-time module imports inside the
# datasets tests package have the signal active before any
# ``Dataset.objects.create(...)`` runs in setUp.
#
# pytest-django loads conftest.py after ``django.setup()``, so
# ``AppRegistryNotReady`` is not expected here.  The guard is
# defensive (in case a future pytest-django version changes the
# import order); if the app registry isn't ready the signal simply
# stays disconnected for the session.
try:
    _connect_signal()
except AppRegistryNotReady:
    pass
