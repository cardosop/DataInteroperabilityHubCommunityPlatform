"""
Ensure all users with tenant_id have UserTenantMembership.

Fixes 403 on assets/datasets/jobs when X-Tenant-Id validation fails because
UserTenantMembership was never created (e.g. users who registered before
the register view added add_membership).

Usage:
  python manage.py ensure_user_tenant_memberships
"""

from django.core.management.base import BaseCommand

from hub.apps.users.models import User
from hub.apps.users.services import UserTenantMembershipService


class Command(BaseCommand):
    help = (
        "Ensure all users with tenant_id have UserTenantMembership "
        "(fixes 403 on API access)"
    )

    def handle(self, *args, **options):
        service = UserTenantMembershipService()
        users = User.objects.filter(
            tenant_id__isnull=False
        ).select_related("tenant")
        added = 0
        for user in users:
            if user.tenant:
                service.add_membership(user, user.tenant)
                added += 1
        self.stdout.write(
            self.style.SUCCESS(f"Ensured membership for {added} user(s).")
        )
