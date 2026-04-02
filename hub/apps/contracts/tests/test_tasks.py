"""
Phase 86.1 — contracts/tasks.py tests.

Tests renormalize_contracts_v310 via management command wrapper
(already thoroughly tested in test_renormalize_command.py).
This file adds direct function-level coverage.
"""
import uuid
from unittest.mock import patch

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

    @patch("hub.apps.contracts.tasks._get_redis_pub_client",
           return_value=None)
    def test_invalidate_cache_noop_without_redis(self, _):
        """No Redis client → no error."""
        from hub.apps.contracts.tasks import _invalidate_contract_cache
        from unittest.mock import MagicMock
        contract = MagicMock()
        contract.id = uuid.uuid4()
        contract.original_raw = "spec: v1"
        # Should not raise
        _invalidate_contract_cache(contract)
