"""
Unit tests for Cost Tracking (UC-TA-007).

Tests for CostTrackingService and CostsViewSet.
"""

import uuid

import pytest
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.api.analytics.cost_tracking import CostTrackingService
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant, TenantPlan
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, User, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class CostTrackingServiceTest(TestCase):
    """Test CostTrackingService cost calculation."""

    def setUp(self):
        from django.core.management import call_command

        call_command("seed_default_plans")
        uid = str(uuid.uuid4())[:8]
        self.plan = TenantPlan.objects.get(slug="free")
        self.tenant = Tenant.objects.create(
            name=f"Cost Test Tenant {uid}",
            slug=f"cost-test-{uid}",
            plan=self.plan,
        )
        ensure_tenant_has_active_subscription(self.tenant)

    def test_get_cost_summary_returns_structure(self):
        """Cost summary returns tenant_id, total_cost, breakdown, period."""
        result = CostTrackingService.get_cost_summary(str(self.tenant.id))
        self.assertEqual(result["tenant_id"], str(self.tenant.id))
        self.assertIn("total_cost", result)
        self.assertIn("breakdown", result)
        self.assertIn("period_start", result)
        self.assertIn("period_end", result)
        self.assertIsInstance(result["total_cost"], (int, float))
        self.assertIsInstance(result["breakdown"], list)

    def test_get_cost_summary_breakdown_categories(self):
        """Breakdown includes core cost categories."""
        result = CostTrackingService.get_cost_summary(str(self.tenant.id))
        categories = {b["category"] for b in result["breakdown"]}
        # FLSC path returns: api_calls, storage, compute, engineering, support, platform
        # Fallback path returns: storage, api_calls, ingestion, export
        # Both paths always include storage and api_calls
        self.assertIn("storage", categories)
        self.assertIn("api_calls", categories)
        self.assertGreater(len(categories), 2,
                          f"Expected more than 2 categories, got: {categories}")

    def test_get_cost_summary_storage_cost_scales_with_usage(self):
        """Storage cost increases with storage usage."""
        # Create File to generate storage usage (TenantUsageService aggregates from File)
        File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=5 * (1024**3),  # 5 GB
            storage_path=f"tenant/{self.tenant.id}/test-{uuid.uuid4().hex}.csv",
            status=FileStatus.ACTIVE,
        )
        result = CostTrackingService.get_cost_summary(str(self.tenant.id))
        storage_item = next(b for b in result["breakdown"] if b["category"] == "storage")
        self.assertGreater(storage_item["amount_usd"], 0)

    @override_settings(COST_RATES={"storage_per_gb_month": "0.10", "api_per_1000": "0.01"})
    def test_get_cost_summary_uses_settings_rates(self):
        """Cost calculation uses COST_RATES from settings."""
        # Create File for storage (1 GB)
        File.objects.create(
            tenant=self.tenant,
            name="rate-test.csv",
            content_type="text/csv",
            size=1 * (1024**3),
            storage_path=f"tenant/{self.tenant.id}/rate-{uuid.uuid4().hex}.csv",
            status=FileStatus.ACTIVE,
        )
        # API calls come from APIUsage - we can't easily create those without BaaS.
        # Test storage rate: 1 GB * 0.10 = 0.10
        result = CostTrackingService.get_cost_summary(str(self.tenant.id))
        storage_item = next(
            (b for b in result["breakdown"] if b["category"] == "storage"),
            None,
        )
        self.assertIsNotNone(storage_item, "Storage category missing from breakdown")
        if result.get("source") == "flsc":
            # FLSC returns amount_cents
            self.assertAlmostEqual(storage_item.get("amount_cents", 0) / 100.0, 0.10, places=2)
        else:
            self.assertAlmostEqual(storage_item["amount_usd"], 0.10, places=2)

    def test_get_cost_by_asset_returns_structure(self):
        """Cost by asset returns by_asset list and total_cost."""
        result = CostTrackingService.get_cost_by_asset(str(self.tenant.id))
        self.assertEqual(result["tenant_id"], str(self.tenant.id))
        self.assertIn("by_asset", result)
        self.assertIn("total_cost", result)
        self.assertIsInstance(result["by_asset"], list)

    def test_get_cost_by_asset_includes_unassigned_storage(self):
        """Cost by asset includes Unassigned row for datasets without asset."""
        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset

        # Create asset with dataset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
        )
        file1 = File.objects.create(
            tenant=self.tenant,
            name="f1.csv",
            content_type="text/csv",
            size=1024,
            storage_path=f"tenant/{self.tenant.id}/f1.csv",
            status=FileStatus.ACTIVE,
        )
        Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file1,
            format="CSV",
        )
        # Create dataset without asset (unassigned)
        file2 = File.objects.create(
            tenant=self.tenant,
            name="f2.csv",
            content_type="text/csv",
            size=2048,
            storage_path=f"tenant/{self.tenant.id}/f2.csv",
            status=FileStatus.ACTIVE,
        )
        Dataset.objects.create(
            tenant=self.tenant,
            asset=None,
            file=file2,
            format="CSV",
        )
        result = CostTrackingService.get_cost_by_asset(str(self.tenant.id))
        unassigned = next(
            (a for a in result["by_asset"] if a["asset_id"] == "__unassigned__"),
            None,
        )
        self.assertIsNotNone(unassigned)
        self.assertEqual(unassigned["asset_name"], "Unassigned")
        self.assertEqual(unassigned["storage_bytes"], 2048)

    def test_get_cost_recommendations_returns_list(self):
        """Recommendations returns at least one item."""
        result = CostTrackingService.get_cost_recommendations(str(self.tenant.id))
        self.assertEqual(result["tenant_id"], str(self.tenant.id))
        self.assertIn("recommendations", result)
        self.assertGreaterEqual(len(result["recommendations"]), 1)

    def test_get_cost_trends_returns_months(self):
        """Trends returns requested number of months."""
        result = CostTrackingService.get_cost_trends(str(self.tenant.id), months=3)
        self.assertEqual(result["tenant_id"], str(self.tenant.id))
        self.assertIn("trends", result)
        self.assertEqual(len(result["trends"]), 3)


class CostsViewSetTest(TestCase):
    """Test CostsViewSet API endpoints."""

    def setUp(self):
        from django.core.management import call_command

        call_command("seed_default_plans")
        uid = str(uuid.uuid4())[:8]
        self.plan = TenantPlan.objects.get(slug="free")
        self.tenant = Tenant.objects.create(
            name=f"Cost API Tenant {uid}",
            slug=f"cost-api-{uid}",
            plan=self.plan,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        self.user = User.objects.create_user(
            email=f"user-{uid}@test.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.user, role=self.admin_role)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_costs_list_success(self):
        """GET /api/v1/analytics/costs/ returns 200 with cost data."""
        response = self.client.get(reverse("costs-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tenant_id"], str(self.tenant.id))
        self.assertIn("total_cost", response.data)
        self.assertIn("breakdown", response.data)

    def test_costs_breakdown_success(self):
        """GET /api/v1/analytics/costs/breakdown/ returns 200."""
        response = self.client.get(reverse("costs-breakdown"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("breakdown", response.data)

    def test_costs_by_asset_success(self):
        """GET /api/v1/analytics/costs/by-asset/ returns 200."""
        response = self.client.get(reverse("costs-by-asset"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("by_asset", response.data)
        self.assertIn("total_cost", response.data)

    def test_costs_recommendations_success(self):
        """GET /api/v1/analytics/costs/recommendations/ returns 200."""
        response = self.client.get(reverse("costs-recommendations"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("recommendations", response.data)

    def test_costs_trends_success(self):
        """GET /api/v1/analytics/costs/trends/ returns 200."""
        response = self.client.get(reverse("costs-trends"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("trends", response.data)

    def test_costs_401_unauthenticated(self):
        """Costs endpoints return 401 when unauthenticated."""
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse("costs-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_costs_403_or_400_when_no_tenant(self):
        """Costs endpoints return 403 (no role) or 400 (tenant context) when user has no tenant."""
        user_no_tenant = User.objects.create_user(
            email="no-tenant-cost@test.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=user_no_tenant)
        response = self.client.get(reverse("costs-list"))
        self.assertIn(
            response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST)
        )

    def test_costs_403_when_not_tenant_admin(self):
        """Costs endpoints return 403 when user lacks TENANT_ADMIN role."""
        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        provider_user = User.objects.create_user(
            email="provider-cost@test.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=provider_user, role=provider_role)
        self.client.force_authenticate(user=provider_user)
        response = self.client.get("/api/v1/analytics/costs/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
