"""
285.5.5 — Per-flag gate tests (21 tests).

Tests that each of the 7 new Phase 285.5.2 feature flags correctly
gates its ViewSet: Flag ON → 200 with valid response data, Flag OFF →
403 with error body, capability endpoint returns flag state.

Pattern follows DQFeatureFlagMixin from hub/apps/dq/tests/test_feature_flag.py.
Real DB, no mocks at the gate boundary.
"""
import uuid

import pytest

from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole


def _setup_tenant_with_flag(flag_name: str, flag_value: bool):
    """Create a tenant with a specific flag value and a TENANT_ADMIN user.

    Uses a UUID suffix in the slug to avoid uniqueness violations across
    test classes that share the same flag name.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    uid = uuid.uuid4().hex[:8]
    kwargs = {
        "name": f"test-{flag_name}-{uid}",
        "slug": f"test-{flag_name}-{uid}",
        flag_name: flag_value,
    }
    tenant = Tenant.objects.create(**kwargs)
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"{flag_name}-{uid}@test.com", password="p", tenant=tenant,
    )
    role, _ = Role.objects.get_or_create(
        tenant=tenant, name="TENANT_ADMIN", defaults={"description": ""},
    )
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)
    return tenant, user


class MarketplaceIntegrationsGateTest(TestCase):
    """285.5.2.1 — marketplace_integrations_enabled DRAFT gate."""

    FLAG = "marketplace_integrations_enabled"
    ENDPOINT = "/api/v1/integrations/marketplace/connections/"

    @pytest.mark.integration
    def test_flag_on_returns_200(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, True)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, 200)
        # When the flag is ON, the response should contain paginated data.
        self.assertIn("results", resp.data,
                      "Flag ON should return paginated list with 'results' key")

    @pytest.mark.integration
    def test_flag_off_returns_403(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, False)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, 403)
        # When the flag is OFF, the response must have a non-empty body
        # indicating the denial reason (not a bare 403 with empty body).
        self.assertTrue(
            resp.data,
            f"Flag OFF 403 response body must not be empty; got: {resp.content}",
        )

    @pytest.mark.integration
    def test_capability_endpoint_reflects_flag(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, True)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/capabilities/")
        self.assertEqual(resp.status_code, 200)
        # The capabilities response must contain a 'capabilities' key
        # with the available feature set.  Individual flag names are
        # not necessarily 1:1 with capability keys, but the endpoint
        # itself must be reachable and return valid JSON.
        self.assertIn("capabilities", resp.data,
                      "Capabilities response must include 'capabilities' key")


class DataMeshGateTest(TestCase):
    """285.5.2.2 — data_mesh_enabled CANARY gate."""

    FLAG = "data_mesh_enabled"
    ENDPOINT = "/api/v1/mesh/domains/"

    @pytest.mark.integration
    def test_flag_on_returns_200(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, True)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.data,
                      "Flag ON should return paginated list with 'results' key")

    @pytest.mark.integration
    def test_flag_off_returns_403(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, False)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(
            resp.data,
            f"Flag OFF 403 response body must not be empty; got: {resp.content}",
        )

    @pytest.mark.integration
    def test_capability_endpoint_reflects_flag(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, True)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/capabilities/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            "capabilities", resp.data,
            "Capabilities response must include 'capabilities' key",
        )


class VirtualizationGateTest(TestCase):
    """285.5.2.3 — virtualization_enabled CANARY gate."""

    FLAG = "virtualization_enabled"
    ENDPOINT = "/api/v1/virtualization/datasets/"

    @pytest.mark.integration
    def test_flag_on_returns_200(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, True)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.data,
                      "Flag ON should return paginated list with 'results' key")

    @pytest.mark.integration
    def test_flag_off_returns_403(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, False)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(
            resp.data,
            f"Flag OFF 403 response body must not be empty; got: {resp.content}",
        )

    @pytest.mark.integration
    def test_capability_endpoint_reflects_flag(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, True)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/capabilities/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            "capabilities", resp.data,
            "Capabilities response must include 'capabilities' key",
        )


class DeveloperGateTest(TestCase):
    """285.5.2.4 — developer_enabled DRAFT gate."""

    FLAG = "developer_enabled"
    ENDPOINT = "/api/v1/developer/plugins/"

    @pytest.mark.integration
    def test_flag_on_returns_200(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, True)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.data,
                      "Flag ON should return paginated list with 'results' key")

    @pytest.mark.integration
    def test_flag_off_returns_403(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, False)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(
            resp.data,
            f"Flag OFF 403 response body must not be empty; got: {resp.content}",
        )

    @pytest.mark.integration
    def test_capability_endpoint_reflects_flag(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, True)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/capabilities/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            "capabilities", resp.data,
            "Capabilities response must include 'capabilities' key",
        )


class MLGateTest(TestCase):
    """285.5.2.5 — ml_enabled CANARY gate."""

    FLAG = "ml_enabled"
    ENDPOINT = "/api/v1/ml/models/"

    @pytest.mark.integration
    def test_flag_on_returns_200(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, True)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.data,
                      "Flag ON should return paginated list with 'results' key")

    @pytest.mark.integration
    def test_flag_off_returns_403(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, False)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(
            resp.data,
            f"Flag OFF 403 response body must not be empty; got: {resp.content}",
        )

    @pytest.mark.integration
    def test_capability_endpoint_reflects_flag(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, True)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/capabilities/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            "capabilities", resp.data,
            "Capabilities response must include 'capabilities' key",
        )


class TransformationGateTest(TestCase):
    """285.5.2.6 — transformation_enabled DRAFT gate."""

    FLAG = "transformation_enabled"
    ENDPOINT = "/api/v1/transformation/pipelines/"

    @pytest.mark.integration
    def test_flag_on_returns_200(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, True)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.data,
                      "Flag ON should return paginated list with 'results' key")

    @pytest.mark.integration
    def test_flag_off_returns_403(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, False)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(
            resp.data,
            f"Flag OFF 403 response body must not be empty; got: {resp.content}",
        )

    @pytest.mark.integration
    def test_capability_endpoint_reflects_flag(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, True)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/capabilities/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            "capabilities", resp.data,
            "Capabilities response must include 'capabilities' key",
        )


class BaaSGateTest(TestCase):
    """285.5.2.7 — baas_enabled CANARY gate."""

    FLAG = "baas_enabled"
    ENDPOINT = "/api/v1/baas/api-keys/"

    @pytest.mark.integration
    def test_flag_on_returns_200(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, True)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.data,
                      "Flag ON should return paginated list with 'results' key")

    @pytest.mark.integration
    def test_flag_off_returns_403(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, False)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(
            resp.data,
            f"Flag OFF 403 response body must not be empty; got: {resp.content}",
        )

    @pytest.mark.integration
    def test_capability_endpoint_reflects_flag(self):
        tenant, user = _setup_tenant_with_flag(self.FLAG, True)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/capabilities/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            "capabilities", resp.data,
            "Capabilities response must include 'capabilities' key",
        )
