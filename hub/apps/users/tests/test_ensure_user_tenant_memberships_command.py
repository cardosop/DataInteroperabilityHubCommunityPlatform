from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, UserTenantMembership

pytestmark = pytest.mark.django_db(transaction=True)


class EnsureUserTenantMembershipsCommandTest(TestCase):
    @pytest.mark.integration
    def test_command_creates_membership_for_user_home_tenant(self):
        from hub.apps.audit import event_types
        from hub.apps.audit.models import AuditEvent

        tenant = Tenant.objects.create(
            name="Membership Cmd T1",
            slug="membership-cmd-t1",
        )
        user = User.objects.create_user(  # type: ignore[attr-defined]  # test: edge-case type exercise
            email="membership-cmd@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.filter(user=user, tenant=tenant).delete()

        call_command("ensure_user_tenant_memberships")

        self.assertTrue(UserTenantMembership.objects.filter(user=user, tenant=tenant).exists())
        audit = AuditEvent.objects.filter(
            action=event_types.MEMBERSHIP_GRANTED,
            resource_id=str(user.id),
            tenant_id=tenant.id,
        ).first()
        self.assertIsNotNone(audit)
        assert audit is not None
        self.assertEqual(
            audit.details_json["reason"],
            "ensure_user_tenant_memberships_command",
        )
        self.assertIsNone(audit.details_json["actor_user_id"])
        membership = UserTenantMembership.objects.get(user=user, tenant=tenant)
        self.assertEqual(audit.details_json["membership_id"], str(membership.id))

    @pytest.mark.integration
    def test_command_is_idempotent(self):
        from hub.apps.audit import event_types
        from hub.apps.audit.models import AuditEvent

        tenant = Tenant.objects.create(
            name="Membership Cmd T2",
            slug="membership-cmd-t2",
        )
        user = User.objects.create_user(  # type: ignore[attr-defined]  # test: edge-case type exercise
            email="membership-cmd-2@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )

        out = StringIO()
        call_command("ensure_user_tenant_memberships", stdout=out)
        call_command("ensure_user_tenant_memberships", stdout=out)

        self.assertEqual(
            UserTenantMembership.objects.filter(user=user, tenant=tenant).count(),
            1,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                action=event_types.MEMBERSHIP_GRANTED,
                resource_id=str(user.id),
                tenant_id=tenant.id,
            ).count(),
            1,
        )
