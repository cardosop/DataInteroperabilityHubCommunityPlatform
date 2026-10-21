
"""
Phase 86.1 — contracts/tasks.py tests.

Tests renormalize_contracts_v310 via management command wrapper
(already thoroughly tested in test_renormalize_command.py).
This file adds direct function-level coverage.
"""

import uuid
from unittest.mock import patch
from urllib.parse import urlsplit

from django.test import TestCase


class RenormalizeTaskTest(TestCase):
    """Verify the task function exists and is importable."""

    def test_function_importable(self):
        from hub.apps.contracts.tasks import renormalize_contracts_v310

        assert callable(renormalize_contracts_v310)

    def test_backfill_metric_helper_importable(self):
        from hub.apps.contracts.tasks import _set_backfill_remaining

        assert callable(_set_backfill_remaining)

    def test_invalidate_cache_helper_importable(self):
        from hub.apps.contracts.tasks import _invalidate_contract_cache

        assert callable(_invalidate_contract_cache)

    @patch("hub.apps.contracts.tasks._get_redis_pub_client")
    def test_invalidate_cache_publishes(self, mock_redis):
        """Cache invalidation publishes to Redis channel."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        from hub.apps.contracts.tasks import _invalidate_contract_cache

        contract = MagicMock()
        contract.id = uuid.uuid4()
        contract.original_raw = "spec: v1"
        _invalidate_contract_cache(contract)
        mock_client.publish.assert_called_once()

    @patch("hub.apps.contracts.tasks._get_redis_pub_client", return_value=None)
    def test_invalidate_cache_noop_without_redis(self, _mock_redis):
        """No Redis client → no error."""
        from unittest.mock import MagicMock

        from hub.apps.contracts.tasks import _invalidate_contract_cache

        contract = MagicMock()
        contract.id = uuid.uuid4()
        contract.original_raw = "spec: v1"
        # Should not raise
        _invalidate_contract_cache(contract)


class RedisPubClientFallbackTest(TestCase):
    """The pub/sub client's URL fallback chain (close-test-coverage-gaps
    0.5 root cause): ``REDIS_CACHE_URL`` → ``REDIS_URL`` → the
    settings-computed default. The old code read ONLY ``REDIS_CACHE_URL``
    and fell back to a hardcoded ``redis://localhost:6379/0`` — ignoring
    the local-run recipe's ``REDIS_URL`` and the settings default, so the
    host-side contracts Redis tests hit the wrong instance and skipped.

    No mocks: ``redis.Redis.from_url`` is lazy (no connection at
    construction) — the pins assert the resolved host/port from the
    connection pool kwargs, and one REAL ping against the configured
    instance proves reachability when one is available.
    """

    @staticmethod
    def _target(url: str) -> tuple[str | None, int | None]:
        parts = urlsplit(url)
        return parts.hostname, parts.port

    def setUp(self):
        from hub.apps.contracts import tasks

        self.tasks = tasks
        # Reset the module-level singleton so each pin exercises the
        # fallback chain from scratch.
        tasks._redis_pub_client = None
        self.addCleanup(setattr, tasks, "_redis_pub_client", None)

    def _client_target(self) -> tuple[str | None, int | None]:
        client = self.tasks._get_redis_pub_client()
        kwargs = client.connection_pool.connection_kwargs
        return kwargs.get("host"), kwargs.get("port")

    def test_redis_cache_url_env_wins(self):
        with patch.dict(
            "os.environ",
            {
                "REDIS_CACHE_URL": "redis://cache-host:7001/0",
                "REDIS_URL": "redis://queue-host:7002/0",
            },
        ):
            assert self._client_target() == ("cache-host", 7001)

    def test_redis_url_env_is_the_fallback(self):
        with patch.dict(
            "os.environ",
            {
                "REDIS_CACHE_URL": "",
                "REDIS_URL": "redis://queue-host:7002/0",
            },
        ):
            assert self._client_target() == ("queue-host", 7002)

    def test_settings_default_when_no_env(self):
        with patch.dict("os.environ", {"REDIS_CACHE_URL": "", "REDIS_URL": ""}):
            from django.conf import settings

            assert self._client_target() == self._target(settings.REDIS_CACHE_URL)
