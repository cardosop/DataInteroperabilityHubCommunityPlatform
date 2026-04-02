"""
Phase 83.2 — recover_stuck_jobs management command tests.
"""
import uuid
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from hub.apps.jobs.models import Job, JobStatus, JobType


@pytest.mark.django_db(transaction=True)
class RecoverStuckJobsCommandTest(TestCase):

    def _create_tenant(self):
        from hub.apps.tenants.models import Tenant
        return Tenant.objects.get_or_create(
            name="recover-test", defaults={"slug": "recover-test"},
        )[0]

    def _create_job(self, tenant, status, started_at=None, **kwargs):
        return Job.objects.create(
            tenant=tenant, type=JobType.DQ_RUN,
            status=status, resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            started_at=started_at, **kwargs,
        )

    def test_stuck_running_marked_failed(self):
        tenant = self._create_tenant()
        old = timezone.now() - timedelta(hours=3)
        job = self._create_job(tenant, JobStatus.RUNNING, started_at=old)
        out = StringIO()
        call_command("recover_stuck_jobs", stdout=out)
        job.refresh_from_db()
        assert job.status == JobStatus.FAILED

    def test_recent_running_untouched(self):
        tenant = self._create_tenant()
        recent = timezone.now() - timedelta(minutes=10)
        job = self._create_job(tenant, JobStatus.RUNNING, started_at=recent)
        call_command("recover_stuck_jobs")
        job.refresh_from_db()
        assert job.status == JobStatus.RUNNING

    def test_dry_run_does_not_modify(self):
        tenant = self._create_tenant()
        old = timezone.now() - timedelta(hours=3)
        job = self._create_job(tenant, JobStatus.RUNNING, started_at=old)
        call_command("recover_stuck_jobs", "--dry-run")
        job.refresh_from_db()
        assert job.status == JobStatus.RUNNING

    def test_completed_jobs_untouched(self):
        tenant = self._create_tenant()
        old = timezone.now() - timedelta(hours=3)
        job = self._create_job(
            tenant, JobStatus.COMPLETED, started_at=old,
            completed_at=timezone.now(),
        )
        call_command("recover_stuck_jobs")
        job.refresh_from_db()
        assert job.status == JobStatus.COMPLETED

    def test_no_stuck_jobs_clean_exit(self):
        out = StringIO()
        call_command("recover_stuck_jobs", stdout=out)
        assert "No stuck jobs found" in out.getvalue() or "0" in out.getvalue() or "Recovered" in out.getvalue()
