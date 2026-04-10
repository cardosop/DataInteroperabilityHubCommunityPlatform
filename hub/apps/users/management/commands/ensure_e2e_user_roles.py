"""
Management command to ensure E2E test users exist with role-specific personas.

Creates users for all role personas so Playwright/frontend E2E tests can log in
as DPO, DC, TA, PA, AUD, CPO, DEV, DMO. Run before E2E (e.g. via e2e-detect-api.sh or CI).

Personas:
- DATA_PROVIDER (DPO): e2e_test@example.com
- DATA_CONSUMER: e2e_consumer@example.com
- TENANT_ADMIN (TA): e2e_admin@example.com
- PLATFORM_ADMIN (PA): e2e_platform@example.com (is_platform_admin=True)
- AUDITOR (AUD): e2e_auditor@example.com
- Compliance Officer (CPO): e2e_cpo@example.com (TENANT_ADMIN + DATA_PROVIDER + COMPLIANCE_OFFICER)
- External Developer (DEV): e2e_developer@example.com (DATA_PROVIDER)
- Data Mesh Domain Owner (DMO): e2e_dmo@example.com (TENANT_ADMIN + DATA_PROVIDER)
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.users.models import Role, User, UserRole, UserStatus

# Must match frontend e2e/setup/create-test-user.ts (PROFILE_ISOLATION_WORKER_COUNT)
PROFILE_ISOLATION_WORKER_COUNT = 16

# Must match frontend e2e/setup/create-test-user.ts
_BASE_E2E_USERS = [
    {
        "email": "e2e_test@example.com",
        "password": "TestPass123",
        "display_name": "E2E Test User (DPO)",
        "roles": ["DATA_PROVIDER"],
        "is_platform_admin": False,
    },
    {
        "email": "e2e_consumer@example.com",
        "password": "TestPass123",
        "display_name": "E2E Consumer User",
        "roles": ["DATA_CONSUMER"],
        "is_platform_admin": False,
        "tenant_slug": "consumer",  # Separate tenant so marketplace "cannot order own listing" passes
    },
    {
        "email": "e2e_admin@example.com",
        "password": "TestPass123",
        "display_name": "E2E Tenant Admin",
        "roles": ["TENANT_ADMIN", "DATA_PROVIDER"],
        "is_platform_admin": False,
    },
    {
        "email": "e2e_platform@example.com",
        "password": "TestPass123",
        "display_name": "E2E Platform Admin",
        "roles": [],
        "is_platform_admin": True,
    },
    {
        "email": "e2e_auditor@example.com",
        "password": "TestPass123",
        "display_name": "E2E Auditor",
        "roles": ["AUDITOR"],
        "is_platform_admin": False,
    },
    {
        "email": "e2e_cpo@example.com",
        "password": "TestPass123",
        "display_name": "E2E Compliance Officer",
        "roles": ["TENANT_ADMIN", "DATA_PROVIDER", "COMPLIANCE_OFFICER"],
        "is_platform_admin": False,
    },
    {
        "email": "e2e_developer@example.com",
        "password": "TestPass123",
        "display_name": "E2E External Developer",
        "roles": ["DATA_PROVIDER"],
        "is_platform_admin": False,
    },
    {
        "email": "e2e_dmo@example.com",
        "password": "TestPass123",
        "display_name": "E2E Data Mesh Domain Owner",
        "roles": ["TENANT_ADMIN", "DATA_PROVIDER"],
        "is_platform_admin": False,
    },
    # Secondary tenants for cross-tenant isolation & tenant-switching tests
    {
        "email": "e2e_iso@example.com",
        "password": "TestPass123",
        "display_name": "E2E Isolation Tenant User",
        "roles": ["DATA_PROVIDER"],
        "is_platform_admin": False,
        "tenant_slug": "tenant-iso",
    },
    {
        "email": "e2e_tenant_b@example.com",
        "password": "TestPass123",
        "display_name": "E2E Tenant-B User",
        "roles": ["DATA_PROVIDER", "DATA_CONSUMER"],
        "is_platform_admin": False,
        "tenant_slug": "tenant-b",
    },
]

# One user per Playwright worker: profile E2E mutates display_name; sharing e2e_test@ across
# workers races GET /auth/me/ cache vs PATCH and flakes the header assertion.
E2E_USERS = _BASE_E2E_USERS + [
    {
        "email": f"e2e_profile_w{i}@example.com",
        "password": "TestPass123",
        "display_name": f"E2E Profile Worker {i}",
        "roles": ["DATA_PROVIDER"],
        "is_platform_admin": False,
    }
    for i in range(PROFILE_ISOLATION_WORKER_COUNT)
]


ROLE_DESCRIPTIONS = {
    "DATA_PROVIDER": "Can create and manage data assets",
    "DATA_CONSUMER": "Can consume and purchase data products",
    "TENANT_ADMIN": "Tenant administrator",
    "AUDITOR": "Can audit access logs and compliance",
    "COMPLIANCE_OFFICER": "Can review access requests and compliance",
}


class Command(BaseCommand):
    help = (
        "Ensure E2E test users exist with role-specific personas (DPO, DC, TA, PA, AUD, CPO, DEV, DMO) "
        "so frontend E2E tests can access role-gated routes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            help="Ensure only this email (default: ensure all E2E persona users)",
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
            default_tenant, created = Tenant.objects.get_or_create(
                slug="default",
                defaults={"name": "Default Tenant", "status": TenantStatus.ACTIVE},
            )
            if created and not dry_run:
                self.stdout.write(self.style.SUCCESS("Created default tenant."))

            consumer_tenant, _ = Tenant.objects.get_or_create(
                slug="consumer",
                defaults={"name": "Consumer Tenant", "status": TenantStatus.ACTIVE},
            )

            # Secondary tenants for cross-tenant isolation and tenant-switching tests
            _tenant_cache = {
                "default": default_tenant,
                "consumer": consumer_tenant,
            }
            for extra_slug, extra_name in [
                ("tenant-iso", "Isolation Test Tenant"),
                ("tenant-b", "Tenant-B Test Tenant"),
            ]:
                t, t_created = Tenant.objects.get_or_create(
                    slug=extra_slug,
                    defaults={"name": extra_name, "status": TenantStatus.ACTIVE},
                )
                _tenant_cache[extra_slug] = t
                if t_created and not dry_run:
                    self.stdout.write(self.style.SUCCESS(f"Created tenant: {extra_slug}"))

            for spec in users_to_ensure:
                email = spec["email"]
                password = spec["password"]
                display_name = spec["display_name"]
                roles = spec.get("roles", [])
                is_platform_admin = spec.get("is_platform_admin", False)
                tenant_slug = spec.get("tenant_slug", "default")
                tenant = _tenant_cache.get(tenant_slug, default_tenant)

                user, user_created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "tenant": tenant,
                        "display_name": display_name,
                        "status": UserStatus.ACTIVE,
                        "is_platform_admin": is_platform_admin,
                    },
                )
                # Ensure existing users without tenant get assigned (fixes users created before tenant was required)
                if not dry_run and not user_created and user.tenant_id is None:
                    user.tenant = tenant
                    user.save(update_fields=["tenant"])
                    self.stdout.write(
                        self.style.SUCCESS(f"Assigned tenant {tenant.slug} to {email} (was missing)")
                    )
                # Migrate consumer to separate tenant if they were in default (for marketplace tests)
                if (
                    not dry_run
                    and not user_created
                    and tenant_slug == "consumer"
                    and getattr(user, "tenant_id", None) != consumer_tenant.id
                ):
                    user.tenant = consumer_tenant
                    user.save(update_fields=["tenant"])
                    self.stdout.write(
                        self.style.SUCCESS(f"Migrated {email} to consumer tenant for marketplace tests")
                    )
                if user_created and not dry_run:
                    user.set_password(password)
                    user.save(update_fields=["password"])
                    self.stdout.write(self.style.SUCCESS(f"Created user: {email}"))
                elif user_created and dry_run:
                    self.stdout.write(f"[dry-run] Would create user: {email}")
                elif not dry_run:
                    # Sync password for existing users (idempotent; ensures correct creds after DB restore)
                    if not user.check_password(password):
                        user.set_password(password)
                        user.save(update_fields=["password"])
                        self.stdout.write(
                            self.style.SUCCESS(f"Synced password for existing user: {email}")
                        )

                # Phase 204: mark all E2E users as email-verified so the
                # 24-hour grace period check in the login view doesn't block
                # them after the first day. Without this, E2E users created
                # >24h ago get 403 EMAIL_NOT_VERIFIED on every login attempt.
                if not dry_run and not getattr(user, "email_verified", False):
                    user.email_verified = True
                    from django.utils import timezone as _tz
                    user.email_verified_at = _tz.now()
                    user.save(update_fields=["email_verified", "email_verified_at"])
                    self.stdout.write(
                        self.style.SUCCESS(f"Marked {email} as email-verified")
                    )

                # Update is_platform_admin if changed
                if not dry_run and user.is_platform_admin != is_platform_admin:
                    user.is_platform_admin = is_platform_admin
                    user.save(update_fields=["is_platform_admin"])
                    self.stdout.write(
                        self.style.SUCCESS(f"Updated is_platform_admin={is_platform_admin} for {email}")
                    )

                # Assign roles
                user_tenant = user.tenant or tenant
                # Ensure UserTenantMembership exists for home tenant (X-Tenant-Id validation in API)
                if not dry_run and user_tenant:
                    from hub.apps.users.services import UserTenantMembershipService

                    UserTenantMembershipService().add_membership(user, user_tenant)
                for role_name in roles:
                    role, role_created = Role.objects.get_or_create(
                        tenant=user_tenant,
                        name=role_name,
                        defaults={"description": ROLE_DESCRIPTIONS.get(role_name, role_name)},
                    )
                    if role_created and not dry_run:
                        self.stdout.write(
                            self.style.SUCCESS(f"Created role {role_name} for tenant {user_tenant.slug}")
                        )
                    if not dry_run:
                        _, ur_created = UserRole.objects.get_or_create(
                            user=user, tenant=role.tenant, role=role
                        )
                        if ur_created:
                            self.stdout.write(
                                self.style.SUCCESS(f"Assigned {role_name} to {email}")
                            )
                    else:
                        if not UserRole.objects.filter(user=user, role=role).exists():
                            self.stdout.write(f"[dry-run] Would assign {role_name} to {email}")

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
