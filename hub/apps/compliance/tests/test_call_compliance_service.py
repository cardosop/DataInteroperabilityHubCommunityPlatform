"""
Tests for ComplianceService._call_compliance_service() dispatch logic.

Validates the async (202), sync (200), and fallback paths using mocked
ComplianceServiceClient. Real DB objects are used for ComplianceRun.
"""
import uuid

import pytest
from django.test import TestCase, override_settings
from django.utils import timezone
from unittest.mock import patch, MagicMock

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.compliance.services import ComplianceService
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

from django.contrib.auth import get_user_model

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class CallComplianceServiceTest(TestCase):
    """Tests for ComplianceService._call_compliance_service()"""

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
            status=ComplianceRunStatus.RUNNING,
            started_at=timezone.now(),
        )
        defaults.update(overrides)
        return ComplianceRun.objects.create(**defaults)

    def _call_kwargs(self, run, **overrides):
        """Default kwargs for _call_compliance_service."""
        defaults = dict(
            compliance_run=run,
            file_content=b"col1,col2\nval1,val2\n",
            file_format="csv",
            scan_mode="internal",
            applicable_regulations=["GDPR"],
            legal_basis="CONSENT",
            destination_jurisdiction="EU",
            tenant_id=str(self.tenant.id),
            correlation_id=str(run.id),
        )
        defaults.update(overrides)
        return defaults

    # ----------------------------------------------------------------
    # 1. Async 202 sets QUEUED and stores metadata
    # ----------------------------------------------------------------

    @patch("hub.apps.compliance.service_client.ComplianceServiceClient")
    @patch("hub.apps.compliance.tasks.poll_compliance_job")
    def test_async_202_sets_queued(self, mock_poll, MockClient):
        """202 response sets run.status=QUEUED and stores job_id in metadata."""
        client_instance = MockClient.return_value
        client_instance.scan_file_async.return_value = {
            "_http_status": 202,
            "job_id": "abc-123",
            "poll_url": "/poll/abc-123",
        }

        run = self._create_run()

        # Mock django_rq.get_queue to avoid real Redis dependency
        with patch("django_rq.get_queue") as mock_get_q:
            mock_queue = MagicMock()
            mock_get_q.return_value = mock_queue
            ComplianceService._call_compliance_service(**self._call_kwargs(run))

        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.QUEUED)
        self.assertEqual(run.metadata_json["job_id"], "abc-123")
        self.assertEqual(run.metadata_json["poll_url"], "/poll/abc-123")

    # ----------------------------------------------------------------
    # 2. Sync 200 persists result directly
    # ----------------------------------------------------------------

    @patch("hub.apps.compliance.service_client.ComplianceServiceClient")
    @patch.object(ComplianceService, "_persist_result")
    def test_sync_200_persists_result(self, mock_persist, MockClient):
        """200 response calls _persist_result and run reaches SUCCEEDED."""
        sync_result = {
            "_http_status": 200,
            "overall_status": "PASS",
            "risk_level": "LOW",
            "allowed_to_store": True,
            "detected_categories": [],
            "column_findings": [],
            "applicable_regulations": ["GDPR"],
        }
        client_instance = MockClient.return_value
        client_instance.scan_file_async.return_value = sync_result

        run = self._create_run()
        ComplianceService._call_compliance_service(**self._call_kwargs(run))

        mock_persist.assert_called_once()
        call_args = mock_persist.call_args
        self.assertEqual(call_args[0][0], run)
        # The _http_status key is popped before passing to persist
        self.assertNotIn("_http_status", call_args[0][1])

    # ----------------------------------------------------------------
    # 3. Async exception falls back to sync
    # ----------------------------------------------------------------

    @patch("hub.apps.compliance.service_client.ComplianceServiceClient")
    @patch.object(ComplianceService, "_persist_result")
    def test_async_exception_falls_back_to_sync(self, mock_persist, MockClient):
        """When scan_file_async raises, falls back to scan_file (sync)."""
        client_instance = MockClient.return_value
        client_instance.scan_file_async.side_effect = ConnectionError("service down")
        client_instance.scan_file.return_value = {
            "overall_status": "PASS",
            "risk_level": "LOW",
            "allowed_to_store": True,
        }

        run = self._create_run()
        ComplianceService._call_compliance_service(**self._call_kwargs(run))

        client_instance.scan_file.assert_called_once()
        mock_persist.assert_called_once()

    # ----------------------------------------------------------------
    # 4. legal_basis forwarded in sync fallback
    # ----------------------------------------------------------------

    @patch("hub.apps.compliance.service_client.ComplianceServiceClient")
    @patch.object(ComplianceService, "_persist_result")
    def test_legal_basis_forwarded_in_sync_fallback(self, mock_persist, MockClient):
        """Verify scan_file receives legal_basis when falling back to sync."""
        client_instance = MockClient.return_value
        client_instance.scan_file_async.side_effect = ConnectionError("timeout")
        client_instance.scan_file.return_value = {"overall_status": "PASS"}

        run = self._create_run()
        ComplianceService._call_compliance_service(
            **self._call_kwargs(run, legal_basis="LEGITIMATE_INTEREST")
        )

        call_kwargs = client_instance.scan_file.call_args
        self.assertEqual(call_kwargs.kwargs.get("legal_basis"), "LEGITIMATE_INTEREST")

    # ----------------------------------------------------------------
    # 5. applicable_regulations forwarded to async endpoint
    # ----------------------------------------------------------------

    @patch("hub.apps.compliance.service_client.ComplianceServiceClient")
    def test_applicable_regulations_forwarded(self, MockClient):
        """applicable_regulations passed through to scan_file_async."""
        client_instance = MockClient.return_value
        client_instance.scan_file_async.return_value = {
            "_http_status": 200,
            "overall_status": "PASS",
        }

        run = self._create_run()

        with patch.object(ComplianceService, "_persist_result"):
            ComplianceService._call_compliance_service(
                **self._call_kwargs(run, applicable_regulations=["GDPR", "LGPD"])
            )

        call_kwargs = client_instance.scan_file_async.call_args
        self.assertEqual(
            call_kwargs.kwargs.get("applicable_regulations"), ["GDPR", "LGPD"]
        )
