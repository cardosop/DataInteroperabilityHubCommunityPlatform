"""
Tests for the execute_dq_run() function.

Mocks the DQServiceClient (HTTP layer only) and S3StorageClient to verify
that execute_dq_run correctly persists results, clamps scores, updates asset
DQ status, and handles errors with fail-closed semantics.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.assets.models import DQStatus as AssetDQStatus
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.dq.tests.test_base import DQTestBase
from hub.apps.dq.views import execute_dq_run
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.jobs.utils import create_job
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TestExecuteDQRunDetailed(DQTestBase):
    """Tests for execute_dq_run() function internals."""

    def setUp(self):
        super().setUp()
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def _create_dq_run(self, **overrides):
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={},
            timeout_seconds=300,
            executed_by_prefect=True,
        )
        defaults = {
            "tenant": self.tenant,
            "asset": self.asset,
            "file": self.file,
            "job": job,
            "status": DQRunStatus.PENDING,
            "profile_key": "intake_basic_gx",
            "engine": DQEngine.GREAT_EXPECTATIONS,
        }
        defaults.update(overrides)
        return DQRun.objects.create(**defaults)

    def _mock_dq_result(self, **overrides):
        """Build a mock DQ service result dict."""
        result = {
            "overall_status": "PASS",
            "quality_score": 95.0,
            "checks": [
                {"name": "null_check", "status": "PASS", "category": "COMPLETENESS"},
            ],
            "engine_type": "GX",
            "engine_version": "0.18.0",
            "profile_key": "intake_basic_gx",
            "metadata": {"total_rows": 100, "total_columns": 5},
        }
        result.update(overrides)
        return result

    # ------------------------------------------------------------------
    # 1. Successful run persists all fields
    # ------------------------------------------------------------------
    @patch("hub.apps.files.storage.S3StorageClient")
    @patch("hub.apps.dq.views.DQServiceClient")
    def test_successful_run_persists_all_fields(self, MockClient, MockStorage):
        MockStorage.return_value.download_file.return_value = b"col1,col2\n1,2\n"
        mock_result = self._mock_dq_result()
        MockClient.return_value.run_dq.return_value = mock_result

        run = self._create_dq_run()
        execute_dq_run(str(run.id))

        run.refresh_from_db()
        self.assertEqual(run.status, DQRunStatus.SUCCEEDED)
        self.assertEqual(run.overall_status, "PASS")
        self.assertEqual(run.quality_score, 95.0)
        self.assertIsInstance(run.checks_json, list)
        self.assertEqual(len(run.checks_json), 1)
        self.assertIn("metering", run.details_json)
        self.assertIsNotNone(run.completed_at)

    # ------------------------------------------------------------------
    # 2. Asset DQ status set to PASS on success
    # ------------------------------------------------------------------
    @patch("hub.apps.files.storage.S3StorageClient")
    @patch("hub.apps.dq.views.DQServiceClient")
    def test_asset_dq_status_updated_pass(self, MockClient, MockStorage):
        MockStorage.return_value.download_file.return_value = b"col1\n1\n"
        MockClient.return_value.run_dq.return_value = self._mock_dq_result(
            overall_status="PASS"
        )

        run = self._create_dq_run()
        execute_dq_run(str(run.id))

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.dq_status, AssetDQStatus.PASS)

    # ------------------------------------------------------------------
    # 3. Asset DQ status set to FAIL
    # ------------------------------------------------------------------
    @patch("hub.apps.files.storage.S3StorageClient")
    @patch("hub.apps.dq.views.DQServiceClient")
    def test_asset_dq_status_updated_fail(self, MockClient, MockStorage):
        MockStorage.return_value.download_file.return_value = b"col1\n1\n"
        MockClient.return_value.run_dq.return_value = self._mock_dq_result(
            overall_status="FAIL", quality_score=20.0
        )

        run = self._create_dq_run()
        execute_dq_run(str(run.id))

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.dq_status, AssetDQStatus.FAIL)

    # ------------------------------------------------------------------
    # 4. quality_score > 100 is clamped to 100.0
    # ------------------------------------------------------------------
    @patch("hub.apps.files.storage.S3StorageClient")
    @patch("hub.apps.dq.views.DQServiceClient")
    def test_quality_score_clamped(self, MockClient, MockStorage):
        MockStorage.return_value.download_file.return_value = b"col1\n1\n"
        MockClient.return_value.run_dq.return_value = self._mock_dq_result(
            quality_score=150
        )

        run = self._create_dq_run()
        execute_dq_run(str(run.id))

        run.refresh_from_db()
        self.assertEqual(run.quality_score, 100.0)

    # ------------------------------------------------------------------
    # 5. quality_score < 0 is clamped to 0.0
    # ------------------------------------------------------------------
    @patch("hub.apps.files.storage.S3StorageClient")
    @patch("hub.apps.dq.views.DQServiceClient")
    def test_quality_score_negative_clamped(self, MockClient, MockStorage):
        MockStorage.return_value.download_file.return_value = b"col1\n1\n"
        MockClient.return_value.run_dq.return_value = self._mock_dq_result(
            quality_score=-10
        )

        run = self._create_dq_run()
        execute_dq_run(str(run.id))

        run.refresh_from_db()
        self.assertEqual(run.quality_score, 0.0)

    # ------------------------------------------------------------------
    # 6. Exception → fail-closed: FAILED + UNKNOWN + asset.dq_status=UNKNOWN
    # ------------------------------------------------------------------
    @patch("hub.apps.files.storage.S3StorageClient")
    @patch("hub.apps.dq.views.DQServiceClient")
    def test_error_sets_fail_closed(self, MockClient, MockStorage):
        MockStorage.return_value.download_file.return_value = b"col1\n1\n"
        MockClient.return_value.run_dq.side_effect = RuntimeError("service down")

        run = self._create_dq_run()
        execute_dq_run(str(run.id))

        run.refresh_from_db()
        self.assertEqual(run.status, DQRunStatus.FAILED)
        self.assertEqual(run.overall_status, "UNKNOWN")
        self.assertIn("fail_closed", run.details_json)

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.dq_status, AssetDQStatus.UNKNOWN)

    # ------------------------------------------------------------------
    # 7. Deadline exceeded → FAILED + UNKNOWN
    # ------------------------------------------------------------------
    @override_settings(DQ_POLL_MAX_SECONDS=0)
    @patch("hub.apps.files.storage.S3StorageClient")
    @patch("hub.apps.dq.views.DQServiceClient")
    def test_timeout_sets_fail_closed(self, MockClient, MockStorage):
        MockStorage.return_value.download_file.return_value = b"col1\n1\n"
        MockClient.return_value.run_dq.return_value = self._mock_dq_result()

        run = self._create_dq_run()
        execute_dq_run(str(run.id))

        run.refresh_from_db()
        self.assertEqual(run.status, DQRunStatus.FAILED)
        self.assertEqual(run.overall_status, "UNKNOWN")

    # ------------------------------------------------------------------
    # 8. No file/dataset → FAILED
    # ------------------------------------------------------------------
    @patch("hub.apps.files.storage.S3StorageClient")
    @patch("hub.apps.dq.views.DQServiceClient")
    def test_no_file_raises_error(self, MockClient, MockStorage):
        """DQRun with no file, dataset, or asset-with-dataset → FAILED."""
        # Create asset without any datasets
        bare_asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"bare-asset-{uuid.uuid4().hex[:8]}",
            name="Bare Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        run = self._create_dq_run(asset=bare_asset, file=None)
        execute_dq_run(str(run.id))

        run.refresh_from_db()
        self.assertEqual(run.status, DQRunStatus.FAILED)
        self.assertIn("error", run.details_json)
