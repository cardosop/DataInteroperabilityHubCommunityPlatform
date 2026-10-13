"""TDD pins for the ADMIN cross-tenant feature-flags GET surface
(close-test-coverage-gaps 4.1).

The live 4.1 spec surfaced the drift the component-level coverage had
masked: ``AdminTenantFeatureFlagView``'s row builder accessed
``flag.sensitive`` — an attribute the registry's ``FeatureFlag`` class
never had — so EVERY GET on the admin surface 500'd
("'FeatureFlag' object has no attribute 'sensitive'"). Sensitivity is a
REGISTRY-derived property (``is_sensitive(name)``: related_audit_event /
DPO / Legal sign-off), not a stored field.

These pins hold the REAL contract end-to-end (no mocks — a real tenant,
a real platform admin, the real URLconf):

- GET /api/v1/admin/tenants/{uuid}/feature-flags/ returns 200 for a
  PLATFORM_ADMIN;
- every row carries ``sensitive`` and it MATCHES ``is_sensitive(name)``
  for each registry flag;
- a non-admin gets 403 (the surface is admin-only).
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.feature_flag_registry import is_sensitive


@pytest.mark.django_db(transaction=True)
class TestAdminFeatureFlagGet:
    def _make_tenant(self):
        import uuid

        from hub.apps.tenants.models import Tenant, TenantStatus

        return Tenant.objects.create(
            name=f"flag-get-{uuid.uuid4().hex[:8]}",
            slug=f"flag-get-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
        )

    def _make_admin(self, tenant, is_platform_admin=True):
        import uuid

        from hub.apps.users.models import Role, User, UserRole

        user = User.objects.create_user(
            email=f"flag-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=tenant,
        )
        if is_platform_admin:
            role, _ = Role.objects.get_or_create(
                tenant=tenant,
                name="PLATFORM_ADMIN",
                defaults={"description": "PA"},
            )
            UserRole.objects.create(user=user, role=role)
            user.is_platform_admin = True
            user.save(update_fields=["is_platform_admin"])
        return user

    def test_get_returns_200_with_sensitive_matching_the_registry(self):
        tenant = self._make_tenant()
        admin = self._make_admin(tenant)
        client = APIClient()
        client.force_authenticate(user=admin)

        resp = client.get(f"/api/v1/admin/tenants/{tenant.id}/feature-flags/")
        assert resp.status_code == status.HTTP_200_OK, resp.content[:300]

        rows = resp.json()["flags"]
        assert len(rows) >= 1
        by_name = {row["name"]: row for row in rows}
        for name, row in by_name.items():
            assert row["sensitive"] is is_sensitive(name), (
                f"{name}: row.sensitive {row['sensitive']!r} != is_sensitive {is_sensitive(name)!r}"
            )

    def test_non_admin_gets_403(self):
        tenant = self._make_tenant()
        user = self._make_admin(tenant, is_platform_admin=False)
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.get(f"/api/v1/admin/tenants/{tenant.id}/feature-flags/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN
