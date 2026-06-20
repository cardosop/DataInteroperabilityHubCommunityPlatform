"""
Session-scoped test fixtures for hub/tests.

Patches that previously lived in hub/settings.py have been moved here so that
settings.py stays free of test-only monkey-patches.
"""

import pytest


@pytest.fixture(autouse=True, scope="session")
def disable_db_thread_validation():
    """Disable Django's validate_thread_sharing for the test session.

    pytest-django creates database connections in one thread but Django's
    TestCase executes queries in another.  The patch is safe because
    pytest-django manages the full connection lifecycle.  It is restored
    after the session so the method is back to normal for any code that
    runs after the suite.
    """
    import django.db.backends.base.base as _db_base

    original = _db_base.BaseDatabaseWrapper.validate_thread_sharing
    _db_base.BaseDatabaseWrapper.validate_thread_sharing = lambda self: None
    yield
    _db_base.BaseDatabaseWrapper.validate_thread_sharing = original
