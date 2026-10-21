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

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

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

    def handle(self, *_args, **options):
        dry_run = options["dry_run"]
        single_email = options.get("email")
        users_to_ensure = (
            [u for u in E2E_USERS if u["email"] == single_email]
            if single_email
            else E2E_USERS
        )
        if single_email and not users_to_ensure:
            self.stdout.write(
                self.style.WARNING(f"Unknown email: {single_email}. No action taken.")
            )
            return

        with transaction.atomic():
            default_tenant, created = Tenant.objects.get_or_create(
                slug="default",
                defaults={
                    "name": "Default Tenant",
                    "status": TenantStatus.ACTIVE,
                    "ml_enabled": True,
                },
            )
            if created and not dry_run:
                self.stdout.write(self.style.SUCCESS("Created default tenant."))
            # E2E personas represent ESTABLISHED tenants: the asset-creation
            # gate (Phase 250.6.D.3) blocks the create form with
            # ONBOARDING_INCOMPLETE while ``onboarding_completed_at IS NULL``
            # (hub/apps/tenants/models.py capability snapshot). Mark the
            # default tenant onboarded so the persona-driven create flows
            # (DPO asset-creation journey) are not gated by a seed gap.
            if not dry_run and default_tenant.onboarding_completed_at is None:
                default_tenant.onboarding_completed_at = timezone.now()
                default_tenant.save(
                    update_fields=["onboarding_completed_at", "updated_at"]
                )
            # Ensure ml_enabled is True on the default tenant (idempotent update for pre-existing tenants).
            if not dry_run and not default_tenant.ml_enabled:
                default_tenant.ml_enabled = True
                default_tenant.save(update_fields=["ml_enabled"])
                self.stdout.write(
                    self.style.SUCCESS("Enabled ml_enabled on default tenant.")
                )
            # E2E personas exercise the full marketplace surface against the
            # default tenant; the marketplace viewsets gate on this flag
            # (403 MARKETPLACE_INTEGRATIONS_DISABLED when False — measured
            # 2026-08-28 across the use_cases marketplace suites).
            if not dry_run and not default_tenant.marketplace_integrations_enabled:
                default_tenant.marketplace_integrations_enabled = True
                default_tenant.save(update_fields=["marketplace_integrations_enabled"])
                self.stdout.write(
                    self.style.SUCCESS(
                        "Enabled marketplace_integrations_enabled on default tenant."
                    )
                )
            # BaaS feature gate — the BaaS CLI e2e workflows run against the
            # default persona tenant (403 BAAS_DISABLED when False; measured
            # 2026-08-28 in test_baas_api_keys_workflows).
            if not dry_run and not default_tenant.baas_enabled:
                default_tenant.baas_enabled = True
                default_tenant.save(update_fields=["baas_enabled"])
                self.stdout.write(
                    self.style.SUCCESS("Enabled baas_enabled on default tenant.")
                )
            # Advanced-DQ surface (Phase 240.4.B) — Tenant.data_quality_advanced_enabled
            # defaults False ("flip to True per-tenant after the basic DQ
            # feature is stable", hub/apps/tenants/models.py). The E2E
            # data-quality-advanced suite (frontend/e2e/features/
            # data-quality-advanced.spec.ts) exercises the real dashboards
            # against the default persona tenant; conjunctive with
            # data_quality_enabled (already True here).
            if not dry_run and not default_tenant.data_quality_advanced_enabled:
                default_tenant.data_quality_advanced_enabled = True
                default_tenant.save(update_fields=["data_quality_advanced_enabled"])
                self.stdout.write(
                    self.style.SUCCESS(
                        "Enabled data_quality_advanced_enabled on default tenant."
                    )
                )
            # Databricks control plane gate (openspec add-databricks-control-plane,
            # task 0.12) — defaults OFF for every tenant. JOURNEY-DB-001/002 E2E
            # run the real workspace-registry wizard against the default persona
            # tenant (403 DATABRICKS_CONTROL_PLANE_DISABLED when False).
            if not dry_run and not default_tenant.databricks_control_plane_enabled:
                default_tenant.databricks_control_plane_enabled = True
                default_tenant.save(update_fields=["databricks_control_plane_enabled"])
                self.stdout.write(
                    self.style.SUCCESS(
                        "Enabled databricks_control_plane_enabled on default tenant."
                    )
                )

            # UC browse seed (openspec add-databricks-uc-read task 1.11) —
            # JOURNEY-DB-005/006 E2E browse the REAL mirror rows of a
            # deterministic workspace (the mirror is normally populated by
            # the UC metadata sync, which needs live Databricks; the seed
            # gives the e2e tenant a stable catalog → schema → table chain).
            # W4.6 (oss-release-remediation, G1): the seed writes estate
            # models, so it lives in databricks_admin's
            # ``seed_e2e_uc_mirror`` command — invoked by NAME through
            # Django's command registry (no estate import here).
            if not dry_run and default_tenant.databricks_control_plane_enabled:
                # The tenant id is a POSITIONAL argument — Django's
                # call_command cannot pass positional args through
                # **options (min() on the empty option_strings tuple
                # crashes) — pinned RED-first by the W4.6 test.
                call_command(
                    "seed_e2e_uc_mirror",
                    str(default_tenant.id),
                    dry_run=dry_run,
                    stdout=self.stdout,
                )

            consumer_tenant, _ = Tenant.objects.get_or_create(
                slug="consumer",
                defaults={
                    "name": "Consumer Tenant",
                    "status": TenantStatus.ACTIVE,
                    "onboarding_completed_at": timezone.now(),
                },
            )
            if not dry_run and consumer_tenant.onboarding_completed_at is None:
                consumer_tenant.onboarding_completed_at = timezone.now()
                consumer_tenant.save(
                    update_fields=["onboarding_completed_at", "updated_at"]
                )
            # The DC persona lives in the CONSUMER tenant and the marketplace
            # IS its primary surface (orders/entitlements — JOURNEY-DC-004,
            # marketplace order/entitlement journeys). The marketplace
            # viewsets 403 MARKETPLACE_INTEGRATIONS_DISABLED when this flag
            # is False, and the SPA's 313.H.4 marketplace capability probe
            # then fails → /marketplace/* renders /unavailable before any
            # page assertion can run (measured: DC-004 "non-existent id"
            # landed on /unavailable). Mirror the default-tenant enablement.
            if not dry_run and not consumer_tenant.marketplace_integrations_enabled:
                consumer_tenant.marketplace_integrations_enabled = True
                consumer_tenant.save(update_fields=["marketplace_integrations_enabled"])
                self.stdout.write(
                    self.style.SUCCESS(
                        "Enabled marketplace_integrations_enabled on consumer tenant."
                    )
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
                    defaults={
                        "name": extra_name,
                        "status": TenantStatus.ACTIVE,
                        "onboarding_completed_at": timezone.now(),
                    },
                )
                _tenant_cache[extra_slug] = t
                if t_created and not dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(f"Created tenant: {extra_slug}")
                    )
                if not dry_run and t.onboarding_completed_at is None:
                    t.onboarding_completed_at = timezone.now()
                    t.save(update_fields=["onboarding_completed_at", "updated_at"])

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
                        self.style.SUCCESS(
                            f"Assigned tenant {tenant.slug} to {email} (was missing)"
                        )
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
                        self.style.SUCCESS(
                            f"Migrated {email} to consumer tenant for marketplace tests"
                        )
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
                            self.style.SUCCESS(
                                f"Synced password for existing user: {email}"
                            )
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
                        self.style.SUCCESS(
                            f"Updated is_platform_admin={is_platform_admin} for {email}"
                        )
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
                        defaults={
                            "description": ROLE_DESCRIPTIONS.get(role_name, role_name)
                        },
                    )
                    if role_created and not dry_run:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Created role {role_name} for tenant {user_tenant.slug}"
                            )
                        )
                    if not dry_run:
                        _, ur_created = UserRole.objects.get_or_create(
                            user=user, tenant=role.tenant, role=role
                        )
                        if ur_created:
                            self.stdout.write(
                                self.style.SUCCESS(f"Assigned {role_name} to {email}")
                            )
                    elif not UserRole.objects.filter(user=user, role=role).exists():
                        self.stdout.write(
                            f"[dry-run] Would assign {role_name} to {email}"
                        )

                # Ensure tenant has a plan assigned (required for plan limit checks).
                # E2E personas exercise full-mode workflows that create well over
                # the canonical free plan's max_assets (3 — see
                # tenants/plan_defaults.py, the single seeder source) during
                # a single suite run; the use_cases/security batches then
                # failed every create with 403 plan_limit_exceeded (found
                # 2026-08-28: persona tenant 'default' carried the free plan
                # and saturated it).  Assign the pro plan (canonical
                # max_assets=200) instead.  Plan-enforcement tests seed
                # their own dedicated tenants, so they are unaffected by
                # the persona provisioning default.
                if not dry_run and user_tenant:
                    from hub.apps.tenants.models import TenantPlan

                    if not user_tenant.plan:
                        pro_plan = TenantPlan.objects.filter(
                            slug="pro", is_active=True
                        ).first()
                        if pro_plan:
                            user_tenant.plan = pro_plan
                            user_tenant.save(update_fields=["plan"])
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Assigned pro plan to tenant {user_tenant.name}"
                                )
                            )
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"No pro plan found for tenant {user_tenant.name}. "
                                    "Run 'python manage.py seed_default_plans' first."
                                )
                            )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no changes made."))
