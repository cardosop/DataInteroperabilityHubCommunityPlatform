"""
Shared fixtures for concurrency tests.

TransactionTestCase does TRUNCATE … CASCADE on teardown which can
hit the default 30 s statement_timeout on a busy shared DB (other
services hold connections). This autouse fixture raises the timeout
so TRUNCATE completes without blocking the test run.
"""
import pytest
from django.db import connection


@pytest.fixture(autouse=True)
def _raise_statement_timeout():
    """Increase statement_timeout for concurrency tests.

    The shared test DB (hub_test_test_shared) has active sessions
    from api-service-test. TRUNCATE CASCADE waits for those locks
    and can exceed the default 30s timeout. 120s is sufficient.
    """
    with connection.cursor() as cur:
        cur.execute("SET statement_timeout = '120s'")
    yield
