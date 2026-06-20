"""
Phase 69 (69.3.2) — DQ Execution Timeout Tests

Tests fail-closed behavior when DQ execution exceeds DQ_POLL_MAX_SECONDS.
Uses deterministic time patching to avoid timing-dependent flakiness.
"""

import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.dq.tests.test_base import DQTestBase
from hub.apps.dq.views import execute_dq_run
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class DQPollTimeoutTest(DQTestBase):
    """Test the DQ deadline / poll-timeout logic in execute_dq_run()."""

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
    # POLL_TIMEOUT: deadline exceeded after service call = fail-closed
    # ------------------------------------------------------------------
    @override_settings(DQ_POLL_MAX_SECONDS=300)
    @patch("hub.apps.files.storage.S3StorageClient")
    @patch("hub.apps.dq.views.DQServiceClient")
    @patch("time.monotonic")
    def test_deadline_exceeded_sets_fail_closed_and_unknown(
        self, mock_monotonic, MockClient, MockStorage
    ):
        """When the deadline has passed by the time the service call returns,
        the run is set to FAILED + UNKNOWN + POLL_TIMEOUT."""
        # Deterministic time: first call sets deadline to 100, second to 500
        # (past the 100 + DQ_POLL_MAX_SECONDS=300 → 400 deadline).
        mock_monotonic.side_effect = [100.0, 500.0]

        MockStorage.return_value.download_file.return_value = b"col1,col2\n1,2\n"
        MockClient.return_value.run_dq.return_value = self._mock_dq_result()

        run = self._create_dq_run()
        execute_dq_run(str(run.id))

        run.refresh_from_db()
        self.assertEqual(run.status, DQRunStatus.FAILED)
        self.assertEqual(run.overall_status, "UNKNOWN")
        self.assertIsNotNone(run.details_json)
        self.assertEqual(run.details_json.get("error_code"), "POLL_TIMEOUT")
        self.assertIn("deadline", run.details_json.get("error", "").lower())

    # ------------------------------------------------------------------
    # Within deadline → normal processing
    # ------------------------------------------------------------------
    @override_settings(DQ_POLL_MAX_SECONDS=300)
    @patch("hub.apps.files.storage.S3StorageClient")
    @patch("hub.apps.dq.views.DQServiceClient")
    @patch("time.monotonic")
    def test_within_deadline_normal_processing(self, mock_monotonic, MockClient, MockStorage):
        """When the deadline has NOT passed, the result is persisted normally."""
        # First call = 100 (sets deadline to 100+300=400), remaining calls stay
        # below 400 so the deadline check passes.
        mock_monotonic.side_effect = [100.0, 200.0]

        MockStorage.return_value.download_file.return_value = b"col1,col2\n1,2\n"
        MockClient.return_value.run_dq.return_value = self._mock_dq_result(
            overall_status="PASS", quality_score=95.0
        )

        run = self._create_dq_run()
        execute_dq_run(str(run.id))

        run.refresh_from_db()
        self.assertEqual(run.status, DQRunStatus.SUCCEEDED)
        self.assertEqual(run.overall_status, "PASS")
        self.assertEqual(run.quality_score, 95.0)
        self.assertNotEqual(run.details_json.get("error_code"), "POLL_TIMEOUT")
