"""
Unit tests for UserTenantMembership model and UserTenantMembershipService.

Per tasks 29.65.2.1 (TDD). Tests model, add_membership, list_tenants_for_user, validate_membership.
No mocks - uses real implementations.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class UserTenantMembershipModelTest(TestCase):
    """Test UserTenantMembership model."""

    def setUp(self):
        uid = str(uuid.uuid4())[:8]
        self.tenant_a = Tenant.objects.create(
            name=f"Membership Tenant A {uid}",
            slug=f"membership-tenant-a-{uid}",
        )
        self.tenant_b = Tenant.objects.create(
            name=f"Membership Tenant B {uid}",
            slug=f"membership-tenant-b-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"membership-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )

    def test_user_tenant_membership_model_exists(self):
        """UserTenantMembership model exists with user_id, tenant_id, created_at."""
        from hub.apps.users.models import UserTenantMembership

        m = UserTenantMembership.objects.create(user=self.user, tenant=self.tenant_b)
        self.assertEqual(m.user_id, self.user.id)
        self.assertEqual(m.tenant_id, self.tenant_b.id)
        self.assertIsNotNone(m.created_at)

    def test_user_tenant_membership_unique_constraint(self):
        """UNIQUE(user_id, tenant_id) prevents duplicate memberships."""
        from django.db import IntegrityError

        from hub.apps.users.models import UserTenantMembership

        UserTenantMembership.objects.create(user=self.user, tenant=self.tenant_b)
        with self.assertRaises(IntegrityError):
            UserTenantMembership.objects.create(user=self.user, tenant=self.tenant_b)


class UserTenantMembershipServiceAddMembershipTest(TestCase):
    """Test UserTenantMembershipService.add_membership."""

    def setUp(self):
        uid = str(uuid.uuid4())[:8]
        self.tenant = Tenant.objects.create(
            name=f"Add Membership Tenant {uid}",
            slug=f"add-membership-tenant-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"add-mem-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_add_membership_creates_membership(self):
        """add_membership(user, tenant) creates UserTenantMembership."""
        from hub.apps.users.services import UserTenantMembershipService

        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-add-{_uid}",
        )
        service = UserTenantMembershipService()
        service.add_membership(self.user, other_tenant)

        from hub.apps.users.models import UserTenantMembership

        self.assertTrue(
            UserTenantMembership.objects.filter(user=self.user, tenant=other_tenant).exists()
        )

    def test_add_membership_idempotent(self):
        """add_membership is idempotent; calling twice does not create duplicate."""
        from hub.apps.users.models import UserTenantMembership
        from hub.apps.users.services import UserTenantMembershipService

        other_tenant = Tenant.objects.create(
            name="Other Tenant Idempotent",
            slug="other-tenant-idem",
        )
        service = UserTenantMembershipService()
        service.add_membership(self.user, other_tenant)
        service.add_membership(self.user, other_tenant)

        count = UserTenantMembership.objects.filter(user=self.user, tenant=other_tenant).count()
        self.assertEqual(count, 1)

    def test_add_membership_for_primary_tenant_creates_membership(self):
        """add_membership(user, user.tenant) creates membership for primary tenant."""
        from hub.apps.users.models import UserTenantMembership
        from hub.apps.users.services import UserTenantMembershipService

        service = UserTenantMembershipService()
        service.add_membership(self.user, self.tenant)

        self.assertTrue(
            UserTenantMembership.objects.filter(user=self.user, tenant=self.tenant).exists(),
            "add_membership for primary tenant should create membership",
        )


class UserTenantMembershipServiceListTenantsTest(TestCase):
    """Test UserTenantMembershipService.list_tenants_for_user."""

    def setUp(self):
        uid = str(uuid.uuid4())[:8]
        self.tenant_a = Tenant.objects.create(
            name=f"List Tenant A {uid}",
            slug=f"list-tenant-a-{uid}",
        )
        self.tenant_b = Tenant.objects.create(
            name=f"List Tenant B {uid}",
            slug=f"list-tenant-b-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"list-tenants-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )

    def test_list_tenants_for_user_returns_both_tenants(self):
        """When user has memberships for tenant A and B, list_tenants_for_user returns both."""
        from hub.apps.users.models import UserTenantMembership
        from hub.apps.users.services import UserTenantMembershipService

        UserTenantMembership.objects.create(user=self.user, tenant=self.tenant_a)
        UserTenantMembership.objects.create(user=self.user, tenant=self.tenant_b)

        service = UserTenantMembershipService()
        tenants = service.list_tenants_for_user(self.user)

        tenant_ids = {t.id for t in tenants}
        self.assertIn(self.tenant_a.id, tenant_ids)
        self.assertIn(self.tenant_b.id, tenant_ids)
        self.assertEqual(len(tenants), 2)

    def test_list_tenants_for_user_returns_empty_when_no_memberships(self):
        """list_tenants_for_user returns empty list when user has no memberships."""
        from hub.apps.users.services import UserTenantMembershipService

        service = UserTenantMembershipService()
        tenants = service.list_tenants_for_user(self.user)
        self.assertEqual(tenants, [])


class UserTenantMembershipServiceValidateMembershipTest(TestCase):
    """Test UserTenantMembershipService.validate_membership."""

    def setUp(self):
        uid = str(uuid.uuid4())[:8]
        self.tenant_a = Tenant.objects.create(
            name=f"Validate Tenant A {uid}",
            slug=f"validate-tenant-a-{uid}",
        )
        self.tenant_b = Tenant.objects.create(
            name=f"Validate Tenant B {uid}",
            slug=f"validate-tenant-b-{uid}",
        )
        self.tenant_c = Tenant.objects.create(
            name=f"Validate Tenant C {uid}",
            slug=f"validate-tenant-c-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"validate-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )

    def test_validate_membership_returns_true_for_member(self):
        """validate_membership(user, tenant_a_id) returns True when user has membership."""
        from hub.apps.users.models import UserTenantMembership
        from hub.apps.users.services import UserTenantMembershipService

        UserTenantMembership.objects.create(user=self.user, tenant=self.tenant_a)
        UserTenantMembership.objects.create(user=self.user, tenant=self.tenant_b)

        service = UserTenantMembershipService()
        self.assertTrue(service.validate_membership(self.user, str(self.tenant_a.id)))
        self.assertTrue(service.validate_membership(self.user, str(self.tenant_b.id)))

    def test_validate_membership_returns_false_for_non_member(self):
        """validate_membership(user, tenant_c_id) returns False when user has no membership."""
        from hub.apps.users.models import UserTenantMembership
        from hub.apps.users.services import UserTenantMembershipService

        UserTenantMembership.objects.create(user=self.user, tenant=self.tenant_a)
        UserTenantMembership.objects.create(user=self.user, tenant=self.tenant_b)

        service = UserTenantMembershipService()
        self.assertFalse(service.validate_membership(self.user, str(self.tenant_c.id)))

    def test_validate_membership_returns_false_for_invalid_tenant_id(self):
        """validate_membership returns False for None, empty, or invalid UUID (defensive)."""
        from hub.apps.users.services import UserTenantMembershipService

        service = UserTenantMembershipService()
        self.assertFalse(service.validate_membership(self.user, None))
        self.assertFalse(service.validate_membership(self.user, ""))
        self.assertFalse(service.validate_membership(self.user, "invalid-uuid"))
        self.assertFalse(service.validate_membership(self.user, "not-a-uuid"))
