"""
Phase 69 (69.3.1) — Compliance Polling Timeout Tests

Tests fail-closed behavior when polling exceeds COMPLIANCE_POLL_MAX_SECONDS.
"""

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase, override_settings
from django.utils import timezone


@pytest.mark.django_db(transaction=True)
class CompliancePollTimeoutTest(TestCase):
    """Test compliance polling deadline and fail-closed behavior."""

    def _create_run(self, started_minutes_ago=0):
        """Create a ComplianceRun in RUNNING state via ORM.

        Uses the real model layer (save/clean/signals) rather than raw SQL
        so the test exercises the same code paths as production.  The only
        requirement is that ``ComplianceRun.clean()`` passes — satisfied
        because an ``Asset`` is always provided.
        """
        from hub.apps.assets.models import Asset
        from hub.apps.compliance.models import ComplianceRun
        from hub.apps.jobs.models import Job
        from hub.apps.tenants.models import Tenant

        tenant, _ = Tenant.objects.get_or_create(
            name="poll-timeout-test",
            defaults={"slug": "poll-timeout-test"},
        )

        uid = uuid.uuid4().hex[:8]
        asset = Asset.objects.create(
            tenant=tenant,
            key=f"poll-test-{uid}",
            name=f"poll-test-{uid}",
        )
        job = Job.objects.create(
            tenant=tenant,
            type="COMPLIANCE_CHECK",
            status="RUNNING",
            resource_type="ASSET",
            resource_id=str(asset.id),
        )

        started_at = timezone.now() - timedelta(minutes=started_minutes_ago)
        run = ComplianceRun.objects.create(
            tenant=tenant,
            asset=asset,
            job=job,
            status="RUNNING",
            scan_mode="FILE_SCAN",
            started_at=started_at,
            metadata_json={"job_id": str(uuid.uuid4())},
        )
        return run

    @override_settings(COMPLIANCE_POLL_MAX_SECONDS=1)
    def test_poll_timeout_marks_run_failed(self):
        """Polling timeout sets status=FAILED."""
        from hub.apps.compliance.tasks import poll_compliance_job

        run = self._create_run(started_minutes_ago=2)
        poll_compliance_job(run.id)

        run.refresh_from_db()
        from hub.apps.compliance.models import ComplianceRunStatus

        self.assertEqual(run.status, ComplianceRunStatus.FAILED)

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
        with patch("hub.apps.compliance.service_client.ComplianceServiceClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.get_scan_result.return_value = {
                "status": "RUNNING",
            }
            mock_cls.return_value = mock_client

            # Also patch _reenqueue to avoid actual RQ enqueue
            with patch("hub.apps.compliance.tasks._reenqueue"):
                poll_compliance_job(run.id)

            # The client was called — proves we got past the timeout check
            mock_client.get_scan_result.assert_called_once()

    @override_settings(COMPLIANCE_POLL_MAX_SECONDS=1)
    @patch("hub.apps.compliance.service_client.ComplianceServiceClient")
    def test_timeout_falls_back_to_created_at_when_started_at_none(
        self, MockClient,
    ):
        """When started_at is None, the timeout check uses created_at."""
        from hub.apps.compliance.tasks import poll_compliance_job
        from hub.apps.compliance.models import ComplianceRun

        run = self._create_run(started_minutes_ago=2)
        # ``created_at`` is auto_now_add so we must bypass the ORM
        # to set it in the past.  Simulate a run whose started_at was
        # never filled in but whose row was created long ago.
        old = timezone.now() - timedelta(minutes=2)
        ComplianceRun.objects.filter(pk=run.pk).update(
            started_at=None, created_at=old,
        )
        run.refresh_from_db()
        self.assertIsNone(run.started_at)
        poll_compliance_job(run.id)

        run.refresh_from_db()
        from hub.apps.compliance.models import ComplianceRunStatus

        self.assertEqual(run.status, ComplianceRunStatus.FAILED)
