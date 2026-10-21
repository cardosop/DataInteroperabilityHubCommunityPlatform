"""Phase 313 verification — test-mode-safe ``transaction.on_commit`` wrapper.

The repo's TestCase harness holds an outer transaction for the whole test
(``autocommit=False`` even under ``django_db(transaction=True)``), so
callbacks registered with ``transaction.on_commit()`` can never fire while
the test body executes. Production correctness keeps the post-commit
deferral (side effects must not fire on rolled-back savepoints); test mode
runs the callback synchronously via the same escape hatch the event bus
uses (``EVENT_BUS_FORCE_SYNC_PERSISTENCE``).

See also the AssetCreationWorkflow docstring (Phase 250.1.G), which
documents the same TestCase-wrapping discovery for the workflow path.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def run_after_commit(callback: Callable[..., Any]) -> None:
    """Run ``callback`` after the outer transaction commits.

    In pytest/TESTING mode the callback runs synchronously — the outer
    test transaction never commits during the test body, so the deferred
    form would silently never run (and side-effect contract tests would
    fail for the wrong reason).
    """
    from django.conf import settings
    from django.db import transaction

    if getattr(settings, "EVENT_BUS_FORCE_SYNC_PERSISTENCE", False):
        callback()
    else:
        transaction.on_commit(callback)
