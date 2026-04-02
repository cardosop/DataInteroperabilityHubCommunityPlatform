"""
Phase 73.3 — Prefect Job Orphan Detection Tests

Tests the _recover_prefect_orphans section of recover_stuck_jobs command.
"""
import uuid

from datetime import timedelta
from io import StringIO
from unittest.mock import patch, MagicMock

import pytest
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from hub.apps.jobs.models import Job, JobStatus


@pytest.mark.django_db(transaction=True)
class PrefectOrphanDetectionTest(TestCase):
    """Test Prefect orphan detection in recover_stuck_jobs."""

    def setUp(self):
        from hub.apps.tenants.models import Tenant
        self.tenant = Tenant.objects.create(
            name="Test Orphan Tenant", slug="test-orphan",
            status="ACTIVE",
        )

    def _create_prefect_job(self, minutes_ago=45):
        import uuid
        job = Job.objects.create(
            tenant=self.tenant,
            type="SCHEDULED_INGESTION",
            status=JobStatus.PENDING,
            resource_id=str(uuid.uuid4()),
            details_json={
                "executed_by_prefect": True,
                "scheduled_ingestion_id": "si-test-123",
            },
        )
        # Bypass auto_now_add
        Job.objects.filter(id=job.id).update(
            created_at=timezone.now() - timedelta(minutes=minutes_ago),
        )
        job.refresh_from_db()
        return job

    @patch("httpx.get")
    def test_orphan_prefect_job_detected(self, mock_get):
        """PENDING Prefect job with no flow run → marked FAILED."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        job = self._create_prefect_job(minutes_ago=45)

        with patch.dict(
            "os.environ",
            {"PREFECT_INTEGRATION_SERVICE_URL": "http://prefect:8084"},
        ):
            out = StringIO()
            call_command(
                "recover_stuck_jobs",
                "--threshold-minutes=120",
                stdout=out,
            )

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertEqual(
            (job.result_json or {}).get("error_code"),
            "PREFECT_SUBMISSION_ORPHAN",
        )
        self.assertIn("never submitted", job.error_message)

    @patch("httpx.get")
    def test_active_prefect_job_not_touched(self, mock_get):
        """PENDING Prefect job WITH active flow run → left unchanged."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        job = self._create_prefect_job(minutes_ago=45)

        with patch.dict(
            "os.environ",
            {"PREFECT_INTEGRATION_SERVICE_URL": "http://prefect:8084"},
        ):
            out = StringIO()
            call_command(
                "recover_stuck_jobs",
                "--threshold-minutes=120",
                stdout=out,
            )

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.PENDING)
