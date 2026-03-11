"""
Security test fixtures.

Shared fixtures for two-tenant setup and authenticated clients.
Per tasks 29.1.5. Real DB; no mocks.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus, UserTenantMembership

User = get_user_model()


@pytest.fixture
def two_tenant_setup(db):
    """Create two tenants with one active user each. Returns (tenant_a, tenant_b, user_a, user_b)."""
    tenant_a = Tenant.objects.create(
        name="Security Test Tenant A",
        slug="security-tenant-a",
    )
    tenant_b = Tenant.objects.create(
        name="Security Test Tenant B",
        slug="security-tenant-b",
    )
    user_a = User.objects.create_user(
        email="security-a@example.com",
        password="testpass123",
        tenant=tenant_a,
        status=UserStatus.ACTIVE,
    )
    user_b = User.objects.create_user(
        email="security-b@example.com",
        password="testpass123",
        tenant=tenant_b,
        status=UserStatus.ACTIVE,
    )
    UserTenantMembership.objects.get_or_create(user=user_a, tenant=tenant_a)
    UserTenantMembership.objects.get_or_create(user=user_b, tenant=tenant_b)
    return tenant_a, tenant_b, user_a, user_b


@pytest.fixture
def authenticated_client_per_tenant(two_tenant_setup):
    """Return (client_a, client_b) — APIClients authenticated as user_a and user_b."""
    tenant_a, tenant_b, user_a, user_b = two_tenant_setup
    client_a = APIClient()
    client_a.force_authenticate(user=user_a)
    client_b = APIClient()
    client_b.force_authenticate(user=user_b)
    return client_a, client_b
