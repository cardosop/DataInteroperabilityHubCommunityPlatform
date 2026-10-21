"""
Tests for migration 0006_populate_user_tenant_memberships.

Verifies that users with tenant_id get UserTenantMembership created (idempotent).
Uses real DB; calls migration function directly (no mocks/stubs).
"""

import importlib.util
import uuid

import pytest
from django.apps import apps
from django.test import TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _get_migration_func():
    """Load migration function from 0006."""
    from pathlib import Path

    migration_path = (
        Path(__file__).resolve().parent.parent
        / "migrations"
        / "0006_populate_user_tenant_memberships.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0006", migration_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load migration from {migration_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.create_memberships_for_existing_users


class MigrationPopulateUserTenantMembershipsTest(TestCase):
    """Test migration 0006: populate UserTenantMembership for existing users."""

    def test_users_with_tenant_get_membership(self):
        """Users with tenant_id get UserTenantMembership created."""
        from hub.apps.users.models import UserTenantMembership

        create_memberships = _get_migration_func()

        tenant = Tenant.objects.create(
            name="Migration Populate Tenant",
            slug="migration-populate-tenant",
        )
        user = User.objects.create_user(
            email=f"migration-populate-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        self.assertIsNotNone(user.tenant_id)

        # No membership before migration
        self.assertFalse(UserTenantMembership.objects.filter(user=user, tenant=tenant).exists())

        create_memberships(apps, None)

        # Membership created after migration
        self.assertTrue(
            UserTenantMembership.objects.filter(user=user, tenant=tenant).exists(),
            "User with tenant_id should get UserTenantMembership",
        )

    def test_migration_idempotent(self):
        """Running migration twice does not create duplicate memberships."""
        from hub.apps.users.models import UserTenantMembership

        create_memberships = _get_migration_func()

        tenant = Tenant.objects.create(
            name="Idempotent Tenant",
            slug="idempotent-tenant",
        )
        user = User.objects.create_user(
            email=f"idempotent-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )

        create_memberships(apps, None)
        count_first = UserTenantMembership.objects.filter(user=user, tenant=tenant).count()
        self.assertEqual(count_first, 1)

        create_memberships(apps, None)
        count_second = UserTenantMembership.objects.filter(user=user, tenant=tenant).count()
        self.assertEqual(count_second, 1, "Second run must not create duplicate")

    def test_users_without_tenant_skipped(self):
        """Users with tenant_id=None are skipped (no membership created)."""
        import uuid

        from hub.apps.users.models import UserTenantMembership

        create_memberships = _get_migration_func()
        uid = str(uuid.uuid4())[:8]

        user = User.objects.create_user(
            email=f"no-tenant-{uid}@example.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
            is_platform_admin=True,
        )
        self.assertIsNone(user.tenant_id)

        create_memberships(apps, None)

        self.assertEqual(
            UserTenantMembership.objects.filter(user=user).count(),
            0,
            "User without tenant should have no memberships",
        )
