"""
Phase 69 (69.3.1) — Compliance Polling Timeout Tests

Tests fail-closed behavior when polling exceeds COMPLIANCE_POLL_MAX_SECONDS.
"""

import uuid
from datetime import timedelta
from unittest.mock import patch, MagicMock

import pytest
from django.test import TestCase, override_settings
from django.utils import timezone


@pytest.mark.django_db(transaction=True)
class CompliancePollTimeoutTest(TestCase):
    """Test compliance polling deadline and fail-closed behavior."""

    def _create_run(self, started_minutes_ago=0):
        """Create a ComplianceRun in RUNNING state."""
        from hub.apps.compliance.models import ComplianceRun
        from hub.apps.tenants.models import Tenant

        tenant, _ = Tenant.objects.get_or_create(
            name="poll-timeout-test",
            defaults={"slug": "poll-timeout-test"},
        )

        # Create required related objects
        from hub.apps.jobs.models import Job
        from hub.apps.assets.models import Asset

        asset = Asset.objects.create(
            tenant=tenant,
            name=f"poll-test-{uuid.uuid4().hex[:8]}",
        )
        job = Job.objects.create(
            tenant=tenant,
            type="COMPLIANCE_CHECK",
            status="RUNNING",
            resource_type="ASSET",
            resource_id=str(asset.id),
        )

        # Insert directly to bypass model clean() validation
        from django.db import connection
        run_id = uuid.uuid4()
        started_at = timezone.now() - timedelta(minutes=started_minutes_ago)
        now = timezone.now()
        job_id_meta = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO compliance_runs
                    (id, tenant_id, job_id, asset_id, status,
                     started_at, created_at, updated_at, metadata_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    str(run_id), str(tenant.id), str(job.id),
                    str(asset.id), "RUNNING", started_at, now, now,
                    f'{{"job_id": "{job_id_meta}"}}',
                ],
            )
        return ComplianceRun.objects.get(id=run_id)

    @override_settings(COMPLIANCE_POLL_MAX_SECONDS=1)
    def test_poll_timeout_marks_run_failed(self):
        """Polling timeout sets status=FAILED."""
        from hub.apps.compliance.tasks import poll_compliance_job

        run = self._create_run(started_minutes_ago=2)
        poll_compliance_job(run.id)

        run.refresh_from_db()
        self.assertEqual(run.status, "FAILED")

    @override_settings(COMPLIANCE_POLL_MAX_SECONDS=1)
    def test_poll_timeout_sets_error_code(self):
        """Timeout sets error_code=POLL_TIMEOUT in metadata_json."""
        from hub.apps.compliance.tasks import poll_compliance_job

        run = self._create_run(started_minutes_ago=2)
        poll_compliance_job(run.id)

        run.refresh_from_db()
        metadata = run.metadata_json or {}
        self.assertEqual(metadata.get("error_code"), "POLL_TIMEOUT")

    @override_settings(COMPLIANCE_POLL_MAX_SECONDS=600)
    def test_normal_poll_within_deadline_reaches_service(self):
        """Within deadline, the polling task reaches the service call."""
        from hub.apps.compliance.tasks import poll_compliance_job

        run = self._create_run(started_minutes_ago=0)

        # Patch the service client at its source module
        with patch(
            "hub.apps.compliance.service_client.ComplianceServiceClient"
        ) as mock_cls:
            mock_client = MagicMock()
            mock_client.get_scan_result.return_value = {
                "status": "RUNNING",
            }
            mock_cls.return_value = mock_client

            # Also patch _reenqueue to avoid actual RQ enqueue
            with patch(
                "hub.apps.compliance.tasks._reenqueue"
            ):
                poll_compliance_job(run.id)

            # The client was called — proves we got past the timeout check
            mock_client.get_scan_result.assert_called_once()
