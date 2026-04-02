"""
Unit tests for worker service health check endpoints (Phase 2.5).

Tests /healthz (liveness) and /ready (readiness) probes.

Design notes
------------
- healthz() never touches DB/Redis — pure process-level check.

- ready() performs live connectivity checks (DB ``SELECT 1``,
  Redis PING, cache GET).  Happy-path tests use the
  ``runtime_db_connection`` fixture (see conftest.py) to point
  Django's connection at the real runtime database, bypassing
  pytest-django's test-DB rewrite.

  Failure-path tests patch each dependency at the correct site.

- Django's ``TestCase`` is intentionally NOT used.
"""
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

from services.worker.health import healthz, ready

_REDIS = 'services.worker.health.get_redis_queue_client'
_CACHE = 'services.worker.health.cache'


def _mock_cursor_ok():
    """Return a mock cursor context manager that silently
    succeeds (no real SQL)."""
    mock = MagicMock()
    enter_mock = MagicMock()
    mock.return_value.__enter__ = MagicMock(
        return_value=enter_mock,
    )
    mock.return_value.__exit__ = MagicMock(
        return_value=False,
    )
    return mock, enter_mock


def _mock_redis_ok():
    """Return a mock get_redis_queue_client that returns a
    client whose ping() returns True."""
    client = MagicMock()
    client.ping.return_value = True
    return MagicMock(return_value=client), client


# -------------------------------------------------------------------
# /healthz  (liveness) — no DB, no Redis, no cache
# -------------------------------------------------------------------


class TestHealthzEndpoint:
    """Test /healthz endpoint (liveness probe) - Phase 2.5.1"""

    def test_healthz_returns_200_with_all_fields(self):
        """healthz returns 200 with status, service, timestamp."""
        status_code, content = healthz()

        assert status_code == 200
        assert content['status'] == 'ok'
        assert content['service'] == 'worker-service'
        # Verify timestamp is valid ISO format
        assert 'timestamp' in content
        datetime.fromisoformat(content['timestamp'])

    def test_healthz_json_response_has_all_fields(self):
        """JsonResponse mode includes all response fields."""
        response = healthz(request=MagicMock())

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['status'] == 'ok'
        assert data['service'] == 'worker-service'
        assert 'timestamp' in data

    def test_healthz_no_deep_checks(self):
        """healthz doesn't include dependency checks."""
        _, content = healthz()

        assert 'checks' not in content
        assert 'database' not in content
        assert 'redis' not in content
        assert 'cache' not in content


# -------------------------------------------------------------------
# /ready  (readiness) — happy path
# -------------------------------------------------------------------


class TestReadyEndpointLive:
    """Test /ready with real DB/Redis/cache - Phase 2.5.2"""

    def test_ready_returns_200_when_all_deps_ready(
        self, django_db_blocker, runtime_db_connection,
    ):
        """ready returns 200 with all checks ok."""
        with (
            django_db_blocker.unblock(),
            runtime_db_connection(),
        ):
            status_code, content = ready()

        assert status_code == 200
        assert content['status'] == 'ready'
        assert content['service'] == 'worker-service'
        assert content['checks']['database'] == 'ok'
        assert content['checks']['redis_queue'] == 'ok'
        assert content['checks']['cache'] == 'ok'
        assert 'timestamp' in content
        # Should NOT have error field on success
        assert 'error' not in content

    def test_ready_json_response_has_all_fields(
        self, django_db_blocker, runtime_db_connection,
    ):
        """JsonResponse mode includes all check details."""
        with (
            django_db_blocker.unblock(),
            runtime_db_connection(),
        ):
            response = ready(request=MagicMock())

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['status'] == 'ready'
        assert data['checks']['database'] == 'ok'
        assert data['checks']['redis_queue'] == 'ok'
        assert data['checks']['cache'] == 'ok'


# -------------------------------------------------------------------
# /ready  (readiness) — individual failure paths
# -------------------------------------------------------------------


class TestReadyEndpointFailure:
    """Test /ready endpoint failure scenarios - Phase 2.5.2"""

    def test_503_when_database_unavailable(self):
        """DB failure → 503, other checks still run."""
        from django.db import connection

        db_err = Exception("Connection refused")
        redis_fn, redis_client = _mock_redis_ok()

        with (
            patch.object(
                connection, 'cursor', side_effect=db_err,
            ),
            patch(_REDIS, redis_fn),
            patch(_CACHE) as mock_cache,
        ):
            mock_cache.get.return_value = None
            status_code, content = ready()

        assert status_code == 503
        assert content['status'] == 'not_ready'
        assert 'unhealthy' in content['checks']['database']
        # Redis and cache should still be checked
        assert content['checks']['redis_queue'] == 'ok'
        assert content['checks']['cache'] == 'ok'
        # Error field mentions the failing component
        assert 'database' in content['error']

    def test_503_when_redis_unavailable(self):
        """Redis failure → 503, other checks still run."""
        from django.db import connection

        cursor_mock, enter_mock = _mock_cursor_ok()
        redis_err = Exception("Redis connection refused")

        with (
            patch.object(connection, 'cursor', cursor_mock),
            patch(_REDIS, side_effect=redis_err),
            patch(_CACHE) as mock_cache,
        ):
            mock_cache.get.return_value = None
            status_code, content = ready()

        assert status_code == 503
        assert content['status'] == 'not_ready'
        assert content['checks']['database'] == 'ok'
        assert 'unhealthy' in content['checks']['redis_queue']
        assert content['checks']['cache'] == 'ok'
        assert 'redis_queue' in content['error']

    def test_503_when_cache_unavailable(self):
        """Cache failure → 503, other checks still run."""
        from django.db import connection

        cursor_mock, _ = _mock_cursor_ok()
        redis_fn, _ = _mock_redis_ok()
        cache_err = Exception("Cache backend down")

        with (
            patch.object(connection, 'cursor', cursor_mock),
            patch(_REDIS, redis_fn),
            patch(_CACHE) as mock_cache,
        ):
            mock_cache.get.side_effect = cache_err
            status_code, content = ready()

        assert status_code == 503
        assert content['status'] == 'not_ready'
        assert content['checks']['database'] == 'ok'
        assert content['checks']['redis_queue'] == 'ok'
        assert 'unhealthy' in content['checks']['cache']
        assert 'cache' in content['error']

    def test_503_when_all_deps_down(self):
        """All deps down → 503, error lists all failures."""
        from django.db import connection

        with (
            patch.object(
                connection, 'cursor',
                side_effect=Exception("DB down"),
            ),
            patch(
                _REDIS,
                side_effect=Exception("Redis down"),
            ),
            patch(_CACHE) as mock_cache,
        ):
            mock_cache.get.side_effect = Exception(
                "Cache down",
            )
            status_code, content = ready()

        assert status_code == 503
        assert content['status'] == 'not_ready'
        assert 'unhealthy' in content['checks']['database']
        assert 'unhealthy' in content['checks']['redis_queue']
        assert 'unhealthy' in content['checks']['cache']
        # Error field should mention all three
        assert 'database' in content['error']
        assert 'redis_queue' in content['error']
        assert 'cache' in content['error']

    def test_database_check_executes_select_1(self):
        """ready() runs SELECT 1 to verify DB connectivity."""
        from django.db import connection

        cursor_mock, enter_mock = _mock_cursor_ok()
        redis_fn, _ = _mock_redis_ok()

        with (
            patch.object(connection, 'cursor', cursor_mock),
            patch(_REDIS, redis_fn),
            patch(_CACHE) as mock_cache,
        ):
            mock_cache.get.return_value = None
            ready()

        cursor_mock.assert_called_once()
        enter_mock.execute.assert_called_once_with(
            "SELECT 1",
        )

    def test_redis_check_calls_ping(self):
        """ready() calls ping() on the Redis client."""
        from django.db import connection

        cursor_mock, _ = _mock_cursor_ok()
        redis_fn, redis_client = _mock_redis_ok()

        with (
            patch.object(connection, 'cursor', cursor_mock),
            patch(_REDIS, redis_fn),
            patch(_CACHE) as mock_cache,
        ):
            mock_cache.get.return_value = None
            ready()

        redis_fn.assert_called_once()
        redis_client.ping.assert_called_once()

    def test_cache_check_calls_get(self):
        """ready() calls cache.get() to verify cache."""
        from django.db import connection

        cursor_mock, _ = _mock_cursor_ok()
        redis_fn, _ = _mock_redis_ok()

        with (
            patch.object(connection, 'cursor', cursor_mock),
            patch(_REDIS, redis_fn),
            patch(_CACHE) as mock_cache,
        ):
            mock_cache.get.return_value = None
            ready()

        mock_cache.get.assert_called_once_with(
            'health_check_test', None,
        )
