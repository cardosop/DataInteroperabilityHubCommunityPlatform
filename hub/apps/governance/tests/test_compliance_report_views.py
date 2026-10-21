"""
Tests for the governance compliance-report REST surface.

POST /api/v1/governance/compliance-reports/       — create PENDING runs
GET  /api/v1/governance/compliance-reports/{id}/  — read a run

These endpoints back the SDK ``GovernanceAPI.generate_compliance_report`` /
``get_compliance_report`` contract (SDK batch 9-2-f).
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ComplianceReportViewsTest(TestCase):
    """API tests for governance compliance reports."""

    def setUp(self):
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}"
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uid}",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        self.client.force_authenticate(user=self.user)

    def test_generate_report_creates_pending_run_per_asset(self):
        """POST creates a PENDING ComplianceRun for each tenant-scoped asset."""
        response = self.client.post(
            "/api/v1/governance/compliance-reports/",
            {"regime": "GDPR", "asset_ids": [str(self.asset.id)]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["regime"], "GDPR")
        self.assertIn("report_id", response.data)
        self.assertEqual(response.data["asset_ids"], [str(self.asset.id)])

        run = ComplianceRun.objects.get(id=response.data["report_id"])
        self.assertEqual(run.asset, self.asset)
        self.assertEqual(run.status, ComplianceRunStatus.PENDING)
        self.assertEqual(run.regulations, ["GDPR"])

    def test_generate_report_rejects_unknown_regime(self):
        """POST with an invalid regime returns 400."""
        response = self.client.post(
            "/api/v1/governance/compliance-reports/",
            {"regime": "NOT_A_REGIME", "asset_ids": [str(self.asset.id)]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_report(self):
        """GET returns the serialized run with a report_id alias."""
        run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            regulations=["GDPR"],
            status=ComplianceRunStatus.PENDING,
        )

        response = self.client.get(f"/api/v1/governance/compliance-reports/{run.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(run.id))
        self.assertEqual(response.data["report_id"], str(run.id))

    def test_foreign_tenant_asset_is_rejected(self):
        """asset_ids from another tenant must not create runs (400, tenant-scoped)."""
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug=f"other-tenant-{uuid.uuid4().hex[:8]}"
        )
        other_asset = Asset.objects.create(
            tenant=other_tenant,
            key="other-asset",
            name="Other Asset",
            status=AssetStatus.DRAFT,
        )

        response = self.client.post(
            "/api/v1/governance/compliance-reports/",
            {"regime": "GDPR", "asset_ids": [str(other_asset.id)]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            ComplianceRun.objects.filter(tenant=self.tenant, asset=other_asset).exists()
        )
