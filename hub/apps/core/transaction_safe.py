"""
Transaction-safe side-effect execution.

When code inside @transaction.atomic catches a DB exception without re-raising,
Django's ``needs_rollback`` flag stays True on the connection.  Django 6.0's
``CursorWrapper.execute()`` calls ``validate_no_broken_transaction()`` before
every SQL statement — so the stale flag blocks ALL subsequent queries in the
same request, causing cascade failures.

``run_side_effect()`` wraps the callable in its own ``transaction.atomic()``
savepoint.  If the callable raises, the inner savepoint absorbs the error and
``needs_rollback`` is scoped to that savepoint only.  The outer transaction
stays clean.

Usage inside @transaction.atomic methods::

    from hub.apps.core.transaction_safe import run_side_effect

    @transaction.atomic
    def create_asset(self, ...):
        asset = Asset.objects.create(...)  # main operation

        # Side-effects that must not break the main operation:
        run_side_effect(create_audit_event, resource_type="ASSET", ...)
        run_side_effect(indexer.index_asset, asset)
"""

import logging
from typing import Any, Callable

from django.db import transaction

logger = logging.getLogger(__name__)


def run_side_effect(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Execute *func* in a nested savepoint so DB errors don't poison the caller.

    Returns the result of *func* on success, or ``None`` on failure.
    Exceptions are logged at WARNING level and never propagated.
    """
    try:
        with transaction.atomic():
            return func(*args, **kwargs)
    except Exception:
        logger.warning(
            "side_effect_failed",
            extra={
                "func": getattr(func, "__qualname__", str(func)),
                "args_repr": repr(args)[:200],
            },
            exc_info=True,
        )
        return None
