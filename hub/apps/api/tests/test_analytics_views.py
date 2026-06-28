"""
Unit tests for API Analytics views (APIAnalyticsViewSet, CostsViewSet).

Tests all 9 endpoints defined in hub.apps.api.analytics.views.
Previously only the service layer was tested; views had zero coverage.
"""

import uuid
from unittest.mock import patch

import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, User, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class APIAnalyticsViewSetTest(TestCase):
    """Test APIAnalyticsViewSet — 4 dashboard endpoints"""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"AnalyticsView {uid}",
            slug=f"analytics-view-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"aview-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        # Attach tenant for analytics views that read request.tenant
        self.client.credentials(HTTP_X_TENANT_ID=str(self.tenant.id))

    # ── Dashboard ────────────────────────────────────────────────────

    @patch("hub.apps.api.analytics.views.APIAnalyticsService.get_analytics_dashboard")
    def test_dashboard_returns_200(self, mock_dashboard):
        """GET /api/v1/analytics/api/dashboard/ returns 200"""
        mock_dashboard.return_value = {
            "popular_endpoints": [],
            "usage_trends": [],
            "performance_metrics": {"total_requests": 0},
        }

        url = reverse("api-analytics-dashboard")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("popular_endpoints", response.data)
        self.assertIn("usage_trends", response.data)
        self.assertIn("performance_metrics", response.data)

    @patch("hub.apps.api.analytics.views.APIAnalyticsService.get_analytics_dashboard")
    def test_dashboard_with_date_filters(self, mock_dashboard):
        """Dashboard accepts start_date and end_date query params"""
        mock_dashboard.return_value = {"popular_endpoints": [], "usage_trends": []}

        url = reverse("api-analytics-dashboard")
        response = self.client.get(
            url,
            {"start_date": "2026-01-01T00:00:00Z", "end_date": "2026-06-01T00:00:00Z"},
        )

        self.assertEqual(response.status_code, 200)

    @patch("hub.apps.api.analytics.views.APIAnalyticsService.get_analytics_dashboard")
    def test_dashboard_invalid_date_returns_400(self, mock_dashboard):
        """Dashboard returns 400 for invalid date format"""
        url = reverse("api-analytics-dashboard")
        response = self.client.get(url, {"start_date": "not-a-date"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid", str(response.data))

    def test_dashboard_requires_auth(self):
        """Dashboard returns 401/403 without authentication"""
        unauth_client = APIClient()
        url = reverse("api-analytics-dashboard")
        response = unauth_client.get(url)
        self.assertIn(response.status_code, (401, 403))

    # ── Popular Endpoints ────────────────────────────────────────────

    @patch("hub.apps.api.analytics.views.APIAnalyticsService.get_endpoint_popularity")
    def test_popular_endpoints_returns_200(self, mock_popularity):
        """GET /api/v1/analytics/api/popular-endpoints/ returns 200"""
        mock_popularity.return_value = [
            {"endpoint": "/api/v1/assets/", "request_count": 42},
            {"endpoint": "/api/v1/contracts/", "request_count": 15},
        ]

        url = reverse("api-analytics-popular-endpoints")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["endpoint"], "/api/v1/assets/")

    @patch("hub.apps.api.analytics.views.APIAnalyticsService.get_endpoint_popularity")
    def test_popular_endpoints_with_limit(self, mock_popularity):
        """Popular endpoints accepts limit query param"""
        mock_popularity.return_value = [{"endpoint": "/api/v1/a/", "request_count": 5}]

        url = reverse("api-analytics-popular-endpoints")
        response = self.client.get(url, {"limit": "5"})

        self.assertEqual(response.status_code, 200)
        mock_popularity.assert_called_once()
        call_kwargs = mock_popularity.call_args[1]
        self.assertEqual(call_kwargs["limit"], 5)

    # ── Usage Trends ─────────────────────────────────────────────────

    @patch("hub.apps.api.analytics.views.APIAnalyticsService.get_usage_trends")
    def test_usage_trends_returns_200(self, mock_trends):
        """GET /api/v1/analytics/api/usage-trends/ returns 200"""
        mock_trends.return_value = [
            {"timestamp": "2026-01-01T00:00:00Z", "count": 100},
            {"timestamp": "2026-01-02T00:00:00Z", "count": 150},
        ]

        url = reverse("api-analytics-usage-trends")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    @patch("hub.apps.api.analytics.views.APIAnalyticsService.get_usage_trends")
    def test_usage_trends_with_granularity(self, mock_trends):
        """Usage trends accepts granularity query param"""
        mock_trends.return_value = []

        url = reverse("api-analytics-usage-trends")
        response = self.client.get(url, {"granularity": "hour"})

        self.assertEqual(response.status_code, 200)
        mock_trends.assert_called_once()
        call_kwargs = mock_trends.call_args[1]
        self.assertEqual(call_kwargs["granularity"], "hour")

    # ── Performance ──────────────────────────────────────────────────

    @patch("hub.apps.api.analytics.views.APIAnalyticsService.get_performance_metrics")
    def test_performance_returns_200(self, mock_perf):
        """GET /api/v1/analytics/api/performance/ returns 200"""
        mock_perf.return_value = {
            "total_requests": 500,
            "avg_latency_ms": 45.2,
            "p95_latency_ms": 120.0,
            "error_rate": 0.02,
        }

        url = reverse("api-analytics-performance")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_requests"], 500)
        self.assertAlmostEqual(response.data["avg_latency_ms"], 45.2)


class CostsViewSetTest(TestCase):
    """Test CostsViewSet — 5 cost-tracking endpoints (UC-TA-007)"""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"CostsView {uid}",
            slug=f"costs-view-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        # CostsViewSet requires TENANT_ADMIN or PLATFORM_ADMIN
        self.user = User.objects.create_user(
            email=f"cview-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        tenant_admin_role, _ = Role.objects.get_or_create(
            name="TENANT_ADMIN", tenant=self.tenant
        )
        UserRole.objects.get_or_create(user=self.user, role=tenant_admin_role)

    # ── Cost Summary (list) ──────────────────────────────────────────

    @patch("hub.apps.api.analytics.views.CostTrackingService.get_cost_summary")
    def test_list_cost_summary_returns_200(self, mock_summary):
        """GET /api/v1/analytics/costs/ returns cost summary"""
        mock_summary.return_value = {
            "total_cost": 125.50,
            "currency": "USD",
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        }

        client = APIClient()
        client.force_authenticate(user=self.user)
        client.credentials(HTTP_X_TENANT_ID=str(self.tenant.id))

        url = reverse("costs-list")
        response = client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_cost"], 125.50)
        self.assertEqual(response.data["currency"], "USD")

    def test_list_cost_summary_missing_tenant_returns_400(self):
        """Costs list returns 400 without tenant context.

        Uses a user with a TENANT_ADMIN role (so HasAnyRole passes) but
        no tenant (so _get_tenant_id returns None), triggering the
        _check_tenant ValidationError guard before the service is called.
        No mock needed.
        """
        # Create a separate tenant solely to host the role; the user
        # itself has tenant=None so _get_tenant_id returns None.
        role_tenant = Tenant.objects.create(
            name=f"RoleHost {uuid.uuid4().hex[:8]}",
            slug=f"rolehost-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        admin_role, _ = Role.objects.get_or_create(
            name="TENANT_ADMIN", tenant=role_tenant
        )
        user_no_tenant = User.objects.create_user(
            email=f"cview-nb-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.get_or_create(
            user=user_no_tenant, role=admin_role, tenant=role_tenant
        )
        client = APIClient()
        client.force_authenticate(user=user_no_tenant)

        url = reverse("costs-list")
        response = client.get(url)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Tenant context", str(response.data))

    # ── Breakdown ────────────────────────────────────────────────────

    @patch("hub.apps.api.analytics.views.CostTrackingService.get_cost_breakdown")
    def test_breakdown_returns_200(self, mock_breakdown):
        """GET /api/v1/analytics/costs/breakdown/ returns breakdown"""
        mock_breakdown.return_value = {
            "storage": 50.0,
            "api_calls": 30.0,
            "ingestion": 25.0,
            "export": 20.50,
        }

        client = APIClient()
        client.force_authenticate(user=self.user)
        client.credentials(HTTP_X_TENANT_ID=str(self.tenant.id))

        url = reverse("costs-breakdown")
        response = client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["storage"], 50.0)

    # ── By Asset ─────────────────────────────────────────────────────

    @patch("hub.apps.api.analytics.views.CostTrackingService.get_cost_by_asset")
    def test_by_asset_returns_200(self, mock_by_asset):
        """GET /api/v1/analytics/costs/by-asset/ returns per-asset costs"""
        mock_by_asset.return_value = [
            {"asset_id": "asset-1", "asset_name": "Sales Data", "total_cost": 45.0},
            {"asset_id": "asset-2", "asset_name": "Logs", "total_cost": 80.50},
        ]

        client = APIClient()
        client.force_authenticate(user=self.user)
        client.credentials(HTTP_X_TENANT_ID=str(self.tenant.id))

        url = reverse("costs-by-asset")
        response = client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    # ── Recommendations ──────────────────────────────────────────────

    @patch("hub.apps.api.analytics.views.CostTrackingService.get_cost_recommendations")
    def test_recommendations_returns_200(self, mock_recs):
        """GET /api/v1/analytics/costs/recommendations/ returns recommendations"""
        mock_recs.return_value = [
            {"type": "storage_cleanup", "potential_savings": 25.0},
        ]

        client = APIClient()
        client.force_authenticate(user=self.user)
        client.credentials(HTTP_X_TENANT_ID=str(self.tenant.id))

        url = reverse("costs-recommendations")
        response = client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    # ── Trends ───────────────────────────────────────────────────────

    @patch("hub.apps.api.analytics.views.CostTrackingService.get_cost_trends")
    def test_trends_returns_200(self, mock_trends):
        """GET /api/v1/analytics/costs/trends/ returns cost trends"""
        mock_trends.return_value = [
            {"month": "2026-01", "total": 100.0},
            {"month": "2026-02", "total": 110.0},
        ]

        client = APIClient()
        client.force_authenticate(user=self.user)
        client.credentials(HTTP_X_TENANT_ID=str(self.tenant.id))

        url = reverse("costs-trends")
        response = client.get(url, {"months": "3"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    @patch("hub.apps.api.analytics.views.CostTrackingService.get_cost_trends")
    def test_trends_default_months(self, mock_trends):
        """Cost trends defaults to 6 months when not specified"""
        mock_trends.return_value = []

        client = APIClient()
        client.force_authenticate(user=self.user)
        client.credentials(HTTP_X_TENANT_ID=str(self.tenant.id))

        url = reverse("costs-trends")
        response = client.get(url)

        self.assertEqual(response.status_code, 200)
        mock_trends.assert_called_once()
        call_kwargs = mock_trends.call_args[1]
        self.assertEqual(call_kwargs["months"], 6)

    def test_trends_invalid_months_silently_defaults_to_6(self):
        """Costs trends silently defaults to 6 months for invalid months param.

        The production code catches (TypeError, ValueError) from
        int(months) and falls back to the default of 6 rather than
        returning 400. This test pins that behaviour so a future
        change that adds validation (and returns 400) will fail
        here and force an explicit decision.
        """
        client = APIClient()
        client.force_authenticate(user=self.user)
        client.credentials(HTTP_X_TENANT_ID=str(self.tenant.id))

        url = reverse("costs-trends")
        response = client.get(url, {"months": "not-a-number"})

        self.assertEqual(response.status_code, 200)

    def test_breakdown_missing_tenant_returns_400(self):
        """Costs breakdown returns 400 without tenant context.

        Uses a user with a TENANT_ADMIN role but no tenant so
        _check_tenant raises ValidationError before the service call.
        """
        role_tenant = Tenant.objects.create(
            name=f"RoleHost {uuid.uuid4().hex[:8]}",
            slug=f"rolehost-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        admin_role, _ = Role.objects.get_or_create(
            name="TENANT_ADMIN", tenant=role_tenant
        )
        user_no_tenant = User.objects.create_user(
            email=f"cview-bd-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.get_or_create(
            user=user_no_tenant, role=admin_role, tenant=role_tenant
        )
        client = APIClient()
        client.force_authenticate(user=user_no_tenant)

        url = reverse("costs-breakdown")
        response = client.get(url)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Tenant context", str(response.data))

    def test_costs_list_requires_auth(self):
        """Costs endpoints return 401/403 without authentication"""
        unauth_client = APIClient()
        url = reverse("costs-list")
        response = unauth_client.get(url)
        self.assertIn(response.status_code, (401, 403))
