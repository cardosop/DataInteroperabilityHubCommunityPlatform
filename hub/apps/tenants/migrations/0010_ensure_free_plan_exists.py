# Data migration: ensure FREE plan exists for PersonalTenantService.
# Idempotent: creates FREE plan only when missing.

from django.db import migrations


def ensure_free_plan(apps, schema_editor):
    """Create FREE plan if it does not exist (idempotent)."""
    TenantPlan = apps.get_model("tenants", "TenantPlan")
    if TenantPlan.objects.filter(slug="free").exists():
        return
    TenantPlan.objects.create(
        name="Free Plan",
        slug="free",
        tier="FREE",
        limits_json={
            "max_assets": 10,
            "max_datasets": 20,
            "max_api_calls_per_month": 10000,
            "max_scheduled_ingestions": 5,
            "max_scheduled_runs_per_month": 50,
            "max_scheduled_exports": 5,
            "max_export_runs_per_month": 20,
            "max_storage_gb": 1,
        },
        is_active=True,
    )


def noop(apps, schema_editor):
    """No reverse - plan creation is idempotent and safe to leave."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0009_add_kyc_status_pending_review"),
    ]

    operations = [
        migrations.RunPython(ensure_free_plan, noop),
    ]
