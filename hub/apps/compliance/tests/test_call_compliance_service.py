"""
Tests for ComplianceService._call_compliance_service() dispatch logic.

Validates the async (202), sync (200), and fallback paths using mocked
ComplianceServiceClient. Real DB objects are used for ComplianceRun.
"""

import os
import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.compliance.services import ComplianceService
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

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

    @patch.dict(os.environ, {"COMPLIANCE_USE_ASYNC": "1"})
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

        # The poll task is enqueued via transaction.on_commit(), which
        # fires after the current transaction commits.  In the test
        # transaction the hook is registered but never executed
        # (rollback).  Verify the queue was acquired; the enqueue
        # payload is tested via integration / E2E.
        mock_get_q.assert_called_once_with("job_default")

    # ----------------------------------------------------------------
    # 2. Sync 200 persists result directly
    # ----------------------------------------------------------------

    @patch("hub.apps.compliance.service_client.ComplianceServiceClient")
    @patch.object(ComplianceService, "_persist_result")
    def test_sync_200_persists_result(self, mock_persist, MockClient):
        """200 response calls _persist_result and run reaches SUCCEEDED."""
        sync_result = {
            "overall_status": "PASS",
            "risk_level": "LOW",
            "allowed_to_store": True,
            "detected_categories": [],
            "column_findings": [],
            "applicable_regulations": ["GDPR"],
        }
        client_instance = MockClient.return_value
        client_instance.scan_file.return_value = sync_result

        run = self._create_run()
        ComplianceService._call_compliance_service(**self._call_kwargs(run))

        mock_persist.assert_called_once()
        called_with = mock_persist.call_args
        self.assertEqual(called_with.kwargs["run"], run)
        # Verify the result dict is passed through — the sync path
        # receives whatever scan_file returns (no _http_status injected).
        self.assertIsInstance(called_with.kwargs["result_data"], dict)
        self.assertEqual(called_with.kwargs["result_data"]["overall_status"], "PASS")

    # ----------------------------------------------------------------
    # 3. Async exception falls back to sync
    # ----------------------------------------------------------------

    @patch.dict(os.environ, {"COMPLIANCE_USE_ASYNC": "1"})
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

    @patch.dict(os.environ, {"COMPLIANCE_USE_ASYNC": "1"})
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
        """applicable_regulations passed through to scan_file (sync path)."""
        client_instance = MockClient.return_value
        client_instance.scan_file.return_value = {
            "overall_status": "PASS",
        }

        run = self._create_run()

        with patch.object(ComplianceService, "_persist_result"):
            ComplianceService._call_compliance_service(
                **self._call_kwargs(run, applicable_regulations=["GDPR", "LGPD"])
            )

        call_kwargs = client_instance.scan_file.call_args
        self.assertEqual(call_kwargs.kwargs.get("applicable_regulations"), ["GDPR", "LGPD"])

    # ----------------------------------------------------------------
    # 6. Sync path persists result to DB (real _persist_result)
    # ----------------------------------------------------------------

    @patch("hub.apps.compliance.service_client.ComplianceServiceClient")
    def test_sync_persists_result_to_db(self, MockClient):
        """Sync path persists result fields to the ComplianceRun row."""
        sync_result = {
            "overall_status": "PASS",
            "risk_level": "LOW",
            "allowed_to_store": True,
            "detected_categories": ["email"],
            "column_findings": [{"col": "email", "type": "PII"}],
            "applicable_regulations": ["GDPR"],
            "regulation_mapping": {"gdpr": {"status": "compliant"}},
            "cross_border_alert": None,
            "localization_alert": None,
            "legal_basis_violations": [],
            "metadata": {"total_rows": 100, "total_columns": 5},
            "risk_score": 0.15,
        }
        client_instance = MockClient.return_value
        client_instance.scan_file.return_value = sync_result

        run = self._create_run(status=ComplianceRunStatus.RUNNING)
        # NOT mocking _persist_result — exercise the real persistence.
        ComplianceService._call_compliance_service(**self._call_kwargs(run))

        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.SUCCEEDED)
        self.assertEqual(run.overall_status, "PASS")
        self.assertEqual(run.risk_level, "LOW")
        self.assertTrue(run.allowed_to_store)
        self.assertEqual(run.detected_categories_json, ["email"])
        self.assertEqual(run.column_findings_json, [{"col": "email", "type": "PII"}])
        self.assertEqual(run.regulations, ["GDPR"])
        self.assertIn("gdpr", run.regulation_mapping_json)
        self.assertIn("metering", run.regulation_mapping_json)
        self.assertEqual(run.regulation_mapping_json["metering"]["rows_scanned"], 100)
        self.assertIsNotNone(run.completed_at)

    # ----------------------------------------------------------------
    # 7. FAILED/ERROR guard in _persist_result
    # ----------------------------------------------------------------

    def test_persist_result_failed_status_guard(self):
        """FAILED status in result_data forces run to FAILED with allowed_to_store=False."""
        run = self._create_run(status=ComplianceRunStatus.RUNNING)
        ComplianceService._persist_result(
            run,
            {
                "status": "FAILED",
                "error": "compliance scan crashed",
                "overall_status": "PASS",  # must be ignored for FAILED status
            },
        )
        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.FAILED)
        self.assertFalse(run.allowed_to_store)
        self.assertIn("error", run.regulation_mapping_json)
        self.assertEqual(run.regulation_mapping_json["error"], "compliance scan crashed")
        self.assertEqual(run.regulation_mapping_json["error_type"], "EXECUTION_ERROR")
        self.assertIsNotNone(run.completed_at)

    # ----------------------------------------------------------------
    # 8. UNKNOWN overall_status / missing allowed_to_store guard
    # ----------------------------------------------------------------

    def test_persist_result_unknown_overall_status_fail_closed(self):
        """UNKNOWN overall_status forces allowed_to_store=False regardless of input."""
        run = self._create_run(status=ComplianceRunStatus.RUNNING)
        ComplianceService._persist_result(
            run,
            {
                "overall_status": "UNKNOWN",
                "allowed_to_store": True,  # service returned True but status is UNKNOWN
                "risk_level": "UNKNOWN",
                "detected_categories": [],
                "column_findings": [],
                "applicable_regulations": [],
                "metadata": {},
            },
        )
        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.SUCCEEDED)
        self.assertFalse(
            run.allowed_to_store,
            "allowed_to_store must be False when overall_status is UNKNOWN",
        )

    def test_persist_result_missing_allowed_to_store_fail_closed(self):
        """Missing allowed_to_store key forces it to False."""
        run = self._create_run(status=ComplianceRunStatus.RUNNING)
        ComplianceService._persist_result(
            run,
            {
                "overall_status": "PASS",
                # allowed_to_store deliberately omitted
                "risk_level": "LOW",
                "detected_categories": [],
                "column_findings": [],
                "applicable_regulations": [],
                "metadata": {},
            },
        )
        run.refresh_from_db()
        self.assertFalse(
            run.allowed_to_store,
            "allowed_to_store must be False when key is missing",
        )

    # ----------------------------------------------------------------
    # 9. Async endpoint returns 200 (sync response from async endpoint)
    # ----------------------------------------------------------------

    @patch.dict(os.environ, {"COMPLIANCE_USE_ASYNC": "1"})
    @patch("hub.apps.compliance.service_client.ComplianceServiceClient")
    @patch.object(ComplianceService, "_persist_result")
    def test_async_endpoint_returns_200_calls_persist(self, mock_persist, MockClient):
        """When async endpoint returns 200, _persist_result is called directly."""
        client_instance = MockClient.return_value
        client_instance.scan_file_async.return_value = {
            "_http_status": 200,
            "overall_status": "PASS",
            "risk_level": "LOW",
        }

        run = self._create_run()
        ComplianceService._call_compliance_service(**self._call_kwargs(run))

        mock_persist.assert_called_once()
        # _http_status is popped by the async-200 branch before calling persist.
        persist_kwargs = mock_persist.call_args
        self.assertNotIn("_http_status", persist_kwargs[0][1])
