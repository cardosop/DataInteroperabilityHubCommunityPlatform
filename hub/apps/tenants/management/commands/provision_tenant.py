"""285.14.8.10 — Provision a new tenant.

Usage:
    python manage.py provision_tenant \
        --name "Acme Corp" --slug "acme-corp" \
        --admin-email "admin@acme.com" --plan "starter" \
        --regulations "GDPR,UK_GDPR"
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Provision a new tenant with plan, admin user, and default configuration."

    def add_arguments(self, parser):
        parser.add_argument("--name", type=str, required=True, help="Tenant display name.")
        parser.add_argument("--slug", type=str, required=True, help="URL-safe tenant identifier.")
        parser.add_argument(
            "--admin-email", type=str, required=True, help="Email for the initial admin user."
        )
        parser.add_argument("--plan", type=str, default="free", help="Plan slug (default: free).")
        parser.add_argument(
            "--regulations",
            type=str,
            default="",
            help="Comma-separated regulation keys (e.g., 'GDPR,UK_GDPR').",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Validate inputs without creating the tenant.",
        )

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model

        from hub.apps.tenants.models import Tenant, TenantPlan, TenantStatus

        User = get_user_model()

        name = options["name"]
        slug = options["slug"]
        admin_email = options["admin_email"]
        plan_slug = options["plan"]
        regulations_str = options["regulations"]
        dry_run = options["dry_run"]

        # Validate plan exists
        try:
            plan = TenantPlan.objects.get(slug=plan_slug, is_active=True)
        except TenantPlan.DoesNotExist:
            self.stderr.write(f"Plan '{plan_slug}' not found or inactive.")
            return

        # Validate slug is available
        if Tenant.objects.filter(slug=slug).exists():
            self.stderr.write(f"Tenant slug '{slug}' is already taken.")
            return

        regulation_keys = [r.strip().upper() for r in regulations_str.split(",") if r.strip()]

        if dry_run:
            self.stdout.write(
                f"DRY RUN — would create tenant '{name}' ({slug}) "
                f"with plan '{plan_slug}' and regulations {regulation_keys}"
            )
            return

        # Create tenant
        tenant = Tenant.objects.create(
            name=name,
            slug=slug,
            plan=plan,
            status=TenantStatus.ACTIVE,
            licensed_regulation_keys=regulation_keys,
        )

        # Create admin user (placeholder — real implementation sets password)
        user = User.objects.create(
            email=admin_email,
            tenant=tenant,
            is_tenant_admin=True,
        )

        self.stdout.write(
            self.style.SUCCESS(f"Tenant '{slug}' provisioned (id={tenant.id}, admin={user.email}).")
        )
        self.stdout.write("Next: set the admin password and configure feature flags.")
