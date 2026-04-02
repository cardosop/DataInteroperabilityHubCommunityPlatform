"""
Comprehensive Trust Signals Config API Integration Tests

Tests trust signals configuration API with real DB and real services.
No mocks of hub/services/DB per development best practices.

Coverage:
- Create (POST), Read (list + retrieve), Update (PUT/PATCH), Delete (DELETE)
- Tenant isolation (user from tenant A cannot see/update/delete tenant B's configs)
- UC-MKT-ADV-003, UC-MKT-ADV-005.
"""

import uuid

import pytest

pytestmark = pytest.mark.slow
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant, TenantConfig, TenantStatus
from hub.apps.users.models import User, UserStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.integration,
    pytest.mark.marketplace,
    pytest.mark.timeout(120),
    pytest.mark.uc("UC-MKT-ADV-003"),
    pytest.mark.uc("UC-MKT-ADV-005"),
]


class TrustSignalsConfigAPIsComprehensiveTest(TestCase):
    """Integration tests for /api/v1/marketplace/config/trust-signals/ CRUD and tenant isolation."""

    reset_sequences = False
    serialized_rollback = False

    @classmethod
    def _fixture_teardown(cls):
        """Skip database flush for integration tests (avoid FK locks; use transaction rollback)."""
        pass

    def setUp(self):
        self.client = APIClient()
        unique_id = str(uuid.uuid4())[:8]

        self.tenant1 = Tenant.objects.create(
            name=f"Trust Signals Tenant 1 {unique_id}",
            slug=f"trust-signals-tenant-1-{unique_id}",
            status=TenantStatus.ACTIVE,
        )
        self.tenant2 = Tenant.objects.create(
            name=f"Trust Signals Tenant 2 {unique_id}",
            slug=f"trust-signals-tenant-2-{unique_id}",
            status=TenantStatus.ACTIVE,
        )

        self.user1 = User.objects.create_user(
            email=f"trust1-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant1,
            status=UserStatus.ACTIVE,
        )
        self.user2 = User.objects.create_user(
            email=f"trust2-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant2,
            status=UserStatus.ACTIVE,
        )

        ensure_tenant_has_active_subscription(self.tenant1)
        ensure_tenant_has_active_subscription(self.tenant2)

    def _url_list(self):
        return "/api/v1/marketplace/config/trust-signals/"

    def _url_detail(self, pk):
        return f"/api/v1/marketplace/config/trust-signals/{pk}/"

    def test_create_trust_signal_config_success(self):
        """POST creates a trust signal config (badge or quality_sla) and returns 201."""
        self.client.force_authenticate(user=self.user1)

        data = {
            "name": "quality_verified",
            "kind": "badge",
            "config": {"description": "Quality verified by DQ run"},
        }
        response = self.client.post(self._url_list(), data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["name"], "quality_verified")
        self.assertEqual(response.data["kind"], "badge")
        self.assertEqual(response.data["config"], {"description": "Quality verified by DQ run"})
        self.assertEqual(response.data["tenant_id"], str(self.tenant1.id))

    def test_create_quality_sla_config_success(self):
        """POST creates a quality SLA trust signal config."""
        self.client.force_authenticate(user=self.user1)

        data = {
            "name": "sla_99",
            "kind": "quality_sla",
            "config": {"availability": 99.9, "freshness_hours": 24},
        }
        response = self.client.post(self._url_list(), data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "sla_99")
        self.assertEqual(response.data["kind"], "quality_sla")
        self.assertEqual(response.data["config"]["availability"], 99.9)

    def test_list_trust_signal_configs(self):
        """GET list returns only current tenant's configs (paginated or list)."""
        from hub.apps.marketplace.models import TrustSignalConfig

        TrustSignalConfig.objects.create(
            tenant=self.tenant1,
            name="badge_a",
            kind="badge",
            config={"description": "Badge A"},
        )
        TrustSignalConfig.objects.create(
            tenant=self.tenant1,
            name="sla_b",
            kind="quality_sla",
            config={"availability": 99.5},
        )
        TrustSignalConfig.objects.create(
            tenant=self.tenant2,
            name="tenant2_only",
            kind="badge",
            config={},
        )

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self._url_list())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Paginated response has 'results' or direct list
        data = response.data
        if isinstance(data, dict) and "results" in data:
            items = data["results"]
        else:
            items = data if isinstance(data, list) else []
        names = [item["name"] for item in items]
        self.assertIn("badge_a", names)
        self.assertIn("sla_b", names)
        self.assertNotIn("tenant2_only", names)

    def test_retrieve_trust_signal_config(self):
        """GET detail returns the config when it belongs to the request tenant."""
        from hub.apps.marketplace.models import TrustSignalConfig

        config = TrustSignalConfig.objects.create(
            tenant=self.tenant1,
            name="retrieve_me",
            kind="badge",
            config={"key": "value"},
        )

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self._url_detail(config.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(config.id))
        self.assertEqual(response.data["name"], "retrieve_me")
        self.assertEqual(response.data["config"]["key"], "value")

    def test_update_trust_signal_config(self):
        """PUT/PATCH updates the config and returns 200."""
        from hub.apps.marketplace.models import TrustSignalConfig

        config = TrustSignalConfig.objects.create(
            tenant=self.tenant1,
            name="update_me",
            kind="badge",
            config={"old": True},
        )

        self.client.force_authenticate(user=self.user1)
        response = self.client.patch(
            self._url_detail(config.id),
            {"config": {"new": True, "description": "Updated"}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        config.refresh_from_db()
        self.assertEqual(config.config, {"new": True, "description": "Updated"})

    def test_delete_trust_signal_config(self):
        """DELETE removes the config and returns 204."""
        from hub.apps.marketplace.models import TrustSignalConfig

        config = TrustSignalConfig.objects.create(
            tenant=self.tenant1,
            name="delete_me",
            kind="badge",
            config={},
        )

        self.client.force_authenticate(user=self.user1)
        response = self.client.delete(self._url_detail(config.id))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TrustSignalConfig.objects.filter(id=config.id).exists())

    def test_tenant_isolation_list(self):
        """User from tenant1 does not see tenant2's configs in list."""
        from hub.apps.marketplace.models import TrustSignalConfig

        TrustSignalConfig.objects.create(
            tenant=self.tenant2,
            name="tenant2_secret",
            kind="badge",
            config={},
        )

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self._url_list())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        items = data.get("results", data) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        names = [item["name"] for item in items] if items else []
        self.assertNotIn("tenant2_secret", names)

    def test_tenant_isolation_retrieve(self):
        """User from tenant1 gets 404 when retrieving tenant2's config."""
        from hub.apps.marketplace.models import TrustSignalConfig

        config2 = TrustSignalConfig.objects.create(
            tenant=self.tenant2,
            name="tenant2_only",
            kind="badge",
            config={},
        )

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self._url_detail(config2.id))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_tenant_isolation_update(self):
        """User from tenant1 gets 404 when updating tenant2's config."""
        from hub.apps.marketplace.models import TrustSignalConfig

        config2 = TrustSignalConfig.objects.create(
            tenant=self.tenant2,
            name="tenant2_only",
            kind="badge",
            config={},
        )

        self.client.force_authenticate(user=self.user1)
        response = self.client.patch(
            self._url_detail(config2.id),
            {"name": "hacked"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        config2.refresh_from_db()
        self.assertEqual(config2.name, "tenant2_only")

    def test_tenant_isolation_delete(self):
        """User from tenant1 gets 404 when deleting tenant2's config."""
        from hub.apps.marketplace.models import TrustSignalConfig

        config2 = TrustSignalConfig.objects.create(
            tenant=self.tenant2,
            name="tenant2_only",
            kind="badge",
            config={},
        )

        self.client.force_authenticate(user=self.user1)
        response = self.client.delete(self._url_detail(config2.id))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(TrustSignalConfig.objects.filter(id=config2.id).exists())

    def test_unauthenticated_list_returns_401(self):
        """GET list without auth returns 401."""
        response = self.client.get(self._url_list())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_create_returns_401(self):
        """POST without auth returns 401."""
        response = self.client.post(
            self._url_list(),
            {"name": "x", "kind": "badge", "config": {}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_duplicate_name_returns_400(self):
        """POST with same (tenant, name) returns 400 and clear error (no 500)."""
        from hub.apps.marketplace.models import TrustSignalConfig

        TrustSignalConfig.objects.create(
            tenant=self.tenant1,
            name="already_taken",
            kind="badge",
            config={},
        )
        self.client.force_authenticate(user=self.user1)

        response = self.client.post(
            self._url_list(),
            {"name": "already_taken", "kind": "badge", "config": {}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertEqual(response.data.get("code"), "DUPLICATE_NAME")
        self.assertEqual(
            TrustSignalConfig.objects.filter(tenant=self.tenant1, name="already_taken").count(),
            1,
        )

    def test_create_missing_required_fields_returns_400(self):
        """POST without name or kind returns 400 (serializer validation)."""
        self.client.force_authenticate(user=self.user1)

        missing_name = self.client.post(
            self._url_list(),
            {"kind": "badge", "config": {}},
            format="json",
        )
        self.assertEqual(missing_name.status_code, status.HTTP_400_BAD_REQUEST)

        missing_kind = self.client.post(
            self._url_list(),
            {"name": "x", "config": {}},
            format="json",
        )
        self.assertEqual(missing_kind.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_duplicate_name_returns_400(self):
        """PATCH name to an existing name in same tenant returns 400."""
        from hub.apps.marketplace.models import TrustSignalConfig

        TrustSignalConfig.objects.create(
            tenant=self.tenant1,
            name="existing",
            kind="badge",
            config={},
        )
        other = TrustSignalConfig.objects.create(
            tenant=self.tenant1,
            name="other",
            kind="badge",
            config={},
        )
        self.client.force_authenticate(user=self.user1)

        response = self.client.patch(
            self._url_detail(other.id),
            {"name": "existing"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("code"), "DUPLICATE_NAME")
        other.refresh_from_db()
        self.assertEqual(other.name, "other")

    def test_trust_signals_disabled_list_returns_empty(self):
        """Phase 11: When trust_signals_enabled=False, list returns 200 with empty results."""
        from hub.apps.marketplace.models import TrustSignalConfig

        TrustSignalConfig.objects.create(
            tenant=self.tenant1,
            name="existing_badge",
            kind="badge",
            config={},
        )
        TenantConfig.objects.create(tenant=self.tenant1, trust_signals_enabled=False)

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self._url_list())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        items = data.get("results", data) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        self.assertEqual(len(items), 0)

    def test_trust_signals_disabled_create_returns_403(self):
        """Phase 11: When trust_signals_enabled=False, create returns 403 with TRUST_SIGNALS_DISABLED."""
        TenantConfig.objects.create(tenant=self.tenant1, trust_signals_enabled=False)

        self.client.force_authenticate(user=self.user1)
        response = self.client.post(
            self._url_list(),
            {"name": "blocked", "kind": "badge", "config": {}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("code"), "TRUST_SIGNALS_DISABLED")
        self.assertIn("Trust signals are disabled", response.data.get("error", ""))

    def test_trust_signals_disabled_retrieve_returns_403(self):
        """Phase 11: When trust_signals_enabled=False, retrieve returns 403 with TRUST_SIGNALS_DISABLED."""
        from hub.apps.marketplace.models import TrustSignalConfig

        config = TrustSignalConfig.objects.create(
            tenant=self.tenant1,
            name="retrieve_blocked",
            kind="badge",
            config={},
        )
        TenantConfig.objects.create(tenant=self.tenant1, trust_signals_enabled=False)

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self._url_detail(config.id))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("code"), "TRUST_SIGNALS_DISABLED")

    def test_trust_signals_disabled_update_returns_403(self):
        """Phase 11: When trust_signals_enabled=False, update returns 403 with TRUST_SIGNALS_DISABLED."""
        from hub.apps.marketplace.models import TrustSignalConfig

        config = TrustSignalConfig.objects.create(
            tenant=self.tenant1,
            name="update_blocked",
            kind="badge",
            config={},
        )
        TenantConfig.objects.create(tenant=self.tenant1, trust_signals_enabled=False)

        self.client.force_authenticate(user=self.user1)
        response = self.client.patch(
            self._url_detail(config.id),
            {"config": {"new": True}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("code"), "TRUST_SIGNALS_DISABLED")
        config.refresh_from_db()
        self.assertEqual(config.config, {})

    def test_trust_signals_disabled_delete_returns_403(self):
        """Phase 11: When trust_signals_enabled=False, delete returns 403 with TRUST_SIGNALS_DISABLED."""
        from hub.apps.marketplace.models import TrustSignalConfig

        config = TrustSignalConfig.objects.create(
            tenant=self.tenant1,
            name="delete_blocked",
            kind="badge",
            config={},
        )
        TenantConfig.objects.create(tenant=self.tenant1, trust_signals_enabled=False)

        self.client.force_authenticate(user=self.user1)
        response = self.client.delete(self._url_detail(config.id))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("code"), "TRUST_SIGNALS_DISABLED")
        self.assertTrue(TrustSignalConfig.objects.filter(id=config.id).exists())
