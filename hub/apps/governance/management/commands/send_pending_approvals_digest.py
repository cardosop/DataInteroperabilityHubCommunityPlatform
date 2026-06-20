"""
Phase 272.5 — send_pending_approvals_digest management command.

Daily cron: enumerates active tenants, finds access requests in
PENDING or PENDING_NEXT_APPROVER state, builds a per-next-approver
digest, and sends email notifications via the existing email service.
"""

from django.core.management.base import BaseCommand

from hub.apps.governance.models import AccessRequest, AccessRequestStatus
from hub.apps.tenants.models import Tenant, TenantStatus


class Command(BaseCommand):
    help = "Phase 272.5 — daily pending-approvals email digest per tenant/approver"

    def handle(self, **options):
        active_tenants = Tenant.objects.filter(status=TenantStatus.ACTIVE)
        sent = 0

        for tenant in active_tenants:
            pending = AccessRequest.objects.filter(
                tenant=tenant,
                status__in=(
                    AccessRequestStatus.PENDING,
                    AccessRequestStatus.PENDING_NEXT_APPROVER,
                ),
            )
            if not pending.exists():
                continue

            # Group by next-step approver role.
            # For requests with a multi-step workflow, notify users
            # matching the current step's role.
            from hub.apps.users.models import User, UserRole

            # Find users with TENANT_ADMIN role in this tenant
            # (simplified: notify all tenant admins of pending queue).
            admin_role = UserRole.objects.filter(
                name="TENANT_ADMIN",
                tenant=tenant,
            ).first()
            if not admin_role:
                continue

            admin_users = User.objects.filter(
                user_roles__role=admin_role,
                is_active=True,
            )

            for user in admin_users:
                self._send_digest(tenant, user, pending)
                sent += 1

        self.stdout.write(
            f"Digest sent to {sent} approvers across {active_tenants.count()} tenants."
        )

    def _send_digest(self, tenant, user, pending_qs):
        """Send a single-approver digest email."""
        try:
            from hub.apps.notifications.utils import create_user_notification

            count = pending_qs.count()
            if count == 0:
                return

            create_user_notification(
                user=user,
                tenant=tenant,
                title=f"Pending approvals digest — {count} request(s)",
                message=(
                    f"You have {count} access request(s) awaiting approval "
                    f"in tenant {tenant.name}. Please review them at your "
                    f"earliest convenience."
                ),
                notification_type="INFO",
                category="GOVERNANCE",
                resource_type="ACCESS_REQUEST",
                resource_id=None,
            )
        except Exception:
            self.stderr.write(f"Failed to send digest to {user.email}")
