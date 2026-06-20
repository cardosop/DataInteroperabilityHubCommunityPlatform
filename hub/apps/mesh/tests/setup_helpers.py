"""
Shared test setup helpers for hub.apps.mesh tests.

Extracts repeated tenant / user / ABAC / subscription creation from
individual setUp methods so every test file gets a consistent environment.

Usage::

    from hub.apps.mesh.tests.setup_helpers import (
        create_mesh_test_tenant,
        create_mesh_test_users,
        setup_mesh_test_environment,
        TTestUser,
        TTestTenant,
    )

    class MyTestCase(TestCase):
        def setUp(self):
            self.tenant = create_mesh_test_tenant(data_mesh_enabled=True)
            self.admin_user, self.regular_user = create_mesh_test_users(self.tenant)
            self.admin_api_key, self.user_api_key = create_mesh_test_api_keys(
                self.tenant, self.admin_user, self.regular_user
            )
            setup_mesh_test_environment(self.tenant)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.contrib.auth import get_user_model

from hub.apps.auth.models import APIKey
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import Role, UserRole, UserStatus

User = get_user_model()


# ---------------------------------------------------------------------------
# Lightweight containers so tests can destructure return values cleanly
# ---------------------------------------------------------------------------


@dataclass
class TTestTenant:
    tenant: Tenant
    admin_role: Role


@dataclass
class TTestUser:
    user: User
    api_key: APIKey


# ---------------------------------------------------------------------------
# Tenant helpers
# ---------------------------------------------------------------------------


def create_mesh_test_tenant(
    *,
    kyc_status: str = KYCStatus.VERIFIED,
    data_mesh_enabled: bool = True,
    name_prefix: str = "Test Tenant",
    slug_prefix: str = "test-tenant",
) -> Tenant:
    """Create a Tenant with standard mesh-test defaults."""
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"{name_prefix} {uid}",
        slug=f"{slug_prefix}-{uid}",
        kyc_status=kyc_status,
        data_mesh_enabled=data_mesh_enabled,
    )


def create_mesh_test_users(
    tenant: Tenant,
) -> tuple[User, User]:
    """
    Create an admin user (with TENANT_ADMIN role) and a regular user
    (no role) for *tenant*.  Returns (admin_user, regular_user).
    """
    admin_role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name="TENANT_ADMIN",
        defaults={"description": "Tenant Administrator"},
    )

    uid = uuid.uuid4().hex[:8]
    admin_user = User.objects.create_user(
        email=f"admin-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        display_name="Admin User",
        status=UserStatus.ACTIVE,
    )
    UserRole.objects.create(user=admin_user, role=admin_role)

    regular_user = User.objects.create_user(
        email=f"user-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        display_name="Regular User",
        status=UserStatus.ACTIVE,
    )

    return admin_user, regular_user


def create_mesh_test_api_keys(
    tenant: Tenant,
    admin_user: User,
    regular_user: User,
) -> tuple[APIKey, APIKey]:
    """
    Create admin-scoped (mesh:write + mesh:read) and user-scoped
    (mesh:read) API keys.  ``_plaintext_key`` is attached to each
    object so tests can pass the plain-text key in Authorization headers.
    Returns (admin_api_key, user_api_key).
    """
    admin_key_value = APIKey.generate_key()
    admin_key_hash = APIKey.hash_key(admin_key_value)
    admin_api_key = APIKey.objects.create(
        tenant=tenant,
        user=admin_user,
        name="Admin API Key",
        key_hash=admin_key_hash,
        scopes=["mesh:write", "mesh:read"],
    )
    admin_api_key._plaintext_key = admin_key_value

    user_key_value = APIKey.generate_key()
    user_key_hash = APIKey.hash_key(user_key_value)
    user_api_key = APIKey.objects.create(
        tenant=tenant,
        user=regular_user,
        name="User API Key",
        key_hash=user_key_hash,
        scopes=["mesh:read"],
    )
    user_api_key._plaintext_key = user_key_value

    return admin_api_key, user_api_key


# ---------------------------------------------------------------------------
# Environment helpers (billing + ABAC)
# ---------------------------------------------------------------------------


def setup_mesh_test_environment(
    tenant: Tenant,
    *,
    abac_policy_name: str = "Allow Domain Creation (Mesh Tests)",
) -> None:
    """
    Ensure the tenant has an active subscription and an ABAC ALLOW
    policy for DATA_MESH_DOMAIN resources.  Required for view-layer
    tests that pass through TenantSuspensionMiddleware and ABACEngine.

    Idempotent — safe to call in setUp even when records already exist.
    """
    from hub.apps.governance.models import AccessPolicy
    from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

    # Billing — prevents 403 from TenantSuspensionMiddleware on writes
    ensure_tenant_has_active_subscription(tenant)

    # ABAC — create_domain and other mesh operations require an ALLOW policy
    AccessPolicy.objects.get_or_create(
        tenant=tenant,
        name=abac_policy_name,
        defaults={
            "conditions": {
                "user": {"tenant_id": str(tenant.id)},
                "resource": {"type": "DATA_MESH_DOMAIN"},
            },
            "effect": "ALLOW",
            "priority": 100,
            "enabled": True,
        },
    )
