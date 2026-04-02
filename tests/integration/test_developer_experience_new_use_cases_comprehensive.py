"""
Comprehensive Developer Experience New Use Cases Test Suite (Task 10.1.53.10)

Tests all new Developer Experience use cases:
- UC-DEV-001: Install Plugin
- UC-DEV-002: Create Custom Plugin
- UC-DEV-003: Use CLI Tool
- UC-DEV-004: Access Developer Portal
- UC-DEV-007: Build Custom Connector
- UC-DEV-008: Use Plugin System
- UC-DEV-009: Integrate with Developer Portal

All tests hit real endpoints -- no mocks/stubs.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import KYCStatus, TenantStatus
from hub.apps.testing.billing_support import (
    ensure_tenant_has_active_subscription,
)
from hub.apps.users.models import Role, UserRole
from tests.fixtures.test_data_factories import (
    TenantFactory,
    UserFactory,
)
from tests.utils.test_data_management import TestDatabaseIsolationMixin

User = get_user_model()

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.uc("UC-DEV-001"),
    pytest.mark.uc("UC-DEV-002"),
    pytest.mark.uc("UC-DEV-003"),
    pytest.mark.uc("UC-DEV-004"),
    pytest.mark.uc("UC-DEV-007"),
    pytest.mark.uc("UC-DEV-008"),
    pytest.mark.uc("UC-DEV-009"),
]


class DevExpTestBase(TestCase, TestDatabaseIsolationMixin):
    """Base test class for Developer Experience use cases."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()

        uid = str(uuid.uuid4())[:8]
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

        self.dev_user = UserFactory.create_user(
            tenant=self.tenant,
            email=f"dev-{uid}@example.com",
        )
        UserRole.objects.get_or_create(
            user=self.dev_user, role=self.data_provider_role,
        )


class UCDEV001InstallPluginTest(DevExpTestBase):
    """UC-DEV-001: Install Plugin -- discover plugins."""

    def test_plugin_marketplace_list(self):
        """GET /plugins/ -> 200 with list of plugins."""
        self.client.force_authenticate(user=self.dev_user)
        response = self.client.get("/api/v1/developer/plugins/")
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
        )
        data = response.json()
        results = (
            data.get("results", data)
            if isinstance(data, dict) else data
        )
        self.assertIsInstance(results, list)

    def test_plugin_list_allows_anonymous_access(self):
        """Plugin marketplace is public (AllowAny) -> 200."""
        self.client.logout()
        response = self.client.get("/api/v1/developer/plugins/")
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
            "Plugin list is a public endpoint (AllowAny)",
        )


class UCDEV002CreateCustomPluginTest(DevExpTestBase):
    """UC-DEV-002: Create Custom Plugin -- not implemented."""

    def test_plugin_creation_returns_405(self):
        """POST to plugins -> 405 (ReadOnlyModelViewSet)."""
        self.client.force_authenticate(user=self.dev_user)
        response = self.client.post(
            "/api/v1/developer/plugins/",
            {"name": "Custom Plugin", "type": "connector"},
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class UCDEV003UseCLIToolTest(DevExpTestBase):
    """UC-DEV-003: Use CLI Tool

    Verifies the API endpoints that the CLI tool relies on:
    asset list, contract list, and DQ runs.
    """

    def test_cli_asset_list_endpoint(self):
        """GET /assets/ -> 200 (primary CLI endpoint)."""
        self.client.force_authenticate(user=self.dev_user)
        url = reverse("asset-list")
        response = self.client.get(url)
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
        )
        data = response.json()
        results = data.get("results", data)
        self.assertIsInstance(results, list)

    def test_cli_contract_list_endpoint(self):
        """GET /contracts/ -> 200 (CLI contracts command)."""
        self.client.force_authenticate(user=self.dev_user)
        url = reverse("contract-list")
        response = self.client.get(url)
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
        )

    def test_cli_dq_runs_endpoint(self):
        """GET /dq/runs/ -> 200 (CLI dq command)."""
        self.client.force_authenticate(user=self.dev_user)
        url = reverse("dq-run-list")
        response = self.client.get(url)
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
        )


class UCDEV004AccessDeveloperPortalTest(DevExpTestBase):
    """UC-DEV-004: Access Developer Portal."""

    def test_developer_portal_plugins(self):
        """GET /plugins/ -> 200 with list."""
        self.client.force_authenticate(user=self.dev_user)
        response = self.client.get("/api/v1/developer/plugins/")
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
        )

    def test_developer_portal_sdk_docs(self):
        """GET /sdk/ -> 200 with sdks key."""
        self.client.force_authenticate(user=self.dev_user)
        response = self.client.get("/api/v1/developer/sdk/")
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
        )
        data = response.json()
        self.assertIn("sdks", data)
        self.assertIsInstance(data["sdks"], list)

    def test_developer_portal_openapi_schema(self):
        """GET /openapi.json -> 200 with OpenAPI structure."""
        self.client.force_authenticate(user=self.dev_user)
        response = self.client.get("/api/v1/openapi.json")
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
        )
        data = response.json()
        self.assertIn("openapi", data)
        self.assertIn("paths", data)


class UCDEV007BuildCustomConnectorTest(DevExpTestBase):
    """UC-DEV-007: Build Custom Connector."""

    def test_list_connectors(self):
        """GET connectors -> 200 with connectors list."""
        self.client.force_authenticate(user=self.dev_user)
        url = "/api/v1/integrations/marketplace/connectors/"
        response = self.client.get(url)
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
        )
        data = response.json()
        self.assertIn("connectors", data)
        self.assertIsInstance(data["connectors"], list)
        self.assertGreaterEqual(
            len(data["connectors"]), 1,
            "At least one connector type must be registered",
        )

    def test_get_connector_detail(self):
        """GET connectors/{type}/ -> 200 with type field."""
        self.client.force_authenticate(user=self.dev_user)
        url = "/api/v1/integrations/marketplace/connectors/"
        list_resp = self.client.get(url)
        self.assertEqual(
            list_resp.status_code, status.HTTP_200_OK,
        )
        connectors = list_resp.json().get("connectors", [])
        self.assertGreater(len(connectors), 0)
        ctype = connectors[0].get("type")
        self.assertIsNotNone(ctype)

        detail_resp = self.client.get(f"{url}{ctype}/")
        self.assertEqual(
            detail_resp.status_code, status.HTTP_200_OK,
        )
        self.assertEqual(detail_resp.json()["type"], ctype)


class UCDEV008UsePluginSystemTest(DevExpTestBase):
    """UC-DEV-008: Use Plugin System."""

    def test_plugins_list(self):
        """GET /plugins/ -> 200 with list."""
        self.client.force_authenticate(user=self.dev_user)
        response = self.client.get("/api/v1/developer/plugins/")
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
        )

    def test_plugins_filter_by_category(self):
        """GET /plugins/?category=CONNECTOR -> 200."""
        self.client.force_authenticate(user=self.dev_user)
        response = self.client.get(
            "/api/v1/developer/plugins/?category=CONNECTOR",
        )
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
        )

    def test_plugins_retrieve(self):
        """GET /plugins/{id}/ -> 200 with matching id."""
        from hub.apps.developer.models import (
            Plugin, PluginCategory, PluginStatus,
        )

        self.client.force_authenticate(user=self.dev_user)
        plugin = Plugin.objects.filter(
            status=PluginStatus.AVAILABLE,
        ).first()
        if not plugin:
            plugin = Plugin.objects.create(
                name="Test Plugin for Retrieve",
                description="Created by test suite",
                category=PluginCategory.CONNECTOR,
                status=PluginStatus.AVAILABLE,
                version="1.0.0",
                author="test-suite",
            )
        response = self.client.get(
            f"/api/v1/developer/plugins/{plugin.id}/",
        )
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
        )
        self.assertEqual(
            response.json().get("id"), str(plugin.id),
        )


class UCDEV009IntegrateWithDeveloperPortalTest(DevExpTestBase):
    """UC-DEV-009: Integrate with Developer Portal."""

    def test_sdk_documentation_list(self):
        """GET /sdk/ -> 200 with sdks list."""
        self.client.force_authenticate(user=self.dev_user)
        response = self.client.get("/api/v1/developer/sdk/")
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
        )
        data = response.json()
        self.assertIn("sdks", data)
        self.assertIsInstance(data["sdks"], list)

    def test_sdk_documentation_by_language(self):
        """GET /sdk/?language=python -> 200 or data-dependent 404."""
        self.client.force_authenticate(user=self.dev_user)
        response = self.client.get(
            "/api/v1/developer/sdk/?language=python",
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND],
        )
        data = response.json()
        if response.status_code == status.HTTP_200_OK:
            self.assertIn("language", data)
            self.assertIn("sdk_name", data)
        else:
            self.assertTrue(
                "detail" in data or "error" in data,
            )

    def test_portal_plugins_and_sdk_accessible(self):
        """Both plugins and SDK docs are accessible."""
        self.client.force_authenticate(user=self.dev_user)
        p_resp = self.client.get("/api/v1/developer/plugins/")
        s_resp = self.client.get("/api/v1/developer/sdk/")
        self.assertEqual(
            p_resp.status_code, status.HTTP_200_OK,
        )
        self.assertEqual(
            s_resp.status_code, status.HTTP_200_OK,
        )
