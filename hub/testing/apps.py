"""
Django app config for hub.testing.

When ``TESTING=1`` is set in the environment, this app is added to
INSTALLED_APPS.  All test-environment setup previously done here
(monkey-patching Django internals to support ``TEST_DB_SUFFIX=shared``)
has been removed in favour of root-cause fixes:

- Every app now has a ``migrations/__init__.py`` (no more ``sync_apps``).
- ``TEST_DB_SUFFIX=shared`` removed — each xdist worker has its own database.
- ``TenantPlan`` seed data moved to a data migration.
- The three essential small adjustments (thread validation, TRUNCATE CASCADE,
  fakeredis fallback) now live inline in ``hub/conftest.py``.
"""

from django.apps import AppConfig


class TestingConfig(AppConfig):
    name = "hub.testing"
    label = "hub_testing"
    verbose_name = "Hub Testing Infrastructure"

    def ready(self):
        # All setup moved to hub/conftest.py._setup_test_environment()
        pass
