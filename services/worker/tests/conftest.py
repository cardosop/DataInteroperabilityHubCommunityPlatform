"""
Worker service test conftest — bridges to project-level conftest patches.

When running ``pytest services/worker/tests/``, the root testpaths
(hub/apps, tests) are not collected, so hub/conftest.py and
tests/conftest.py are never loaded.  Those files contain critical
patches (sync_apps no-op, keepdb for TEST_DB_SUFFIX, sql_flush CASCADE,
TenantPlan seeding) that must be active for any django_db test.

This conftest imports both files so all patches are applied.
"""
import os
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

# Ensure repo root is on sys.path so project conftest modules
# are importable.
_repo_root = Path(__file__).resolve().parents[3]  # noqa: E501
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")

# Load project-level conftest patches.
try:
    import tests.conftest  # noqa: F401
except ImportError:
    pass

try:
    import hub.conftest  # noqa: F401
except ImportError:
    pass


@pytest.fixture()
def runtime_db_connection():
    """Yield a context manager that points Django's default connection
    at the real runtime database (POSTGRES_DB env var) instead of the
    test database that pytest-django creates.

    ready() only runs ``SELECT 1`` — no application tables needed.
    pytest-django rewrites DATABASES["default"]["NAME"] to a test DB
    name that may not exist when ``@pytest.mark.django_db`` is absent.
    This fixture restores the original name for the duration of the
    call, then reverts it so other tests are unaffected.
    """
    from django.conf import settings
    from django.db import connections

    @contextmanager
    def _swap():
        db_conf = settings.DATABASES['default']
        current_name = db_conf['NAME']
        runtime_name = os.environ.get(
            'POSTGRES_DB', 'hub_test_test_shared',
        )

        # If already pointing at the runtime DB, nothing to do.
        if current_name == runtime_name:
            yield
            return

        db_conf['NAME'] = runtime_name
        conn = connections['default']
        conn.close()
        try:
            yield
        finally:
            db_conf['NAME'] = current_name
            conn.close()

    return _swap
