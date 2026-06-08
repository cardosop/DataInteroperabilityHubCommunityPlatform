"""
Comprehensive Advanced Observability New Use Cases Test Suite (Task 10.1.53.8)

Tests all new Advanced Observability use cases:
- UC-OBS-ADV-001: Monitor Reliability Scores (via asset health-score)
- UC-OBS-ADV-002: Track Data Costs (via /api/v1/analytics/costs/)
- UC-OBS-ADV-003: Set Up Predictive Alerts (via DQ alerting rules)
- UC-OBS-ADV-004: Monitor Performance Regressions (via jobs performance)

All tests hit real endpoints -- no mocks/stubs.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import AssetStatus
from hub.apps.tenants.models import KYCStatus, TenantStatus
from hub.apps.testing.billing_support import (
ensure_tenant_has_active_subscription,
)
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import Role, UserRole
from tests.fixtures.test_data_factories import (
    AssetFactory,
    TenantFactory,
    UserFactory,
)
from tests.utils.test_data_management import TestDatabaseIsolationMixin

User = get_user_model()

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.uc("UC-OBS-ADV-001"),
    pytest.mark.uc("UC-OBS-ADV-002"),
    pytest.mark.uc("UC-OBS-ADV-003"),
    pytest.mark.uc("UC-OBS-ADV-004"),
]


class AdvancedObservabilityTestBase(
    TestCase, TestDatabaseIsolationMixin,
):
    """Base test class for Advanced Observability new use cases."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()

        uid = uuid.uuid4().hex[:8]
        self.tenant = TenantFactory.create_tenant(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Admin"},
        )

        self.dpo_user = UserFactory.create_user(
            tenant=self.tenant,
            email=f"dpo-{uid}@example.com",
        )
        UserRole.objects.get_or_create(
            user=self.dpo_user, role=self.data_provider_role,
        )

        self.admin_user = UserFactory.create_user(
            tenant=self.tenant,
            email=f"admin-{uid}@example.com",
        )
        UserRole.objects.get_or_create(
            user=self.admin_user, role=self.tenant_admin_role,
        )

        self.asset = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.dpo_user,
            status=AssetStatus.ACTIVE,
        )


# ------------------------------------------------------------------
# UC-OBS-ADV-001: Monitor Reliability Scores
# ------------------------------------------------------------------
class UCOBSADV001MonitorReliabilityScoresTest(
    AdvancedObservabilityTestBase,
):
    """UC-OBS-ADV-001: Monitor Reliability Scores

    Tests the real asset health-score endpoint which computes
    reliability from DQ status, compliance status, and contracts.
    """

    def test_health_score_returns_score_and_status(self):
        """GET /assets/{id}/health-score/ -> score, dq/compliance status."""
        self.client.force_authenticate(user=self.dpo_user)
        url = f"/api/v1/assets/{self.asset.id}/health-score/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertIn("health_score", body)
        self.assertIn("asset_id", body)
        # health_score can be None for fresh assets with no DQ runs
        if body["health_score"] is not None:
            self.assertIsInstance(
                body["health_score"], (int, float),
            )

    def test_health_score_with_breakdown(self):
        """GET with breakdown=true -> includes component breakdown."""
        self.client.force_authenticate(user=self.dpo_user)
        url = (
            f"/api/v1/assets/{self.asset.id}"
            f"/health-score/?breakdown=true"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertIn("health_score", body)
        self.assertIn("breakdown", body)
        breakdown = body["breakdown"]
        self.assertIsInstance(breakdown, dict)

    def test_health_score_with_recalculate(self):
        """GET with recalculate=true -> forces fresh computation."""
        self.client.force_authenticate(user=self.dpo_user)
        url = (
            f"/api/v1/assets/{self.asset.id}"
            f"/health-score/?recalculate=true"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertIn("health_score", body)

    def test_health_score_nonexistent_asset(self):
        """GET health-score for non-existent asset -> 404."""
        self.client.force_authenticate(user=self.dpo_user)
        fake_id = uuid.uuid4()
        url = f"/api/v1/assets/{fake_id}/health-score/"
        response = self.client.get(url)
        self.assertEqual(
            response.status_code, status.HTTP_404_NOT_FOUND,
        )

    def test_health_score_unauthorized(self):
        """Unauthenticated health-score -> 401/403."""
        self.client.logout()
        url = f"/api/v1/assets/{self.asset.id}/health-score/"
        response = self.client.get(url)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )


# ------------------------------------------------------------------
# UC-OBS-ADV-002: Track Data Costs
# ------------------------------------------------------------------
class UCOBSADV002TrackDataCostsTest(
    AdvancedObservabilityTestBase,
):
    """UC-OBS-ADV-002: Track Data Costs

    Tests real /api/v1/analytics/costs/ endpoints.
    """

    def test_cost_breakdown(self):
        """GET /analytics/costs/breakdown/ -> cost categories."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            "/api/v1/analytics/costs/breakdown/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertIn("total_cost", body)
        self.assertIn("breakdown", body)
        # breakdown is a list of category dicts
        self.assertIsInstance(body["breakdown"], list)

    def test_cost_by_asset(self):
        """GET /analytics/costs/by-asset/ -> per-asset costs."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            "/api/v1/analytics/costs/by-asset/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertIn("by_asset", body)
        self.assertIsInstance(body["by_asset"], list)

    def test_cost_recommendations(self):
        """GET /analytics/costs/recommendations/ -> optimization tips."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            "/api/v1/analytics/costs/recommendations/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cost_trends(self):
        """GET /analytics/costs/trends/ -> cost over time."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            "/api/v1/analytics/costs/trends/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cost_unauthorized(self):
        """Unauthenticated cost tracking -> 401/403."""
        self.client.logout()
        response = self.client.get(
            "/api/v1/analytics/costs/breakdown/",
        )
        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )


# ------------------------------------------------------------------
# UC-OBS-ADV-003: Set Up Predictive Alerts
# ------------------------------------------------------------------
class UCOBSADV003SetUpPredictiveAlertsTest(
    AdvancedObservabilityTestBase,
):
    """UC-OBS-ADV-003: Set Up Predictive Alerts

    Tests webhook creation as alert delivery channel and DQ alerting
    rule model validation (DQAlertingRule is the real alerting infra).
    """

    def test_create_webhook_as_alert_channel(self):
        """POST /webhooks/webhooks/ creates alert channel -> 201."""
        self.client.force_authenticate(user=self.dpo_user)
        response = self.client.post(
            "/api/v1/webhooks/webhooks/",
            {
                "name": f"Alert Hook {uuid.uuid4().hex[:8]}",
                "url": "https://alerts.example.com/hook",
                "secret": f"whsec_{uuid.uuid4().hex}",
                "event_types": [
                    "asset.created",
                    "asset.updated",
                ],
            },
            format="json",
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_200_OK],
            f"Webhook create returned "
            f"{response.status_code}: "
            f"{getattr(response, 'data', '')}",
        )
        body = response.json()
        self.assertIn("id", body)
        self.assertIn("name", body)

    def test_list_webhooks_for_alerts(self):
        """GET /webhooks/webhooks/ -> 200 with list."""
        self.client.force_authenticate(user=self.dpo_user)
        response = self.client.get(
            "/api/v1/webhooks/webhooks/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        results = body.get("results", body)
        self.assertIsInstance(results, list)

    def test_dq_alerting_rule_model_exists(self):
        """DQAlertingRule model can be created with valid config."""
        from hub.apps.dq.models import DQAlertingRule

        rule = DQAlertingRule.objects.create(
            tenant=self.tenant,
            name=f"Test Alert {uuid.uuid4().hex[:8]}",
            metric_type="quality_score",
            threshold=80.0,
            comparison_operator="<",
            severity="HIGH",
            alert_channels=["WEBHOOK"],
            enabled=True,
        )
        self.assertIsNotNone(rule.id)
        self.assertEqual(rule.threshold, 80.0)
        self.assertEqual(rule.severity, "HIGH")

        # Verify evaluate() method exists and is callable
        self.assertTrue(
            hasattr(rule, "evaluate"),
            "DQAlertingRule must have evaluate() method",
        )

    def test_alerts_unauthorized(self):
        """Unauthenticated webhooks -> 401/403."""
        self.client.logout()
        response = self.client.get(
            "/api/v1/webhooks/webhooks/",
        )
        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )


# ------------------------------------------------------------------
# UC-OBS-ADV-004: Monitor Performance Regressions
# ------------------------------------------------------------------
class UCOBSADV004MonitorPerformanceRegressionsTest(
    AdvancedObservabilityTestBase,
):
    """UC-OBS-ADV-004: Monitor Performance Regressions

    Tests observability freshness endpoint (real data freshness
    monitoring) and job performance tracking.
    """

    def test_observability_freshness_dashboard(self):
        """GET /observability/freshness/ -> 200 with metrics."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            "/api/v1/observability/freshness/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertIsInstance(body, dict)

    def test_jobs_list_for_performance_tracking(self):
        """GET /jobs/ -> 200 with list of jobs for perf tracking."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/v1/jobs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        results = body.get("results", body)
        self.assertIsInstance(results, list)

    def test_freshness_unauthorized(self):
        """Unauthenticated freshness -> 401/403."""
        self.client.logout()
        response = self.client.get(
            "/api/v1/observability/freshness/",
        )
        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )

    def test_jobs_unauthorized(self):
        """Unauthenticated jobs -> 401/403."""
        self.client.logout()
        response = self.client.get("/api/v1/jobs/")
        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )
