"""
Tests for poll_compliance_job task in tasks.py.

Validates terminal-status short-circuit, missing job_id handling,
timeout fail-closed behavior, result persistence on COMPLETED,
failure marking on FAILED, and re-enqueue on RUNNING.
"""

import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.compliance.tasks import poll_compliance_job
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class PollTaskBehaviorTest(TestCase):
    """Tests for poll_compliance_job task."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uid}",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

    def _create_job(self, **overrides):
        defaults = dict(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={"scan_mode": "internal"},
            timeout_seconds=300,
            executed_by_prefect=True,
        )
        defaults.update(overrides)
        return create_job(**defaults)

    def _create_run(self, **overrides):
        defaults = dict(
            tenant=self.tenant,
            asset=self.asset,
            job=self._create_job(),
            status=ComplianceRunStatus.QUEUED,
            metadata_json={"job_id": "remote-job-1", "poll_url": "/poll/1"},
            started_at=timezone.now(),
        )
        defaults.update(overrides)
        return ComplianceRun.objects.create(**defaults)

    # ----------------------------------------------------------------
    # 1. Terminal status skips polling
    # ----------------------------------------------------------------

    @patch("hub.apps.compliance.service_client.ComplianceServiceClient")
    def test_terminal_status_skips(self, MockClient):
        """A run already SUCCEEDED is skipped — no client call."""
        run = self._create_run(status=ComplianceRunStatus.SUCCEEDED)
        poll_compliance_job(run.id)
        MockClient.assert_not_called()

    # ----------------------------------------------------------------
    # 2. Missing job_id marks run FAILED
    # ----------------------------------------------------------------

    @patch("hub.apps.compliance.service_client.ComplianceServiceClient")
    def test_missing_job_id_marks_failed(self, MockClient):
        """Empty metadata_json (no job_id) marks run as FAILED."""
        run = self._create_run(metadata_json={})
        poll_compliance_job(run.id)

        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.FAILED)
        MockClient.assert_not_called()

    @patch("hub.apps.compliance.service_client.ComplianceServiceClient")
    def test_missing_job_id_with_none_metadata_marks_failed(self, MockClient):
        """metadata_json=None (not just {}) also marks run as FAILED."""
        run = self._create_run(metadata_json=None)
        poll_compliance_job(run.id)

        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.FAILED)
        MockClient.assert_not_called()

    # ----------------------------------------------------------------
    # 3. Timeout marks FAILED with fail-closed fields
    # ----------------------------------------------------------------

    @override_settings(COMPLIANCE_POLL_MAX_SECONDS=0)
    @patch("hub.apps.compliance.service_client.ComplianceServiceClient")
    def test_timeout_marks_failed_fail_closed(self, MockClient):
        """Elapsed > max_seconds -> FAILED, allowed_to_store=False, risk_level=UNKNOWN."""
        # started_at in the past to ensure elapsed > 0
        run = self._create_run(
            started_at=timezone.now() - timedelta(seconds=60),
        )
        poll_compliance_job(run.id)

        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.FAILED)
        self.assertFalse(run.allowed_to_store)
        self.assertEqual(run.risk_level, "UNKNOWN")
        MockClient.assert_not_called()

    # ----------------------------------------------------------------
    # 4. COMPLETED result persists via _persist_result
    # ----------------------------------------------------------------

    @patch("hub.apps.compliance.service_client.ComplianceServiceClient")
    @patch("hub.apps.compliance.services.ComplianceService._persist_result")
    def test_completed_result_persists(self, mock_persist, MockClient):
        """Remote status COMPLETED calls _persist_result with result payload."""
        client_instance = MockClient.return_value
        client_instance.get_scan_result.return_value = {
            "status": "COMPLETED",
            "result": {
                "overall_status": "PASS",
                "risk_level": "LOW",
                "allowed_to_store": True,
            },
        }

        run = self._create_run()
        poll_compliance_job(run.id)

        mock_persist.assert_called_once()
        # The result payload is unwrapped from the "result" key
        persisted_data = mock_persist.call_args[0][1]
        self.assertEqual(persisted_data["overall_status"], "PASS")

    # ----------------------------------------------------------------
    # 5. Remote FAILED marks run as FAILED
    # ----------------------------------------------------------------

    @patch("hub.apps.compliance.service_client.ComplianceServiceClient")
    def test_failed_remote_marks_failed(self, MockClient):
        """Remote status FAILED sets run.status=FAILED."""
        client_instance = MockClient.return_value
        client_instance.get_scan_result.return_value = {
            "status": "FAILED",
            "error": "Internal scanner error",
        }

        run = self._create_run()
        poll_compliance_job(run.id)

        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.FAILED)
        # Phase 213.G.6 — error detail must be persisted so API
        # consumers can surface it (not just logged and thrown away).
        self.assertEqual(
            run.regulation_mapping_json["error_type"], "REMOTE_FAILURE",
        )
        self.assertEqual(
            run.regulation_mapping_json["error"], "Internal scanner error",
        )

    # ----------------------------------------------------------------
    # 6. RUNNING re-enqueues the task
    # ----------------------------------------------------------------

    @patch("hub.apps.compliance.tasks._reenqueue")
    @patch("hub.apps.compliance.service_client.ComplianceServiceClient")
    def test_running_reenqueues(self, MockClient, mock_reenqueue):
        """Remote status RUNNING triggers re-enqueue."""
        client_instance = MockClient.return_value
        client_instance.get_scan_result.return_value = {
            "status": "RUNNING",
        }

        run = self._create_run()
        poll_compliance_job(run.id)

        mock_reenqueue.assert_called_once_with(run.id)
