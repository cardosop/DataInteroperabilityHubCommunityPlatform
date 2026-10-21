"""
Security tests for tenant switch.

Phase 29.65.6.3. No cross-tenant switch: user must not access tenants
without membership. X-Tenant-Id must not allow access to non-member tenant.
No mocks; real implementations.
"""

import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.auth.jwt_utils import JWTTokenGenerator
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, UserTenantMembership

pytestmark = pytest.mark.django_db(transaction=True)


class TestTenantSwitchSecurity:
    """Security: no cross-tenant switch; X-Tenant-Id rejects non-members."""

    def test_switch_tenant_without_membership_returns_403(self):
        """POST /auth/switch-tenant/ with tenant user has no membership returns 403."""
        uid = str(uuid.uuid4())[:8]
        tenant_a = Tenant.objects.create(name=f"Sec A {uid}", slug=f"sec-a-{uid}")
        tenant_b = Tenant.objects.create(name=f"Sec B {uid}", slug=f"sec-b-{uid}")
        user = User.objects.create_user(
            email=f"sec-user-{uid}@example.com",
            password="testpass123",
            tenant=tenant_a,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.create(user=user, tenant=tenant_a)
        # No membership in tenant_b

        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.post(
            "/api/v1/auth/switch-tenant/",
            {"tenant_id": str(tenant_b.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_x_tenant_id_without_membership_returns_403(self):
        """X-Tenant-Id header with tenant user has no membership returns 403 from middleware."""
        uid = str(uuid.uuid4())[:8]
        tenant_a = Tenant.objects.create(name=f"Sec XA {uid}", slug=f"sec-xa-{uid}")
        tenant_b = Tenant.objects.create(name=f"Sec XB {uid}", slug=f"sec-xb-{uid}")
        user = User.objects.create_user(
            email=f"sec-xtenant-{uid}@example.com",
            password="testpass123",
            tenant=tenant_a,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.create(user=user, tenant=tenant_a)
        # No membership in tenant_b

        token = JWTTokenGenerator.generate_access_token(user, tenant_id=str(tenant_a.id))
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        resp = client.get("/api/v1/assets/", HTTP_X_TENANT_ID=str(tenant_b.id))
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_x_tenant_id_cannot_access_other_tenant_assets(self):
        """User with membership in tenant_a only cannot see tenant_b assets via X-Tenant-Id."""
        uid = str(uuid.uuid4())[:8]
        tenant_a = Tenant.objects.create(name=f"Sec OA {uid}", slug=f"sec-oa-{uid}")
        tenant_b = Tenant.objects.create(name=f"Sec OB {uid}", slug=f"sec-ob-{uid}")
        user = User.objects.create_user(
            email=f"sec-other-{uid}@example.com",
            password="testpass123",
            tenant=tenant_a,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.create(user=user, tenant=tenant_a)

        Asset.objects.create(
            tenant=tenant_b,
            key=f"sec-asset-b-{uid}",
            name="Asset B",
            status="DRAFT",
        )

        token = JWTTokenGenerator.generate_access_token(user, tenant_id=str(tenant_a.id))
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        # X-Tenant-Id for tenant_b without membership -> 403, so no asset access
        resp = client.get("/api/v1/assets/", HTTP_X_TENANT_ID=str(tenant_b.id))
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_user_a_cannot_switch_to_user_b_tenant_via_switch_api(self):
        """User A (tenant_a only) cannot switch to tenant_b via POST switch-tenant."""
        uid = str(uuid.uuid4())[:8]
        tenant_a = Tenant.objects.create(name=f"Sec UA {uid}", slug=f"sec-ua-{uid}")
        tenant_b = Tenant.objects.create(name=f"Sec UB {uid}", slug=f"sec-ub-{uid}")
        user_a = User.objects.create_user(
            email=f"sec-usera-{uid}@example.com",
            password="testpass123",
            tenant=tenant_a,
            status=UserStatus.ACTIVE,
        )
        user_b = User.objects.create_user(
            email=f"sec-userb-{uid}@example.com",
            password="testpass123",
            tenant=tenant_b,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.create(user=user_a, tenant=tenant_a)
        UserTenantMembership.objects.create(user=user_b, tenant=tenant_b)

        client = APIClient()
        client.force_authenticate(user=user_a)

        # user_a tries to switch to tenant_b (user_b's tenant) - no membership
        resp = client.post(
            "/api/v1/auth/switch-tenant/",
            {"tenant_id": str(tenant_b.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
