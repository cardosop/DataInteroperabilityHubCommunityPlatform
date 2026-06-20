"""
Management command to disable UX v2 for a tenant (rollback).

Phase 278.S.2 — staged rollout rollback tooling.
Emits TENANT_UX_V2_DISABLED audit event with reason.

Usage:
    python manage.py disable_ux_v2_for_tenant <subdomain> --reason "..."
    python manage.py disable_ux_v2_for_tenant acme-corp --reason "P0 regression: marketplace listing cards render blank in UX v2"
"""

import structlog
from django.core.management.base import BaseCommand, CommandError

from hub.apps.audit.utils import create_audit_event
from hub.apps.tenants.models import Tenant

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Disable UX v2 for a tenant by subdomain (rollback)"

    def add_arguments(self, parser):
        parser.add_argument(
            "subdomain",
            type=str,
            help="Tenant subdomain (slug) to disable UX v2 for",
        )
        parser.add_argument(
            "--reason",
            type=str,
            required=True,
            help="Reason for disabling UX v2 (required for audit trail)",
        )

    def handle(self, *args, **options):
        subdomain = options["subdomain"].strip()
        reason = options["reason"].strip()

        try:
            tenant = Tenant.objects.using("admin").get(slug=subdomain)
        except Tenant.DoesNotExist:
            raise CommandError(f'Tenant with subdomain "{subdomain}" not found.')

        if not tenant.ux_v2_enabled:
            self.stdout.write(
                self.style.WARNING(
                    f"Tenant {tenant.name} ({tenant.slug}) already has UX v2 disabled. "
                    "No change made."
                )
            )
            return

        tenant.ux_v2_enabled = False
        tenant.save(update_fields=["ux_v2_enabled", "updated_at"])

        # Emit audit event for rollback trail
        try:
            create_audit_event(
                resource_type="TENANT",
                action="TENANT_UX_V2_DISABLED",
                actor_user=None,
                tenant=tenant,
                resource_id=str(tenant.id),
                result="SUCCESS",
                details={
                    "tenant_id": str(tenant.id),
                    "tenant_name": tenant.name,
                    "tenant_slug": tenant.slug,
                    "disabled_by": "management_command",
                    "reason": reason,
                },
            )
        except Exception as audit_err:
            self.stderr.write(f"Audit event emission failed (non-fatal): {audit_err}")

        self.stdout.write(
            self.style.SUCCESS(
                f"UX v2 disabled for tenant {tenant.name} ({tenant.slug}). Reason: {reason}"
            )
        )

        logger.info(
            "ux_v2_disabled_for_tenant",
            tenant_id=str(tenant.id),
            tenant_slug=tenant.slug,
            tenant_name=tenant.name,
            reason=reason,
        )
