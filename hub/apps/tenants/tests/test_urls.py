"""
Unit tests for Tenant URL configuration (hub.apps.tenants.urls).

Tests that tenant and tenant-config URL names resolve and that key views are wired.
Uses real URL resolution (no mocks).
"""

import pytest
from django.test import TestCase
from django.urls import resolve, reverse

from hub.apps.tenants import urls as tenant_urls

pytestmark = pytest.mark.django_db(transaction=True)


class TenantUrlsTest(TestCase):
    """Test tenant URL patterns and resolution."""

    def test_urlpatterns_non_empty(self):
        """Success: tenant app urlpatterns are defined."""
        self.assertGreater(len(tenant_urls.urlpatterns), 0)

    def test_tenant_list_url_resolves(self):
        """Success: tenant-list name resolves to list path."""
        url = reverse("tenant-list")
        self.assertIn("/tenants/", url)
        self.assertTrue(url.endswith("/") or "/tenants" in url)

    def test_tenant_detail_url_resolves_with_uuid(self):
        """Success: tenant-detail name resolves with id kwarg (lookup_field=id)."""
        from hub.apps.tenants.models import Tenant
        import uuid as _uuid
        _uid = _uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(name=f"Test {_uid}", slug=f"test-tenant-{_uid}")
        url = reverse("tenant-detail", kwargs={"id": tenant.id})
        self.assertIn(str(tenant.id), url)
        self.assertIn("/tenants/", url)

    def test_tenant_config_detail_name_exists(self):
        """Success: tenant-config-detail name is registered."""
        from hub.apps.tenants.models import Tenant
        import uuid as _uuid
        _uid = _uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(name=f"Test {_uid}", slug=f"test-tenant-{_uid}")
        url = reverse("tenant-config-detail", kwargs={"tenant_id": tenant.id})
        self.assertIn("config", url)
        self.assertIn(str(tenant.id), url)

    def test_tenant_usage_url_resolves(self):
        """Success: tenant-usage name resolves."""
        url = reverse("tenant-usage")
        self.assertIn("usage", url)

    def test_tenant_me_config_url_resolves(self):
        """Success: tenant-me-config name resolves."""
        url = reverse("tenant-me-config")
        self.assertIn("me/config", url)

    def test_tenant_list_path_resolves(self):
        """Success: full list path resolves to a callable view."""
        full_path = "/api/v1/tenants/"
        resolver = resolve(full_path)
        self.assertTrue(callable(resolver.func))
        self.assertIsNotNone(resolver.url_name)
