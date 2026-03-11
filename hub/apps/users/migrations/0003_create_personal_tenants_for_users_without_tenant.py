# Data migration: create personal tenants for users with tenant_id=None and is_platform_admin=False.
# Idempotent: only processes users that still have tenant_id=None.
# useronboardfix Phase 3.1.1

import uuid
from datetime import timedelta

from django.db import migrations, transaction
from django.db import IntegrityError
from django.utils import timezone


def _get_platform_defaults():
    """Inline platform defaults (matches hub.apps.tenants.validators.get_platform_defaults)."""
    return {
        "default_dq_profile": "intake_basic_gx",
        "allowed_compliance_regimes": ["GDPR", "LGPD", "CCPA", "HIPAA", "SOX"],
        "default_compliance_regimes": ["GDPR", "LGPD"],
        "data_retention_days": 2555,
        "rate_limits": {
            "dq_runs": {"burst_per_10s": 20, "sustained_per_min": 60, "daily_cap": 10000},
            "compliance_runs": {"burst_per_10s": 20, "sustained_per_min": 60, "daily_cap": 10000},
            "file_uploads": {"burst_per_10s": 10, "sustained_per_min": 30},
            "contract_validation": {"burst_per_10s": 20, "sustained_per_min": 60},
            "catalog_reads": {"burst_per_10s": 50, "sustained_per_min": 200},
            "sparql_queries": {"burst_per_10s": 50, "sustained_per_min": 200},
        },
        "max_file_size_bytes": 10737418240,
        "max_job_concurrency": 5,
        "max_queued_jobs": 50,
    }


def create_personal_tenants_for_users_without_tenant(apps, schema_editor):
    """
    For each User with tenant_id=None and is_platform_admin=False, create a personal
    tenant (Tenant, TenantConfig, Subscription, Roles, UserRoles), assign user.tenant, save.
    Platform admins (is_platform_admin=True) are left unchanged.
    """
    User = apps.get_model("users", "User")
    Tenant = apps.get_model("tenants", "Tenant")
    TenantPlan = apps.get_model("tenants", "TenantPlan")
    TenantConfig = apps.get_model("tenants", "TenantConfig")
    Subscription = apps.get_model("billing", "Subscription")
    Role = apps.get_model("users", "Role")
    UserRole = apps.get_model("users", "UserRole")

    plan = TenantPlan.objects.filter(slug="free", is_active=True).first()
    if not plan:
        raise RuntimeError(
            "FREE plan not found. Run 'python manage.py seed_default_plans' before this migration."
        )

    platform_defaults = _get_platform_defaults()
    now = timezone.now()
    period_end = now + timedelta(days=365 * 100)

    users_to_migrate = User.objects.filter(tenant_id__isnull=True, is_platform_admin=False)
    for user in users_to_migrate:
        max_attempts = 5
        tenant = None

        for attempt in range(max_attempts):
            slug = f"personal-{uuid.uuid4().hex[:8]}"
            # Use suffixed name on retry to handle orphan tenant (name collision)
            name = (
                f"Personal - {user.email} - {uuid.uuid4().hex[:8]}"
                if attempt > 0
                else f"Personal - {user.email}"
            )
            try:
                with transaction.atomic():
                    tenant = Tenant.objects.create(
                        name=name,
                        slug=slug,
                        region=None,
                        status="ACTIVE",
                        kyc_status="UNVERIFIED",
                        plan=plan,
                    )
                break
            except IntegrityError:
                tenant = None
                continue

        if tenant is None:
            raise RuntimeError(
                f"Failed to create personal tenant for user {user.id} after {max_attempts} attempts."
            )

        TenantConfig.objects.create(
            tenant=tenant,
            default_dq_profile=platform_defaults.get("default_dq_profile"),
            allowed_compliance_regimes=platform_defaults.get("allowed_compliance_regimes", []),
            default_compliance_regimes=platform_defaults.get("default_compliance_regimes", []),
            data_retention_days=platform_defaults.get("data_retention_days"),
            rate_limits=platform_defaults.get("rate_limits", {}),
            max_file_size_bytes=platform_defaults.get("max_file_size_bytes"),
            max_job_concurrency=platform_defaults.get("max_job_concurrency"),
            max_queued_jobs=platform_defaults.get("max_queued_jobs"),
        )

        Subscription.objects.create(
            tenant=tenant,
            plan=plan,
            status="ACTIVE",
            current_period_start=now,
            current_period_end=period_end,
        )

        for role_name, description in [
            ("DATA_PROVIDER", "Can create and manage data assets"),
            ("DATA_CONSUMER", "Can consume and purchase data products"),
        ]:
            role, _ = Role.objects.get_or_create(
                tenant=tenant,
                name=role_name,
                defaults={"description": description},
            )
            UserRole.objects.get_or_create(user=user, role=role)

        user.tenant = tenant
        user.save(update_fields=["tenant_id"])


def noop(apps, schema_editor):
    """No reverse - tenant creation is one-way; platform admins were never changed."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_alter_user_status"),
        ("tenants", "0010_ensure_free_plan_exists"),
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_personal_tenants_for_users_without_tenant, noop),
    ]
