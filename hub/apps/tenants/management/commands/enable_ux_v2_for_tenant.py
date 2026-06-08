"""
Management command to enable UX v2 for a specific tenant.

Phase 278.S.2 — staged rollout tooling for Tenant.ux_v2_enabled.
Emits TENANT_UX_V2_ENABLED audit event for the configuration change.

Usage:
    python manage.py enable_ux_v2_for_tenant <subdomain>
    python manage.py enable_ux_v2_for_tenant acme-corp
"""
from django.core.management.base import BaseCommand, CommandError
from hub.apps.audit.utils import create_audit_event
from hub.apps.tenants.models import Tenant
import structlog

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Enable UX v2 for a tenant by subdomain (slug)"

    def add_arguments(self, parser):
        parser.add_argument(
            "subdomain",
            type=str,
            help="Tenant subdomain (slug) to enable UX v2 for",
        )

    def handle(self, *args, **options):
        subdomain = options["subdomain"].strip()

        try:
            tenant = Tenant.objects.using("admin").get(slug=subdomain)
        except Tenant.DoesNotExist:
            raise CommandError(
                f'Tenant with subdomain "{subdomain}" not found.'
            )

        if tenant.ux_v2_enabled:
            self.stdout.write(
                self.style.WARNING(
                    f"Tenant {tenant.name} ({tenant.slug}) already has UX v2 enabled. "
                    "No change made."
                )
            )
            return

        tenant.ux_v2_enabled = True
        tenant.save(update_fields=["ux_v2_enabled", "updated_at"])

        # Emit audit event for staged-rollout trail
        try:
            create_audit_event(
                resource_type="TENANT",
                action="TENANT_UX_V2_ENABLED",
                actor_user=None,
                tenant=tenant,
                resource_id=str(tenant.id),
                result="SUCCESS",
                details={
                    "tenant_id": str(tenant.id),
                    "tenant_name": tenant.name,
                    "tenant_slug": tenant.slug,
                    "enabled_by": "management_command",
                },
            )
        except Exception as audit_err:
            self.stderr.write(
                f"Audit event emission failed (non-fatal): {audit_err}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"UX v2 enabled for tenant {tenant.name} ({tenant.slug})."
            )
        )

        logger.info(
            "ux_v2_enabled_for_tenant",
            tenant_id=str(tenant.id),
            tenant_slug=tenant.slug,
            tenant_name=tenant.name,
        )
