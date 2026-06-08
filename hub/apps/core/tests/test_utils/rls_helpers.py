"""
285.14.1.1 -- RLS tenant isolation test helpers.

Provides reusable primitives for verifying Row-Level Security policies
are correctly enforced across all tenant-scoped models.
"""
from __future__ import annotations
import pytest

from contextlib import contextmanager
from typing import Any, Type
from uuid import UUID

from django.db import connection, models, transaction


@contextmanager
def set_tenant_context(tenant_id: str | UUID):
    """Set ``app.current_tenant_id`` for the current transaction.

    Usage in tests::

        with set_tenant_context(str(tenant_a.id)):
            # Queries in this block run under tenant_a's RLS context.
            results = MyModel.objects.all()

    Uses ``SET LOCAL`` so the GUC is scoped to the current transaction
    and does not leak across test boundaries.
    """
    tenant_id_str = str(tenant_id)
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_tenant_id', true)")
            previous = cursor.fetchone()[0] or None
            try:
                cursor.execute(
                    "SET LOCAL app.current_tenant_id = %s", [tenant_id_str]
                )
                yield
            finally:
                if previous:
                    cursor.execute(
                        "SET LOCAL app.current_tenant_id = %s", [previous]
                    )
                else:
                    cursor.execute("SET LOCAL app.current_tenant_id = DEFAULT")


def clear_tenant_context():
    """Reset ``app.current_tenant_id`` to DEFAULT.

    Call this in ``tearDown`` or ``setUp`` to ensure no stale tenant
    context leaks between tests.  Wrapped in ``transaction.atomic()``
    so ``SET LOCAL`` has a transaction scope even under autocommit.
    """
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL app.current_tenant_id = DEFAULT")
    except Exception:
        pass


def assert_tenant_isolation(
    model_class: Type[models.Model],
    creating_tenant_id: str | UUID,
    accessing_tenant_id: str | UUID,
    creation_kwargs: dict[str, Any] | None = None,
):
    """Assert that RLS prevents cross-tenant access on a model.

    1. Creates a row under ``creating_tenant_id``'s context.
    2. Switches to ``accessing_tenant_id``'s context.
    3. Asserts the row is NOT visible from the other tenant.

    Args:
        model_class: The Django model class under test.  Designed for
                     models with a direct ``tenant_id`` column.  For
                     indirect-FK models (tenant accessed through a
                     parent chain), the caller MUST provide
                     ``creation_kwargs`` that set up the parent chain
                     and verify isolation manually — this helper's
                     auto-insert of ``tenant_id`` won't work for those.
        creating_tenant_id: Tenant that OWNS the row.
        accessing_tenant_id: Tenant that MUST NOT see it.
        creation_kwargs: Extra kwargs for ``model_class.objects.create()``.
                         Required fields for the model MUST be included
                         here (e.g. ForeignKey fields without a default).
    """
    row_id: str | None = None

    with set_tenant_context(str(creating_tenant_id)):
        # Use a unique value for the test row so we can assert
        # it's the SAME row being hidden/revealed.
        kwargs = dict(creation_kwargs or {})
        if hasattr(model_class, "tenant_id") and "tenant_id" not in kwargs:
            kwargs["tenant_id"] = creating_tenant_id
        row = model_class.objects.create(**kwargs)
        row_id = str(row.pk)

        # Row MUST be visible to the creating tenant.
        assert model_class.objects.filter(pk=row.pk).exists(), (
            f"{model_class.__name__}: creating tenant cannot see its own row. "
            f"This usually means RLS is misconfigured (tenant_id mismatch)."
        )

    with set_tenant_context(str(accessing_tenant_id)):
        # Row MUST NOT be visible to a different tenant.
        if row_id is not None:
            assert not model_class.objects.filter(pk=row_id).exists(), (
                f"{model_class.__name__}: cross-tenant access LEAK -- "
                f"tenant {accessing_tenant_id} can see row owned by "
                f"tenant {creating_tenant_id}. RLS policy may be missing "
                f"or incorrectly configured."
            )

    # Back in the creating tenant's context, row must still exist.
    with set_tenant_context(str(creating_tenant_id)):
        assert model_class.objects.filter(pk=row_id).exists(), (
            f"{model_class.__name__}: row disappeared -- possible cascade or "
            f"transaction rollback issue."
        )
