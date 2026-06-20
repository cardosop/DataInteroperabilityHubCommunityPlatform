"""
Tests for the execute_dq_run() function.

Mocks the DQServiceClient (HTTP layer only) and S3StorageClient to verify
that execute_dq_run correctly persists results, clamps scores, updates asset
DQ status, and handles errors with fail-closed semantics.
"""

import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.assets.models import DQStatus as AssetDQStatus
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.dq.tests.test_base import DQTestBase
from hub.apps.dq.views import execute_dq_run
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job

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
        mock_client_instance = MockClient.return_value
        mock_client_instance.run_dq.return_value = mock_result

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

        # M5: verify run_dq was called with the correct arguments.
        mock_client_instance.run_dq.assert_called_once()
        call_kwargs = mock_client_instance.run_dq.call_args.kwargs
        self.assertEqual(call_kwargs["file_format"], "csv")
        self.assertEqual(call_kwargs["profile_key"], "intake_basic_gx")
        self.assertIn("file_content", call_kwargs)
        self.assertIn("tenant_id", call_kwargs)

    # ------------------------------------------------------------------
    # 2. Asset DQ status set to PASS on success
    # ------------------------------------------------------------------
    @patch("hub.apps.files.storage.S3StorageClient")
    @patch("hub.apps.dq.views.DQServiceClient")
    def test_asset_dq_status_updated_pass(self, MockClient, MockStorage):
        MockStorage.return_value.download_file.return_value = b"col1\n1\n"
        MockClient.return_value.run_dq.return_value = self._mock_dq_result(overall_status="PASS")

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
        MockClient.return_value.run_dq.return_value = self._mock_dq_result(quality_score=150)

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
        MockClient.return_value.run_dq.return_value = self._mock_dq_result(quality_score=-10)

        run = self._create_dq_run()
        execute_dq_run(str(run.id))

        run.refresh_from_db()
        self.assertEqual(run.quality_score, 0.0)

    # ------------------------------------------------------------------
    # 6. Unhandled exception → fail-closed: FAILED + UNKNOWN + asset=UNKNOWN
    # ------------------------------------------------------------------
    @patch("hub.apps.files.storage.S3StorageClient")
    @patch("hub.apps.dq.views.DQServiceClient")
    def test_unhandled_exception_sets_fail_closed(self, MockClient, MockStorage):
        """Unhandled RuntimeError from run_dq → FAILED + UNKNOWN + fail_closed.

        Note: this tests the outer exception handler in execute_dq_run, not
        the circuit breaker path. The mock raises directly, bypassing the
        breaker entirely."""
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
    @override_settings(DQ_POLL_MAX_SECONDS=300)
    @patch("hub.apps.files.storage.S3StorageClient")
    @patch("hub.apps.dq.views.DQServiceClient")
    @patch("time.monotonic")
    def test_timeout_sets_fail_closed(self, mock_monotonic, MockClient, MockStorage):
        """Deadline past → FAILED + UNKNOWN + POLL_TIMEOUT.

        Uses deterministic monotonic values: 100 sets the deadline (100+300=400),
        500 is past the deadline, so the fail-closed branch fires."""
        mock_monotonic.side_effect = [100.0, 500.0]
        MockStorage.return_value.download_file.return_value = b"col1\n1\n"
        MockClient.return_value.run_dq.return_value = self._mock_dq_result()

        run = self._create_dq_run()
        execute_dq_run(str(run.id))

        run.refresh_from_db()
        self.assertEqual(run.status, DQRunStatus.FAILED)
        self.assertEqual(run.overall_status, "UNKNOWN")
        self.assertEqual(run.details_json.get("error_code"), "POLL_TIMEOUT")

    # ------------------------------------------------------------------
    # 8. No file/dataset → FAILED
    # ------------------------------------------------------------------
    def test_no_file_raises_error(self):
        """DQRun with no file, dataset, or asset-with-dataset → FAILED.

        The ValueError("No file found for DQ run") is caught by the outer
        handler which sets FAILED + UNKNOWN + error_type=ValueError."""
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
        self.assertEqual(run.overall_status, "UNKNOWN")
        self.assertIn("error", run.details_json)
        self.assertEqual(run.details_json.get("error_type"), "ValueError")
        self.assertTrue(run.details_json.get("fail_closed"))
