"""285.14.8.9 — Revoke all active sessions for a tenant.

Usage:
    python manage.py revoke_all_sessions --tenant <slug> --reason "Security incident INC-1234"
    python manage.py revoke_all_sessions --tenant <slug> --dry-run
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Revoke all active user sessions for a tenant (security incident response)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant", type=str, required=True, help="Tenant slug or UUID."
        )
        parser.add_argument(
            "--reason", type=str, default="Manual revocation",
            help="Reason for the revocation (logged in audit trail)."
        )
        parser.add_argument(
            "--dry-run", action="store_true", default=False,
            help="Report sessions that would be revoked without revoking them."
        )

    def handle(self, *args, **options):
        import uuid as _uuid

        from hub.apps.tenants.models import Tenant
        from hub.apps.audit.utils import create_audit_event

        tenant_slug = options["tenant"]
        try:
            _uuid.UUID(tenant_slug)
            tenant = Tenant.objects.get(id=tenant_slug)
        except (ValueError, Tenant.DoesNotExist):
            tenant = Tenant.objects.get(slug=tenant_slug)

        dry_run = options["dry_run"]
        reason = options["reason"]

        # Count active sessions for this tenant's users
        from hub.apps.auth.models import Session
        from django.contrib.auth import get_user_model

        User = get_user_model()
        tenant_users = User.objects.filter(tenant=tenant)
        sessions = Session.objects.filter(
            user__in=tenant_users,
            is_active=True,
        )

        count = sessions.count()
        self.stdout.write(
            f"Tenant {tenant.slug}: {count} active session(s) "
            f"across {tenant_users.count()} user(s)"
        )

        if dry_run:
            self.stdout.write("DRY RUN — no sessions revoked.")
            return

        revoked = sessions.update(is_active=False, revoked_at=timezone.now())
        self.stdout.write(f"Revoked {revoked} session(s).")

        create_audit_event(
            resource_type="SESSION",
            action="SESSION_REVOKED",
            actor_user=None,
            tenant=tenant,
            resource_id=None,
            result="SUCCESS",
            details={
                "revoked_count": revoked,
                "reason": reason,
                "source": "revoke_all_sessions",
            },
        )
