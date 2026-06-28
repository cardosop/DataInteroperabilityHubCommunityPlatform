"""
Comprehensive tests for developer experience endpoints (plugins, SDK).

Tests cover:
- Unit tests for plugin listing
- Unit tests for SDK documentation
- Integration tests
- Security tests (public endpoints)
- Performance tests
- Error handling
"""

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.developer.models import (
    Plugin,
    PluginCategory,
    PluginStatus,
    SDKDocumentation,
    SDKLanguage,
)

pytestmark = pytest.mark.django_db(transaction=True)


class PluginViewSetTest(TestCase):
    """Test plugin marketplace endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create test plugins
        self.plugin1 = Plugin.objects.create(
            name="Test Plugin 1",
            description="Test plugin description 1",
            version="1.0.0",
            author="Test Author",
            category=PluginCategory.CONNECTOR,
            status=PluginStatus.AVAILABLE,
            download_count=100,
            rating=4.5,
        )

        self.plugin2 = Plugin.objects.create(
            name="Test Plugin 2",
            description="Test plugin description 2",
            version="2.0.0",
            author="Test Author 2",
            category=PluginCategory.TRANSFORMER,
            status=PluginStatus.AVAILABLE,
            download_count=50,
            rating=4.0,
        )

        self.plugin3 = Plugin.objects.create(
            name="Deprecated Plugin",
            description="Deprecated plugin",
            version="0.1.0",
            author="Test Author",
            category=PluginCategory.OTHER,
            status=PluginStatus.DEPRECATED,
            download_count=10,
            rating=3.0,
        )

    def test_list_plugins_public(self):
        """Test plugin listing is public (no auth required)"""
        response = self.client.get("/api/v1/developer/plugins/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response might be a list (no pagination) or dict with 'results' (pagination)
        data = response.data
        if isinstance(data, dict) and "results" in data:
            plugin_list = data["results"]
        else:
            self.assertIsInstance(data, list, "Expected list or paginated dict response")
            plugin_list = data

        # Should only return available plugins by default
        self.assertGreater(len(plugin_list), 0, "Expected at least one plugin in response")
        plugin_names = [p["name"] for p in plugin_list]
        self.assertIn("Test Plugin 1", plugin_names)
        self.assertIn("Test Plugin 2", plugin_names)
        self.assertNotIn("Deprecated Plugin", plugin_names)

    def test_list_plugins_filter_by_category(self):
        """Test filtering plugins by category"""
        response = self.client.get("/api/v1/developer/plugins/?category=CONNECTOR")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        plugin_list = data["results"] if isinstance(data, dict) and "results" in data else data
        self.assertGreater(len(plugin_list), 0, "Expected at least one CONNECTOR plugin")
        for plugin in plugin_list:
            self.assertEqual(plugin["category"], "CONNECTOR")

    def test_list_plugins_search(self):
        """Test searching plugins"""
        response = self.client.get("/api/v1/developer/plugins/?search=Plugin 1")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        plugin_list = data["results"] if isinstance(data, dict) and "results" in data else data
        self.assertGreater(len(plugin_list), 0, "Expected search to return at least one plugin")
        plugin_names = [p["name"] for p in plugin_list]
        self.assertIn("Test Plugin 1", plugin_names)
        self.assertNotIn("Test Plugin 2", plugin_names)

    def test_list_plugins_sort_by_popularity(self):
        """Test sorting plugins by popularity"""
        response = self.client.get("/api/v1/developer/plugins/?sort=popularity")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        plugin_list = data["results"] if isinstance(data, dict) and "results" in data else data
        self.assertGreater(len(plugin_list), 1, "Expected at least 2 plugins to verify sort order")
        downloads = [p["download_count"] for p in plugin_list]
        self.assertEqual(downloads, sorted(downloads, reverse=True))

    def test_list_plugins_sort_by_rating(self):
        """Test sorting plugins by rating"""
        response = self.client.get("/api/v1/developer/plugins/?sort=rating")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        plugin_list = data["results"] if isinstance(data, dict) and "results" in data else data
        self.assertGreater(len(plugin_list), 1, "Expected at least 2 plugins to verify sort order")
        ratings = [p["rating"] or 0 for p in plugin_list]
        self.assertEqual(ratings, sorted(ratings, reverse=True))

    def test_retrieve_plugin(self):
        """Test retrieving a single plugin"""
        response = self.client.get(f"/api/v1/developer/plugins/{self.plugin1.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Test Plugin 1")
        self.assertEqual(response.data["version"], "1.0.0")
        self.assertEqual(response.data["category"], "CONNECTOR")


class SDKDocumentationViewSetTest(TestCase):
    """Test SDK documentation endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create test SDK documentation
        self.python_sdk = SDKDocumentation.objects.create(
            language=SDKLanguage.PYTHON,
            version="1.0.0",
            documentation="# Python SDK\n\nPython SDK for Data Hub API.",
            installation="pip install datahub-sdk",
            quick_start="from datahub import DataHubClient\n\nclient = DataHubClient(api_key='your-key')",
            examples_json=[
                {
                    "title": "List Assets",
                    "code": "assets = client.assets.list()\nfor asset in assets:\n    print(asset.name)",
                    "description": "List all assets",
                }
            ],
            api_reference_json={
                "endpoints": [
                    {"path": "/api/v1/assets/", "method": "GET", "description": "List assets"}
                ]
            },
            is_active=True,
        )

        self.js_sdk = SDKDocumentation.objects.create(
            language=SDKLanguage.JAVASCRIPT,
            version="1.0.0",
            documentation="# JavaScript SDK\n\nJavaScript SDK for Data Hub API.",
            installation="npm install @datahub/sdk",
            quick_start="import { DataHubClient } from '@datahub/sdk';\n\nconst client = new DataHubClient({ apiKey: 'your-key' });",
            examples_json=[],
            api_reference_json={},
            is_active=True,
        )

    def test_list_sdk_all_languages(self):
        """Test listing all SDK documentation"""
        response = self.client.get("/api/v1/developer/sdk/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("sdks", response.data)
        self.assertEqual(len(response.data["sdks"]), 2)

    def test_list_sdk_specific_language(self):
        """Test listing SDK for specific language"""
        response = self.client.get("/api/v1/developer/sdk/?language=python")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("sdk_name", response.data)
        self.assertEqual(response.data["language"], "python")
        self.assertEqual(response.data["version"], "1.0.0")
        self.assertIn("documentation", response.data)
        self.assertIn("installation", response.data)
        self.assertIn("quick_start", response.data)

    def test_list_sdk_with_examples(self):
        """Test SDK documentation includes examples"""
        response = self.client.get("/api/v1/developer/sdk/?language=python&include_examples=true")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("examples", response.data)
        self.assertEqual(len(response.data["examples"]), 1)

    def test_list_sdk_without_examples(self):
        """Test SDK documentation excludes examples when requested"""
        response = self.client.get("/api/v1/developer/sdk/?language=python&include_examples=false")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["examples"], [])

    def test_list_sdk_nonexistent_language(self):
        """Test SDK documentation for nonexistent language"""
        response = self.client.get("/api/v1/developer/sdk/?language=rust")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_list_sdk_public(self):
        """Test SDK documentation is public (no auth required)"""
        response = self.client.get("/api/v1/developer/sdk/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify the response contains the expected SDK listing structure.
        # The endpoint returns {sdks: [...]}.
        self.assertIn("sdks", response.data,
                      "SDK list response must contain a 'sdks' key")
        self.assertIsInstance(response.data["sdks"], list,
                              "'sdks' value must be a list")
        self.assertGreater(len(response.data["sdks"]), 0,
                           "SDK list must not be empty")

    def test_retrieve_sdk(self):
        """Test retrieving SDK documentation by ID"""
        response = self.client.get(f"/api/v1/developer/sdk/{self.python_sdk.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["language"], "python")
        self.assertEqual(response.data["version"], "1.0.0")


class DeveloperFeatureFlagTests(TestCase):
    """Gate checks Tenant.developer_enabled for authenticated users.

    The "developer_enabled" gate is enforced on PluginViewSet (and
    soon other developer endpoints).  Unauthenticated users pass
    through (public docs); authenticated users from a non-developer
    tenant must receive 403.
    """

    def setUp(self):
        super().setUp()
        from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
        from hub.apps.users.models import User, UserStatus

        # Tenant with developer features DISABLED
        self.no_dev_tenant = Tenant.objects.create(
            name="no-dev-tenant",
            slug="no-dev-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
            developer_enabled=False,
        )
        self.no_dev_user = User.objects.create_user(
            email="nodev@example.com",
            password="testpass123",
            tenant=self.no_dev_tenant,
            status=UserStatus.ACTIVE,
        )

        # Tenant with developer features ENABLED
        self.dev_tenant = Tenant.objects.create(
            name="dev-tenant",
            slug="dev-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
            developer_enabled=True,
        )
        self.dev_user = User.objects.create_user(
            email="dev@example.com",
            password="testpass123",
            tenant=self.dev_tenant,
            status=UserStatus.ACTIVE,
        )

    def test_plugins_endpoint_blocked_when_developer_disabled(self):
        """Authenticated user on tenant with developer_enabled=False gets 403."""
        client = APIClient()
        client.force_authenticate(user=self.no_dev_user)
        response = client.get("/api/v1/developer/plugins/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_plugins_endpoint_allowed_when_developer_enabled(self):
        """Authenticated user on tenant with developer_enabled=True gets 200."""
        client = APIClient()
        client.force_authenticate(user=self.dev_user)
        response = client.get("/api/v1/developer/plugins/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
