"""
Shared fixtures for schema validation tests (Phase 312.14).

Provides an authenticated APIClient fixture so response-format tests
can exercise real DRF views and validate pagination envelopes,
field naming, date formats, and null/empty representations against
actual API output rather than skipping on 401/403.
"""

from __future__ import annotations

import uuid

import pytest
from rest_framework.test import APIClient

from hub.apps.auth.jwt_utils import JWTTokenGenerator
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import (
    ensure_user_has_data_provider_role,
    ensure_user_has_tenant_admin_role,
)
from hub.apps.users.models import User, UserStatus


def _uid() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture()
def schema_tenant(db):
    """Create a tenant with active subscription for schema tests."""
    t = Tenant.objects.create(
        name=f"Schema Tenant {_uid()}",
        slug=f"schema-{_uid()}",
        status="ACTIVE",
    )
    ensure_tenant_has_active_subscription(t)
    return t


@pytest.fixture()
def schema_user(schema_tenant):
    """Create an active user with DATA_PROVIDER + TENANT_ADMIN roles."""
    u = User.objects.create_user(
        email=f"schema-{_uid()}@test.local",
        password="TestPass123!",
        tenant=schema_tenant,
        status=UserStatus.ACTIVE,
    )
    ensure_user_has_data_provider_role(u)
    ensure_user_has_tenant_admin_role(u)
    return u


@pytest.fixture()
def authenticated_client(schema_user):
    """Authenticated APIClient using a real JWT token.

    Schema tests validate response structure — they need a real 200,
    not a 401 skip.  This fixture gives every test a properly scoped
    user with a valid token so tests exercise the full DRF stack.
    """
    token = JWTTokenGenerator.generate_access_token(schema_user)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return c
