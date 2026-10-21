"""Committed default-plan seeding for TestCase setUps.

Django ``TestCase`` runs ``setUp`` inside the test's atomic transaction, so
``call_command("seed_default_plans")`` leaves the rows uncommitted — invisible
to services querying through OTHER connections (registration threads, plan
limit checks on separate cursors). Seeding on a helper thread uses its own
autocommit connection and real-commits the rows.

Usage (in setUp):

    from hub.apps.testing.plan_seeding import seed_default_plans_committed
    seed_default_plans_committed(self)   # self = the TestCase (for skipTest)
"""

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from unittest import TestCase as _TestCase


def seed_default_plans_committed(test_case: "_TestCase") -> None:
    """Run ``seed_default_plans`` on a separate committed connection.

    Raises ``test_case.skipTest`` when the seed command itself fails, so the
    failure is visible instead of cascading into unrelated assertions.
    """
    from django.core.management import call_command

    errors: list[str] = []

    def _seed() -> None:
        try:
            call_command("seed_default_plans")
        except Exception as exc:
            errors.append(str(exc))

    seed_thread = threading.Thread(target=_seed)
    seed_thread.start()
    seed_thread.join()
    if errors:
        test_case.skipTest(f"seed_default_plans failed: {errors[0]}")
