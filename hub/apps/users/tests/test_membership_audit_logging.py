"""
Membership grant/revoke audit logging (OpenSpec 260.C.4).

Uses real DB and AuditEvent rows — no mocks.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.audit import event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, UserTenantMembership
from hub.apps.users.services import UserTenantMembershipService

pytestmark = pytest.mark.django_db(transaction=True)


class MembershipAuditLoggingTest(TestCase):
    """MEMBERSHIP_GRANTED / MEMBERSHIP_REVOKED on membership service."""

    def setUp(self):
        uid = str(uuid.uuid4())[:8]
        self.tenant_a = Tenant.objects.create(
            name=f"Audit Mem Tenant A {uid}",
            slug=f"audit-mem-a-{uid}",
        )
        self.tenant_b = Tenant.objects.create(
            name=f"Audit Mem Tenant B {uid}",
            slug=f"audit-mem-b-{uid}",
        )
        self.admin_user = User.objects.create_user(
            email=f"admin-mem-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )
        self.subject_user = User.objects.create_user(
            email=f"subject-mem-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )

    @pytest.mark.integration
    def test_admin_grant_emits_membership_granted_with_actor_and_subject(self):
        svc = UserTenantMembershipService()
        svc.add_membership(
            self.subject_user,
            self.tenant_b,
            actor_user=self.admin_user,
            reason="admin_test_grant",
        )

        ev = AuditEvent.objects.filter(
            action=event_types.MEMBERSHIP_GRANTED,
            resource_id=str(self.subject_user.id),
            tenant_id=self.tenant_b.id,
        ).first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.actor_user_id, self.admin_user.id)
        self.assertEqual(
            ev.details_json["subject_user_id"],
            str(self.subject_user.id),
        )
        self.assertEqual(
            ev.details_json["actor_user_id"],
            str(self.admin_user.id),
        )
        self.assertEqual(ev.details_json["tenant_id"], str(self.tenant_b.id))
        self.assertEqual(ev.details_json["reason"], "admin_test_grant")
        membership = UserTenantMembership.objects.get(
            user=self.subject_user,
            tenant=self.tenant_b,
        )
        self.assertEqual(ev.details_json["membership_id"], str(membership.id))

    @pytest.mark.integration
    def test_idempotent_add_does_not_emit_second_grant_audit(self):
        svc = UserTenantMembershipService()
        svc.add_membership(
            self.subject_user, self.tenant_b, actor_user=self.admin_user
        )
        svc.add_membership(
            self.subject_user, self.tenant_b, actor_user=self.admin_user
        )
        count = AuditEvent.objects.filter(
            action=event_types.MEMBERSHIP_GRANTED,
            tenant_id=self.tenant_b.id,
            resource_id=str(self.subject_user.id),
        ).count()
        self.assertEqual(count, 1)

    @pytest.mark.integration
    def test_self_remove_emits_membership_revoked_actor_equals_subject(self):
        membership, _ = UserTenantMembership.objects.get_or_create(
            user=self.subject_user,
            tenant=self.tenant_b,
            defaults={},
        )
        expected_mid = str(membership.id)
        svc = UserTenantMembershipService()
        removed = svc.remove_membership(
            self.subject_user,
            self.tenant_b,
            actor_user=self.subject_user,
            reason="user_left_tenant",
        )
        self.assertTrue(removed)

        ev = AuditEvent.objects.filter(
            action=event_types.MEMBERSHIP_REVOKED,
            resource_id=str(self.subject_user.id),
            tenant_id=self.tenant_b.id,
        ).first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.actor_user_id, self.subject_user.id)
        self.assertEqual(
            ev.details_json["subject_user_id"],
            str(self.subject_user.id),
        )
        self.assertEqual(
            ev.details_json["actor_user_id"],
            str(self.subject_user.id),
        )
        self.assertEqual(ev.details_json["tenant_id"], str(self.tenant_b.id))
        self.assertEqual(ev.details_json["membership_id"], expected_mid)
        self.assertEqual(ev.details_json["reason"], "user_left_tenant")
        self.assertFalse(
            UserTenantMembership.objects.filter(
                user=self.subject_user, tenant=self.tenant_b
            ).exists(),
        )

    @pytest.mark.integration
    def test_remove_without_membership_emits_no_audit(self):
        svc = UserTenantMembershipService()
        removed = svc.remove_membership(
            self.subject_user,
            self.tenant_b,
            actor_user=self.admin_user,
            reason="noop",
        )
        self.assertFalse(removed)
        self.assertFalse(
            AuditEvent.objects.filter(
                action=event_types.MEMBERSHIP_REVOKED,
                resource_id=str(self.subject_user.id),
            ).exists(),
        )
