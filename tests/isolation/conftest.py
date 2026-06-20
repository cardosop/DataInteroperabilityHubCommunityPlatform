"""
Phase 104 — Shared fixtures for multi-tenant isolation tests.

Provides two fully-independent tenants (A and B), each with an
authenticated APIClient using real JWT tokens. Every test module
in this directory uses these fixtures so that isolation is tested
at the authentication layer, not just ORM filtering.
"""

import uuid

import pytest
from django.db import connection
from rest_framework.test import APIClient

from hub.apps.auth.jwt_utils import JWTTokenGenerator
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import User, UserStatus


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture(autouse=True)
def _raise_statement_timeout():
    """
    Increase statement_timeout for isolation tests.

    TransactionTestCase does TRUNCATE … CASCADE on teardown which can
    hit the default 30 s timeout on a busy shared DB. 120 s is enough
    for the TRUNCATE to complete without blocking test runs.
    """
    with connection.cursor() as cur:
        cur.execute("SET statement_timeout = '120s'")
    yield
    # Reset is implicit — the connection is returned to pool/closed
    # after each TransactionTestCase.


@pytest.fixture()
def tenant_a(db):
    """Create Tenant A with active subscription."""
    t = Tenant.objects.create(
        name=f"Isolation Tenant A {_uid()}",
        slug=f"iso-a-{_uid()}",
        status="ACTIVE",
    )
    ensure_tenant_has_active_subscription(t)
    return t


@pytest.fixture()
def tenant_b(db):
    """Create Tenant B with active subscription."""
    t = Tenant.objects.create(
        name=f"Isolation Tenant B {_uid()}",
        slug=f"iso-b-{_uid()}",
        status="ACTIVE",
    )
    ensure_tenant_has_active_subscription(t)
    return t


@pytest.fixture()
def user_a(tenant_a):
    """Create User A in Tenant A with DATA_PROVIDER role."""
    u = User.objects.create_user(
        email=f"iso-a-{_uid()}@test.local",
        password="TestPass123!",
        tenant=tenant_a,
        status=UserStatus.ACTIVE,
    )
    ensure_user_has_data_provider_role(u)
    return u


@pytest.fixture()
def user_b(tenant_b):
    """Create User B in Tenant B with DATA_PROVIDER role."""
    u = User.objects.create_user(
        email=f"iso-b-{_uid()}@test.local",
        password="TestPass123!",
        tenant=tenant_b,
        status=UserStatus.ACTIVE,
    )
    ensure_user_has_data_provider_role(u)
    return u


@pytest.fixture()
def client_a(user_a):
    """Authenticated APIClient for Tenant A (real JWT)."""
    token = JWTTokenGenerator.generate_access_token(user_a)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return c


@pytest.fixture()
def client_b(user_b):
    """Authenticated APIClient for Tenant B (real JWT)."""
    token = JWTTokenGenerator.generate_access_token(user_b)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return c
