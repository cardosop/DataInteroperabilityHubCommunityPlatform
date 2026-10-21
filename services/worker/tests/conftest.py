import logging

logger = logging.getLogger(__name__)
"""
Worker service test conftest — bridges to project-level conftest patches.

When running ``pytest services/worker/tests/``, the root testpaths
(hub/apps, tests) are not collected, so hub/conftest.py and
tests/conftest.py are never loaded.  Those files contain critical
patches (sync_apps no-op, keepdb for TEST_DB_SUFFIX, sql_flush CASCADE,
TenantPlan seeding) that must be active for any django_db test.

This conftest imports both files so all patches are applied.
"""

import importlib.util
import os
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

# Ensure repo root is on sys.path so project conftest modules
# are importable.
_repo_root = Path(__file__).resolve().parents[3]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")


# Load project-level conftest patches.
# NOTE: this directory is a package (tests/__init__.py exists) and
# services/worker is not, so pytest imports this module as ``tests.conftest``.
# A plain ``import tests.conftest`` would therefore import this module itself,
# never reaching the repo-root tests/conftest.py.  Load the root conftest by
# file path instead.
def _raise_conftest_load_error(path: Path) -> None:
    raise ImportError(f"Unable to load conftest from {path}")


try:
    _tests_conftest_path = _repo_root / "tests" / "conftest.py"
    _tests_conftest_spec = importlib.util.spec_from_file_location(
        "root_tests_conftest", _tests_conftest_path
    )
    if _tests_conftest_spec is None or _tests_conftest_spec.loader is None:
        _raise_conftest_load_error(_tests_conftest_path)
    _root_tests_conftest = importlib.util.module_from_spec(_tests_conftest_spec)
    _tests_conftest_spec.loader.exec_module(_root_tests_conftest)
except ImportError:
    logger.warning("'dependency' import unavailable")

try:
    import hub.conftest
except ImportError:
    logger.warning("'hub.conftest' import unavailable")


@pytest.fixture
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
        db_conf = settings.DATABASES["default"]
        current_name = db_conf["NAME"]
        runtime_name = os.environ.get(
            "POSTGRES_DB",
            "hub_test_test_shared",
        )

        # If already pointing at the runtime DB, nothing to do.
        if current_name == runtime_name:
            yield
            return

        db_conf["NAME"] = runtime_name
        conn = connections["default"]
        conn.close()
        try:
            yield
        finally:
            db_conf["NAME"] = current_name
            conn.close()

    return _swap
