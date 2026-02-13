"""
Management command to ensure E2E test users exist and have DATA_PROVIDER role.

Used so Playwright/frontend E2E tests can access role-gated routes (e.g. scheduled-ingestions)
without changing production registration behavior. Run before E2E (e.g. in docker-compose
entrypoint or CI) so the test user exists with the correct role; frontend getTestUser() will
then succeed via login.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.users.models import Role, User, UserRole, UserStatus

# Must match frontend e2e/setup/create-test-user.ts
E2E_USERS = [
    {
        "email": "e2e_test@example.com",
        "password": "TestPass123",
        "display_name": "E2E Test User",
    },
    {
        "email": "e2e_consumer@example.com",
        "password": "TestPass123",
        "display_name": "E2E Consumer User",
    },
]


class Command(BaseCommand):
    help = (
        "Ensure E2E test users exist with DATA_PROVIDER role so frontend E2E tests "
        "can access role-gated routes (e.g. /scheduled-ingestions)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            help="Ensure only this email (default: ensure both e2e_test and e2e_consumer)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without creating/updating users or roles",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        single_email = options.get("email")
        users_to_ensure = (
            [u for u in E2E_USERS if u["email"] == single_email] if single_email else E2E_USERS
        )
        if single_email and not users_to_ensure:
            self.stdout.write(
                self.style.WARNING(f"Unknown email: {single_email}. No action taken.")
            )
            return

        with transaction.atomic():
            tenant, created = Tenant.objects.get_or_create(
                slug="default",
                defaults={"name": "Default Tenant", "status": TenantStatus.ACTIVE},
            )
            if created and not dry_run:
                self.stdout.write(self.style.SUCCESS("Created default tenant."))

            role, role_created = Role.objects.get_or_create(
                tenant=tenant,
                name="DATA_PROVIDER",
                defaults={"description": "Can create and manage data assets"},
            )
            if role_created and not dry_run:
                self.stdout.write(
                    self.style.SUCCESS(f"Created DATA_PROVIDER role for tenant {tenant.slug}.")
                )

            for spec in users_to_ensure:
                email = spec["email"]
                password = spec["password"]
                display_name = spec["display_name"]
                user, user_created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "tenant": tenant,
                        "display_name": display_name,
                        "status": UserStatus.ACTIVE,
                    },
                )
                if user_created and not dry_run:
                    user.set_password(password)
                    user.save(update_fields=["password"])
                    self.stdout.write(self.style.SUCCESS(f"Created user: {email}"))
                elif user_created and dry_run:
                    self.stdout.write(f"[dry-run] Would create user: {email}")

                # Use role for user's tenant (so assignment is tenant-consistent)
                user_tenant = user.tenant or tenant
                role_for_user, _ = Role.objects.get_or_create(
                    tenant=user_tenant,
                    name="DATA_PROVIDER",
                    defaults={"description": "Can create and manage data assets"},
                )
                if not dry_run:
                    _, ur_created = UserRole.objects.get_or_create(user=user, role=role_for_user)
                    if ur_created:
                        self.stdout.write(self.style.SUCCESS(f"Assigned DATA_PROVIDER to {email}"))
                else:
                    if not UserRole.objects.filter(user=user, role=role_for_user).exists():
                        self.stdout.write(f"[dry-run] Would assign DATA_PROVIDER to {email}")

                # Ensure tenant has a plan assigned (required for plan limit checks)
                if not dry_run and user_tenant:
                    from hub.apps.tenants.models import TenantPlan

                    if not user_tenant.plan:
                        free_plan = TenantPlan.objects.filter(slug="free", is_active=True).first()
                        if free_plan:
                            user_tenant.plan = free_plan
                            user_tenant.save(update_fields=["plan"])
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Assigned free plan to tenant {user_tenant.name}"
                                )
                            )
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"No free plan found for tenant {user_tenant.name}. "
                                    "Run 'python manage.py seed_default_plans' first."
                                )
                            )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no changes made."))
