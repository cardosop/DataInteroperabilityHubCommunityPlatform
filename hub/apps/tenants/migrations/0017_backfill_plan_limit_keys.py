"""
Data migration: backfill 12 new limit keys on existing TenantPlan rows.

Only adds keys that are not already present in limits_json so
manually-customised values are preserved.
"""

from django.db import migrations

# New limit keys added in Phase 113.D with their per-tier defaults.
NEW_LIMIT_DEFAULTS = {
    "FREE": {
        "max_contracts": 10,
        "max_webhooks": 5,
        "max_mesh_domains": 3,
        "max_users": 5,
        "max_marketplace_listings": 5,
        "max_marketplace_connections": 3,
        "max_access_requests_per_month": 20,
        "max_compliance_runs_per_month": 10,
        "max_dq_runs_per_month": 20,
        "max_virtual_datasets": 10,
        "max_transformation_pipelines": 5,
        "max_odps_documents": 10,
    },
    "PRO": {
        "max_contracts": 100,
        "max_webhooks": 50,
        "max_mesh_domains": 30,
        "max_users": 50,
        "max_marketplace_listings": 50,
        "max_marketplace_connections": 30,
        "max_access_requests_per_month": 200,
        "max_compliance_runs_per_month": 100,
        "max_dq_runs_per_month": 200,
        "max_virtual_datasets": 100,
        "max_transformation_pipelines": 50,
        "max_odps_documents": 100,
    },
    "ENTERPRISE": {
        "max_contracts": None,
        "max_webhooks": None,
        "max_mesh_domains": None,
        "max_users": None,
        "max_marketplace_listings": None,
        "max_marketplace_connections": None,
        "max_access_requests_per_month": None,
        "max_compliance_runs_per_month": None,
        "max_dq_runs_per_month": None,
        "max_virtual_datasets": None,
        "max_transformation_pipelines": None,
        "max_odps_documents": None,
    },
}


def backfill_limit_keys(apps, schema_editor):
    TenantPlan = apps.get_model("tenants", "TenantPlan")

    for plan in TenantPlan.objects.all():
        defaults = NEW_LIMIT_DEFAULTS.get(plan.tier, NEW_LIMIT_DEFAULTS["FREE"])
        limits = plan.limits_json or {}
        updated = False

        for key, default_value in defaults.items():
            if key not in limits:
                limits[key] = default_value
                updated = True

        if updated:
            plan.limits_json = limits
            plan.save(update_fields=["limits_json"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0016_populate_plan_order_from_tier"),
    ]

    operations = [
        migrations.RunPython(backfill_limit_keys, noop),
    ]
