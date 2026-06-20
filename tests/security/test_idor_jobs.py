"""
Security tests: IDOR for Jobs.

Per tasks 29.5.1. User from tenant A must not access tenant B's job by ID.
Real APIClient; two tenants/users; assert 403 or 404 for cross-tenant GET.
"""

import uuid

import pytest
from rest_framework import status

from hub.apps.jobs.models import Job, JobStatus, JobType

from .base_idor import IDORTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class JobIDORTest(IDORTestBase):
    """IDOR: user from tenant A must not access tenant B's job by ID."""

    def test_job_retrieve_returns_403_or_404_for_other_tenant(self):
        """GET jobs/{id}/ for other tenant's job must return 403 or 404."""
        job_b = Job.objects.create(
            tenant=self.tenant_b,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
            created_by=self.user_b,
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/jobs/{job_b.id}/")
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Cross-tenant job access must be 403 or 404",
        )

    def test_job_retrieve_succeeds_for_own_tenant(self):
        """GET jobs/{id}/ for own tenant's job can return 200."""
        job_a = Job.objects.create(
            tenant=self.tenant_a,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
            created_by=self.user_a,
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/jobs/{job_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
