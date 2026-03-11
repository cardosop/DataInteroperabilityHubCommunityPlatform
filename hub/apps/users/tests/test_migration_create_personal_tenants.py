"""
Tests for migration 0003_create_personal_tenants_for_users_without_tenant.

Verifies that users with tenant_id=None and is_platform_admin=False get a personal
tenant; platform admins remain unchanged. Uses real DB; calls migration function
directly (no mocks/stubs).
"""
import importlib.util

import pytest
from django.apps import apps
from django.core.management import call_command
from django.test import TestCase

from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import TenantConfig
from hub.apps.users.models import Role, User, UserRole

pytestmark = pytest.mark.django_db(transaction=True)


def _get_migration_func():
    """Load migration function (module name starts with digit)."""
    from pathlib import Path

    migration_path = (
        Path(__file__).resolve().parent.parent
        / "migrations"
        / "0003_create_personal_tenants_for_users_without_tenant.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0003", migration_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load migration from {migration_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.create_personal_tenants_for_users_without_tenant


class MigrationCreatePersonalTenantsTest(TestCase):
    """Test migration 0003: create personal tenants for users without tenant."""

    def setUp(self):
        """Ensure FREE plan exists (tenants.0010)."""
        call_command("seed_default_plans")

    def test_users_without_tenant_get_personal_tenant(self):
        """Users with tenant_id=None and is_platform_admin=False get personal tenant."""
        create_personal_tenants_for_users_without_tenant = _get_migration_func()

        user = User.objects.create_user(
            email="migration-test-user@example.com",
            password="testpass123",
            tenant=None,
            is_platform_admin=False,
        )
        self.assertIsNone(user.tenant_id)

        create_personal_tenants_for_users_without_tenant(apps, None)

        user.refresh_from_db()
        self.assertIsNotNone(user.tenant_id, "User should have tenant assigned")
        tenant = user.tenant
        self.assertTrue(
            tenant.name.startswith("Personal - migration-test-user@example.com"),
            f"Tenant name should start with 'Personal - {{email}}', got {tenant.name}",
        )
        self.assertTrue(tenant.slug.startswith("personal-"))

        config = TenantConfig.objects.get(tenant=tenant)
        self.assertIsNotNone(config.default_dq_profile)

        subscription = Subscription.objects.get(tenant=tenant)
        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE)

        data_provider = Role.objects.filter(tenant=tenant, name="DATA_PROVIDER").first()
        data_consumer = Role.objects.filter(tenant=tenant, name="DATA_CONSUMER").first()
        self.assertIsNotNone(data_provider)
        self.assertIsNotNone(data_consumer)

        user_roles = UserRole.objects.filter(user=user)
        self.assertEqual(user_roles.count(), 2)

    def test_platform_admins_unchanged(self):
        """Platform admins with tenant_id=None remain unchanged (no personal tenant)."""
        create_personal_tenants_for_users_without_tenant = _get_migration_func()

        platform_admin = User.objects.create_user(
            email="platform-admin-migration@example.com",
            password="testpass123",
            tenant=None,
            is_platform_admin=True,
        )
        self.assertIsNone(platform_admin.tenant_id)

        create_personal_tenants_for_users_without_tenant(apps, None)

        platform_admin.refresh_from_db()
        self.assertIsNone(
            platform_admin.tenant_id,
            "Platform admin should remain without tenant",
        )

    def test_migration_idempotent_run_twice_no_duplicate_tenants(self):
        """Running migration twice does not create duplicate tenants for same user."""
        create_personal_tenants_for_users_without_tenant = _get_migration_func()

        user = User.objects.create_user(
            email="idempotent-test@example.com",
            password="testpass123",
            tenant=None,
            is_platform_admin=False,
        )

        create_personal_tenants_for_users_without_tenant(apps, None)
        user.refresh_from_db()
        tenant_id_first = user.tenant_id
        self.assertIsNotNone(tenant_id_first)

        create_personal_tenants_for_users_without_tenant(apps, None)
        user.refresh_from_db()
        tenant_id_second = user.tenant_id
        self.assertEqual(
            tenant_id_first,
            tenant_id_second,
            "Second run must not create a new tenant; user should keep same tenant_id",
        )
