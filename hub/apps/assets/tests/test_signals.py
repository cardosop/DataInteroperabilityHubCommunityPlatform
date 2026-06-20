"""
Phase 80.1 — Asset signal tests.

Tests that the post_save signal on Asset enqueues a search vector rebuild
and that failures are logged rather than propagated.

Phase 250.1.F update (closes B2-5): the rebuild is GATED on
``status != DRAFT``. The original Phase 80.1 tests below were rewritten
to seed assets with ``status=AssetStatus.ACTIVE`` so they continue to
exercise the enqueue path. The DRAFT-suppression contract has its own
dedicated suite at ``test_search_vector_signal_timing.py``.
"""

from unittest.mock import patch

import pytest
from django.db.models.signals import post_save
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus


@pytest.mark.django_db(transaction=True)
class AssetSignalTest(TestCase):
    """Tests for hub.apps.assets.signals.rebuild_asset_search_vector."""

    def _create_tenant(self):
        from hub.apps.tenants.models import Tenant

        tenant, _ = Tenant.objects.get_or_create(
            name="signal-test",
            defaults={"slug": "signal-test"},
        )
        return tenant

    def _create_active_asset(self, tenant, name):
        """Phase 250.1.F gate: only non-DRAFT saves enqueue the
        rebuild, so signal-fire tests must seed with ACTIVE."""
        return Asset.objects.create(
            tenant=tenant,
            name=name,
            status=AssetStatus.ACTIVE,
        )

    def test_signal_connected_to_post_save(self):
        """Signal handler is connected to Asset post_save."""
        from hub.apps.assets.signals import rebuild_asset_search_vector

        receivers = [r[1]() for r in post_save.receivers if r[1]() is not None]
        self.assertIn(rebuild_asset_search_vector, receivers)

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_save_enqueues_search_vector_task(self, mock_enqueue):
        """Asset save enqueues a search vector rebuild task."""
        tenant = self._create_tenant()
        with self.captureOnCommitCallbacks(execute=True):
            asset = self._create_active_asset(tenant, "sig-test-asset")
        mock_enqueue.assert_called_with(str(asset.pk))

    @patch(
        "hub.apps.search.tasks.enqueue_asset_search_vector_update",
        side_effect=RuntimeError("RQ unavailable"),
    )
    def test_exception_logged_not_raised(self, _mock_enqueue):
        """Enqueue failure is logged and does not propagate.

        RuntimeError is caught by the second except clause which logs
        ``asset_search_vector_enqueue_redis_or_rq_error``.
        ``assertLogs(level="WARNING")`` captures WARNING and above,
        so it also captures ERROR-level log records when present.
        """
        tenant = self._create_tenant()
        # Should NOT raise
        with self.assertLogs("hub.apps.assets.signals", level="WARNING") as cm:
            with self.captureOnCommitCallbacks(execute=True):
                self._create_active_asset(tenant, "sig-exc-test")
        self.assertTrue(
            any(
                "asset_search_vector_enqueue_redis_or_rq_error" in r
                or "asset_search_vector_enqueue_failed" in r
                for r in cm.output
            ),
            f"Expected enqueue error in log; got {cm.output}",
        )

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_update_triggers_signal(self, mock_enqueue):
        """Updating an existing asset also triggers the signal."""
        tenant = self._create_tenant()
        with self.captureOnCommitCallbacks(execute=True):
            asset = self._create_active_asset(tenant, "sig-update")
        mock_enqueue.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            asset.name = "sig-update-v2"
            asset.save(update_fields=["name", "updated_at"])
        mock_enqueue.assert_called_with(str(asset.pk))

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_created_and_updated_both_fire(self, mock_enqueue):
        """Signal fires on both create and update for non-DRAFT
        assets (Phase 250.1.F gates DRAFT but does not narrow the
        non-DRAFT contract)."""
        tenant = self._create_tenant()
        with self.captureOnCommitCallbacks(execute=True):
            asset = self._create_active_asset(tenant, "sig-both")
        self.assertGreaterEqual(
            mock_enqueue.call_count, 1, "ACTIVE asset create must enqueue a search vector rebuild"
        )
        mock_enqueue.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            asset.name = "sig-both-v2"
            asset.save()
        self.assertGreaterEqual(
            mock_enqueue.call_count, 1, "ACTIVE asset update must enqueue a search vector rebuild"
        )
