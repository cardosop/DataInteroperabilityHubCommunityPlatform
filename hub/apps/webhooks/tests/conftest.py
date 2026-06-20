"""
Shared pytest fixtures for webhook tests.

Provides ``webhook_test_context`` fixture so individual test files
don't duplicate the tenant + user + subscription setup boilerplate.
"""

from __future__ import annotations

import uuid

import pytest

from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus


@pytest.fixture
def webhook_test_context(db):
    """Create tenant + user + active subscription for webhook tests.

    Returns a dict with ``tenant`` and ``user`` keys.  Each call
    generates unique slug/email so tests don't collide under ``--reuse-db``.
    """
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"Test Tenant {uid}",
        slug=f"test-tenant-{uid}",
        status="ACTIVE",
        kyc_status=KYCStatus.VERIFIED,
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"test-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    return {"tenant": tenant, "user": user}
