"""
Phase 80.4 — Integrations signal tests.

Tests that WorkflowInstance post_save syncs status to MarketplaceSyncJob
for marketplace_sync workflows.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.db.models.signals import post_save
from django.test import TestCase


@pytest.mark.django_db(transaction=True)
class IntegrationsSignalTest(TestCase):
    """Tests for sync_workflow_status_to_sync_job signal."""

    def test_signal_connected_to_post_save(self):
        """Signal handler is connected to WorkflowInstance post_save."""
        import hub.apps.integrations.signals  # noqa: F401 — ensures signal module is loaded
        from hub.apps.orchestration.models import WorkflowInstance

        # Use Django's has_listeners to verify signal is connected for WorkflowInstance
        self.assertTrue(
            post_save.has_listeners(sender=WorkflowInstance),
            "post_save should have listeners for WorkflowInstance",
        )

        # Verify our specific handler is among the connected receivers
        import weakref

        handler_names = []
        for receiver_entry in post_save.receivers:
            # Django stores receivers as (dispatch_uid_key, weakref_or_func)
            ref = receiver_entry[1]
            # Only dereference actual weakrefs; regular functions must not be called
            if isinstance(ref, weakref.ReferenceType):
                handler = ref()
            else:
                handler = ref
            if handler is not None:
                name = getattr(handler, "__name__", "") or getattr(handler, "__qualname__", "")
                if name:
                    handler_names.append(name)
        assert "sync_workflow_status_to_sync_job" in handler_names, (
            f"sync_workflow_status_to_sync_job not found in handlers: {handler_names}"
        )

    def test_created_instance_skipped(self):
        """Signal does nothing on creation (only updates)."""
        from hub.apps.integrations.models import MarketplaceSyncJob
        from hub.apps.integrations.signals import (
            sync_workflow_status_to_sync_job,
        )
        from hub.apps.orchestration.models import WorkflowInstance

        instance = MagicMock(spec=WorkflowInstance)
        instance.workflow_name = "marketplace_sync_push"

        with patch.object(MarketplaceSyncJob.objects, "get") as mock_get:
            sync_workflow_status_to_sync_job(
                sender=WorkflowInstance,
                instance=instance,
                created=True,
            )
            mock_get.assert_not_called()

    def test_non_marketplace_workflow_skipped(self):
        """Signal skips non-marketplace workflows."""
        from hub.apps.integrations.models import MarketplaceSyncJob
        from hub.apps.integrations.signals import (
            sync_workflow_status_to_sync_job,
        )
        from hub.apps.orchestration.models import WorkflowInstance

        instance = MagicMock(spec=WorkflowInstance)
        instance.workflow_name = "dq_run_workflow"

        with patch.object(MarketplaceSyncJob.objects, "get") as mock_get:
            sync_workflow_status_to_sync_job(
                sender=WorkflowInstance,
                instance=instance,
                created=False,
            )
            mock_get.assert_not_called()

    def test_missing_sync_job_id_skipped(self):
        """Signal returns early when state_data has no sync_job_id."""
        from hub.apps.integrations.models import MarketplaceSyncJob
        from hub.apps.integrations.signals import (
            sync_workflow_status_to_sync_job,
        )
        from hub.apps.orchestration.models import WorkflowInstance

        instance = MagicMock(spec=WorkflowInstance)
        instance.workflow_name = "marketplace_sync_pull"
        instance.state_data = {}

        with patch.object(MarketplaceSyncJob.objects, "get") as mock_get:
            sync_workflow_status_to_sync_job(
                sender=WorkflowInstance,
                instance=instance,
                created=False,
            )
            mock_get.assert_not_called()

    @patch("hub.apps.integrations.services.MarketplaceIntegrationService")
    def test_marketplace_sync_calls_service(self, mock_svc_cls):
        """Marketplace sync update triggers service call."""
        from hub.apps.integrations.models import MarketplaceSyncJob
        from hub.apps.integrations.signals import (
            sync_workflow_status_to_sync_job,
        )
        from hub.apps.orchestration.models import WorkflowInstance

        sync_job_id = str(uuid.uuid4())
        instance = MagicMock(spec=WorkflowInstance)
        instance.workflow_name = "marketplace_sync_push"
        instance.state_data = {"sync_job_id": sync_job_id}
        instance.tenant_id = uuid.uuid4()
        instance.id = uuid.uuid4()
        instance.status = "COMPLETED"

        with patch.object(
            MarketplaceSyncJob.objects,
            "get",
            return_value=MagicMock(spec=MarketplaceSyncJob),
        ):
            sync_workflow_status_to_sync_job(
                sender=WorkflowInstance,
                instance=instance,
                created=False,
            )
        mock_svc_cls.assert_called_with(
            tenant_id=str(instance.tenant_id),
        )
        # Verify the service method was actually called
        mock_svc_instance = mock_svc_cls.return_value
        mock_svc_instance.sync_workflow_status_to_sync_job.assert_called_once()

    def test_exception_logged_not_raised(self):
        """Service failure is logged and does not propagate."""
        from hub.apps.integrations.models import MarketplaceSyncJob
        from hub.apps.integrations.signals import (
            sync_workflow_status_to_sync_job,
        )
        from hub.apps.orchestration.models import WorkflowInstance

        instance = MagicMock(spec=WorkflowInstance)
        instance.workflow_name = "marketplace_sync_push"
        instance.state_data = {
            "sync_job_id": str(uuid.uuid4()),
        }
        instance.id = uuid.uuid4()

        with patch.object(
            MarketplaceSyncJob.objects,
            "get",
            side_effect=Exception("DB error"),
        ):
            # Should NOT raise
            sync_workflow_status_to_sync_job(
                sender=WorkflowInstance,
                instance=instance,
                created=False,
            )
