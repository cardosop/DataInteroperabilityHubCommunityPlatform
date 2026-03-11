"""
Unit tests for invite flow (29.65.4).

Tests UserService.invite_user_to_tenant:
- invite existing user adds UserTenantMembership instead of failing
- invite new user creates User + UserTenantMembership

No mocks - uses real implementations.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class InviteFlowServiceTest(TestCase):
    """Test UserService.invite_user_to_tenant."""

    def setUp(self):
        uid = str(uuid.uuid4())[:8]
        self.tenant = Tenant.objects.create(
            name=f"Invite Tenant {uid}",
            slug=f"invite-tenant-{uid}",
        )
        self.actor = User.objects.create_user(
            email=f"actor-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Admin"},
        )
        self.data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )

    def test_invite_new_user_creates_user_and_membership(self):
        """Invite new user creates User + UserTenantMembership."""
        from hub.apps.users.models import UserTenantMembership
        from hub.apps.users.services import UserService

        service = UserService(tenant_id=str(self.tenant.id), user_id=str(self.actor.id))
        user, created = service.invite_user_to_tenant(
            tenant_id=str(self.tenant.id),
            actor_user_id=str(self.actor.id),
            email="newuser@example.com",
            display_name="New User",
            role_ids=[str(self.data_provider_role.id)],
            send_invitation=False,
        )

        self.assertTrue(created)
        self.assertEqual(user.email, "newuser@example.com")
        self.assertEqual(user.status, UserStatus.INVITED)
        self.assertEqual(user.tenant_id, self.tenant.id)

        self.assertTrue(
            UserTenantMembership.objects.filter(
                user=user, tenant=self.tenant
            ).exists(),
            "Invite new user must create UserTenantMembership",
        )

    def test_invite_existing_user_adds_membership(self):
        """Invite existing user (same email) adds UserTenantMembership instead of failing."""
        from hub.apps.users.models import UserTenantMembership
        from hub.apps.users.services import UserService

        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug=f"other-invite-{uuid.uuid4().hex[:8]}",
        )
        existing_user = User.objects.create_user(
            email="existing@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        service = UserService(tenant_id=str(self.tenant.id), user_id=str(self.actor.id))
        user, created = service.invite_user_to_tenant(
            tenant_id=str(self.tenant.id),
            actor_user_id=str(self.actor.id),
            email="existing@example.com",
            display_name="Existing User",
            role_ids=[str(self.data_provider_role.id)],
            send_invitation=False,
        )

        self.assertFalse(created)
        self.assertEqual(user.id, existing_user.id)
        self.assertEqual(user.tenant_id, other_tenant.id, "Primary tenant unchanged")

        self.assertTrue(
            UserTenantMembership.objects.filter(
                user=existing_user, tenant=self.tenant
            ).exists(),
            "Invite existing user must add UserTenantMembership",
        )

    def test_invite_existing_user_already_has_membership_idempotent(self):
        """Invite existing user who already has membership succeeds idempotently."""
        from hub.apps.users.models import UserTenantMembership
        from hub.apps.users.services import UserService

        # User already in self.tenant
        existing_user = User.objects.create_user(
            email="already-member@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.get_or_create(
            user=existing_user, tenant=self.tenant, defaults={}
        )

        service = UserService(tenant_id=str(self.tenant.id), user_id=str(self.actor.id))
        user, created = service.invite_user_to_tenant(
            tenant_id=str(self.tenant.id),
            actor_user_id=str(self.actor.id),
            email="already-member@example.com",
            send_invitation=False,
        )

        self.assertFalse(created)
        self.assertEqual(user.id, existing_user.id)
        # Still exactly one membership (idempotent)
        self.assertEqual(
            UserTenantMembership.objects.filter(
                user=existing_user, tenant=self.tenant
            ).count(),
            1,
        )

    def test_invite_existing_user_audit_in_inviting_tenant(self):
        """USER_TENANT_INVITED audit event is created in inviting tenant's context."""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.users.services import UserService

        other_tenant = Tenant.objects.create(
            name="Other Tenant Audit",
            slug=f"other-audit-{uuid.uuid4().hex[:8]}",
        )
        existing_user = User.objects.create_user(
            email="audit-test@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        service = UserService(tenant_id=str(self.tenant.id), user_id=str(self.actor.id))
        service.invite_user_to_tenant(
            tenant_id=str(self.tenant.id),
            actor_user_id=str(self.actor.id),
            email="audit-test@example.com",
            send_invitation=False,
        )

        event = AuditEvent.objects.filter(
            action="USER_TENANT_INVITED",
            resource_id=str(existing_user.id),
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.tenant_id, self.tenant.id, "Audit in inviting tenant")
