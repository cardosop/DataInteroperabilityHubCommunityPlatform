"""
Phase 277.B.106 — dynamic RESOURCE_COUNTERS /me/usage/ endpoint tests.
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.billing.limit_registry import RESOURCE_COUNTERS
from hub.apps.tenants.models import Tenant, TenantPlan, TenantStatus

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


class MeUsageEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(
            name="UsageTest", slug="usage-test", status=TenantStatus.ACTIVE,
        )
        cls.plan = TenantPlan.objects.create(
            name="Test Plan", slug="test-plan", tier="PRO", is_active=True,
            limits_json={
                "max_assets": 100, "max_datasets": 50,
                "max_webhooks": 10, "max_contracts": 20,
                "max_users": 25, "max_marketplace_listings": 5,
                "max_scheduled_ingestions": 10, "max_scheduled_exports": 10,
                "max_storage_gb": 50, "max_api_calls_per_month": 10000,
            },
        )
        cls.user = User.objects.create_user(
            email="usage-test@example.com", password="testpass",
            tenant=cls.tenant,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    # ── Response shape ──────────────────────────────────────────

    def test_returns_200(self):
        resp = self.client.get("/api/v1/tenants/me/usage/")
        assert resp.status_code == 200

    def test_response_includes_plan_limits(self):
        resp = self.client.get("/api/v1/tenants/me/usage/")
        data = resp.json()
        assert "plan_limits" in data
        assert data["plan_limits"]["max_assets"] == 100

    def test_response_includes_usage_percentages(self):
        resp = self.client.get("/api/v1/tenants/me/usage/")
        data = resp.json()
        assert "usage_percentages" in data
        assert isinstance(data["usage_percentages"], dict)
        # Empty tenant — all percentages should be 0
        for key, pct in data["usage_percentages"].items():
            if pct is not None:
                assert pct == 0.0, f"{key} should be 0.0 but got {pct}"

    def test_response_includes_quota_warnings(self):
        resp = self.client.get("/api/v1/tenants/me/usage/")
        data = resp.json()
        assert "quota_warnings" in data
        assert isinstance(data["quota_warnings"], dict)

    def test_response_includes_plan_info(self):
        resp = self.client.get("/api/v1/tenants/me/usage/")
        data = resp.json()
        assert "plan_slug" in data
        assert "plan_tier" in data

    # ── Dynamic RESOURCE_COUNTERS coverage ──────────────────────

    def test_all_known_limit_keys_in_usage_percentages(self):
        """Every limit in the plan should appear in usage_percentages."""
        resp = self.client.get("/api/v1/tenants/me/usage/")
        data = resp.json()
        limits = data["plan_limits"]
        percentages = data["usage_percentages"]
        for limit_key in limits:
            assert limit_key in percentages, (
                f"Missing usage_percentage for limit_key={limit_key}"
            )

    def test_usage_keys_follow_naming_convention(self):
        """Dynamic keys: max_assets → asset_usage."""
        resp = self.client.get("/api/v1/tenants/me/usage/")
        data = resp.json()
        for limit_key in data["plan_limits"]:
            usage_key = limit_key.replace("max_", "") + "_usage"
            assert usage_key in data, (
                f"Missing dynamic usage key: {usage_key}"
            )

    def test_unlimited_keys_return_none(self):
        """max_limit=None → usage_percentage=None (unlimited)."""
        resp = self.client.get("/api/v1/tenants/me/usage/")
        data = resp.json()
        for limit_key, max_val in data["plan_limits"].items():
            if max_val is None:
                assert data["usage_percentages"][limit_key] is None, (
                    f"Unlimited key {limit_key} should have percentage=None"
                )

    # ── quota_warnings correctness ──────────────────────────────

    def test_quota_warnings_empty_when_all_zero(self):
        """Empty tenant → no warnings."""
        resp = self.client.get("/api/v1/tenants/me/usage/")
        data = resp.json()
        assert data["quota_warnings"] == {}

    def test_quota_warnings_flags_warn_threshold(self):
        """Simulate >=80% usage on one key → quota_warnings fires."""
        from hub.apps.assets.models import Asset

        # Create 90 assets (90% of max_assets=100)
        for i in range(90):
            Asset.objects.create(
                tenant=self.tenant, name=f"asset-{i}", key=f"asset-{i}",
            )

        resp = self.client.get("/api/v1/tenants/me/usage/")
        data = resp.json()
        assert "max_assets" in data["quota_warnings"], (
            f"Expected quota_warning for max_assets at 90%, got {data['quota_warnings']}"
        )

    # ── Caching ──────────────────────────────────────────────────

    def test_cached_response_is_identical(self):
        """Two calls within cache TTL return the same data."""
        from django.core.cache import cache

        # Clear any existing cache
        cache.delete(f"tenant_usage:{self.tenant.id}")

        resp1 = self.client.get("/api/v1/tenants/me/usage/")
        data1 = resp1.json()

        # Verify cache was set
        cached = cache.get(f"tenant_usage:{self.tenant.id}")
        assert cached is not None, "Cache was not populated after first call"

        resp2 = self.client.get("/api/v1/tenants/me/usage/")
        data2 = resp2.json()

        # usage_percentages should be identical (same underlying data)
        assert data1["usage_percentages"] == data2["usage_percentages"]

    # ── Authentication ──────────────────────────────────────────

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        resp = client.get("/api/v1/tenants/me/usage/")
        assert resp.status_code == 401

    # ── Usage data contains dynamic counter keys ─────────────────

    def test_response_contains_dynamic_counter_keys(self):
        """Response body includes {limit_key}_usage for every limit."""
        resp = self.client.get("/api/v1/tenants/me/usage/")
        data = resp.json()
        limit_keys_in_plan = list(data["plan_limits"].keys())
        for limit_key in limit_keys_in_plan:
            usage_key = limit_key.replace("max_", "") + "_usage"
            assert usage_key in data, (
                f"Missing {usage_key} in response for {limit_key}"
            )
