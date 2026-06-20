"""
Security tests: IDOR for Compliance runs.

Per tasks 29.5.2. User from tenant A must not access tenant B's compliance run by ID.
Real APIClient; two tenants/users; assert 403 or 404 for cross-tenant GET.
"""

import uuid

import pytest
from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.jobs.models import Job, JobStatus, JobType

from .base_idor import IDORTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class ComplianceRunIDORTest(IDORTestBase):
    """IDOR: user from tenant A must not access tenant B's compliance run by ID."""

    def test_compliance_run_retrieve_returns_403_or_404_for_other_tenant(self):
        """GET compliance/runs/{id}/ for other tenant's compliance run must return 403 or 404."""
        asset_b = Asset.objects.create(
            tenant=self.tenant_b,
            key=f"idor-comp-asset-b-{uuid.uuid4().hex[:8]}",
            name="IDOR Compliance Asset B",
            status=AssetStatus.DRAFT,
            created_by=self.user_b,
        )
        job_b = Job.objects.create(
            tenant=self.tenant_b,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
            resource_type="ASSET",
            resource_id=str(asset_b.id),
            created_by=self.user_b,
        )
        comp_run_b = ComplianceRun.objects.create(
            tenant=self.tenant_b,
            job=job_b,
            asset=asset_b,
            status=ComplianceRunStatus.SUCCEEDED,
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/compliance/runs/{comp_run_b.id}/")
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Cross-tenant compliance run access must be 403 or 404",
        )

    def test_compliance_run_retrieve_succeeds_for_own_tenant(self):
        """GET compliance/runs/{id}/ for own tenant's compliance run can return 200."""
        asset_a = Asset.objects.create(
            tenant=self.tenant_a,
            key=f"idor-comp-asset-a-{uuid.uuid4().hex[:8]}",
            name="IDOR Compliance Asset A",
            status=AssetStatus.DRAFT,
            created_by=self.user_a,
        )
        job_a = Job.objects.create(
            tenant=self.tenant_a,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
            resource_type="ASSET",
            resource_id=str(asset_a.id),
            created_by=self.user_a,
        )
        comp_run_a = ComplianceRun.objects.create(
            tenant=self.tenant_a,
            job=job_a,
            asset=asset_a,
            status=ComplianceRunStatus.SUCCEEDED,
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/compliance/runs/{comp_run_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
