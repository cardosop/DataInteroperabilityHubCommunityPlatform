"""
Phase 80.1 — Asset signal tests.

Tests that the post_save signal on Asset enqueues a search vector rebuild
and that failures are logged rather than propagated.
"""
from unittest.mock import patch, MagicMock

import pytest
from django.db.models.signals import post_save
from django.test import TestCase

from hub.apps.assets.models import Asset


@pytest.mark.django_db(transaction=True)
class AssetSignalTest(TestCase):
    """Tests for hub.apps.assets.signals.rebuild_asset_search_vector."""

    def _create_tenant(self):
        from hub.apps.tenants.models import Tenant
        tenant, _ = Tenant.objects.get_or_create(
            name="signal-test", defaults={"slug": "signal-test"},
        )
        return tenant

    def test_signal_connected_to_post_save(self):
        """Signal handler is connected to Asset post_save."""
        from hub.apps.assets.signals import rebuild_asset_search_vector
        receivers = [r[1]() for r in post_save.receivers if r[1]() is not None]
        assert rebuild_asset_search_vector in receivers

    @patch("hub.apps.assets.signals.logger")
    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_save_enqueues_search_vector_task(self, mock_enqueue, _mock_logger):
        """Asset save enqueues a search vector rebuild task."""
        tenant = self._create_tenant()
        with self.captureOnCommitCallbacks(execute=True):
            asset = Asset.objects.create(tenant=tenant, name="sig-test-asset")
        mock_enqueue.assert_called_with(str(asset.pk))

    @patch("hub.apps.assets.signals.logger")
    @patch(
        "hub.apps.search.tasks.enqueue_asset_search_vector_update",
        side_effect=RuntimeError("RQ unavailable"),
    )
    def test_exception_logged_not_raised(self, _mock_enqueue, mock_logger):
        """Enqueue failure is logged at WARNING and does not propagate."""
        tenant = self._create_tenant()
        # Should NOT raise
        with self.captureOnCommitCallbacks(execute=True):
            Asset.objects.create(tenant=tenant, name="sig-exc-test")
        mock_logger.warning.assert_called_once()
        assert "asset_search_vector_enqueue_failed" in str(mock_logger.warning.call_args)

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_update_triggers_signal(self, mock_enqueue):
        """Updating an existing asset also triggers the signal."""
        tenant = self._create_tenant()
        with self.captureOnCommitCallbacks(execute=True):
            asset = Asset.objects.create(tenant=tenant, name="sig-update")
        mock_enqueue.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            asset.name = "sig-update-v2"
            asset.save(update_fields=["name", "updated_at"])
        mock_enqueue.assert_called_with(str(asset.pk))

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_created_and_updated_both_fire(self, mock_enqueue):
        """Signal fires on both create and update (no created-only guard)."""
        tenant = self._create_tenant()
        with self.captureOnCommitCallbacks(execute=True):
            asset = Asset.objects.create(tenant=tenant, name="sig-both")
        assert mock_enqueue.call_count >= 1
        mock_enqueue.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            asset.name = "sig-both-v2"
            asset.save()
        assert mock_enqueue.call_count >= 1
