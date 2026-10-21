"""
Data migration: seed the canonical set of TenantPlan rows.

Previously this was done at runtime by conftest._seed_tenant_plans_if_missing()
called from a session-scoped fixture. Moving to a data migration means the rows
survive TransactionTestCase TRUNCATE — Django re-runs data migration RunPython
after each flush, so the plans are always present without monkey-patching
_fixture_teardown.
"""
from django.db import migrations


_DEFAULT_PLANS = [
    {
        "slug": "sandbox", "name": "Sandbox Plan", "tier": "SANDBOX",
        "category": "BASE", "order": 0, "is_active": True,
        "limits_json": {
            "max_assets": 5, "max_datasets": 5, "max_contracts": 3,
            "max_webhooks": 1, "max_mesh_domains": 0, "max_users": 1,
            "max_marketplace_listings": 0, "max_marketplace_connections": 1,
            "max_marketplace_orders_per_month": 5, "max_virtual_datasets": 1,
            "max_api_calls_per_month": 500, "max_scheduled_ingestions": 1,
            "max_scheduled_runs_per_month": 10, "max_scheduled_exports": 0,
            "max_export_runs_per_month": 5, "max_compliance_runs_per_month": 5,
            "max_dq_runs_per_month": 5, "max_access_requests_per_month": 0,
            "max_storage_gb": 1, "max_transformation_pipelines": 0,
            "max_transformation_runs_per_month": 5, "max_odps_documents": 3,
        },
    },
    {
        "slug": "free", "name": "Free Plan", "tier": "FREE",
        "category": "BASE", "order": 1, "is_active": True,
        "limits_json": {
            "max_assets": 10, "max_datasets": 20, "max_contracts": 10,
            "max_webhooks": 5, "max_mesh_domains": 3, "max_users": 5,
            "max_marketplace_listings": 5, "max_marketplace_connections": 3,
            "max_marketplace_orders_per_month": 10, "max_virtual_datasets": 10,
            "max_api_calls_per_month": 10000, "max_scheduled_ingestions": 5,
            "max_scheduled_runs_per_month": 50, "max_scheduled_exports": 5,
            "max_export_runs_per_month": 20, "max_compliance_runs_per_month": 10,
            "max_dq_runs_per_month": 20, "max_access_requests_per_month": 20,
            "max_storage_gb": 1, "max_transformation_pipelines": 5,
            "max_transformation_runs_per_month": 20, "max_odps_documents": 10,
        },
    },
    {
        "slug": "pro", "name": "Pro Plan", "tier": "PRO",
        "category": "BASE", "order": 2, "is_active": True,
        "limits_json": {
            "max_assets": 100, "max_datasets": 500, "max_contracts": 100,
            "max_webhooks": 50, "max_mesh_domains": 30, "max_users": 50,
            "max_marketplace_listings": 50, "max_marketplace_connections": 30,
            "max_marketplace_orders_per_month": 100, "max_virtual_datasets": 100,
            "max_api_calls_per_month": 100000, "max_scheduled_ingestions": 50,
            "max_scheduled_runs_per_month": 1000, "max_scheduled_exports": 50,
            "max_export_runs_per_month": 500, "max_compliance_runs_per_month": 100,
            "max_dq_runs_per_month": 200, "max_access_requests_per_month": 200,
            "max_storage_gb": 100, "max_transformation_pipelines": 50,
            "max_transformation_runs_per_month": 500, "max_odps_documents": 100,
        },
    },
    {
        "slug": "enterprise", "name": "Enterprise Plan", "tier": "ENTERPRISE",
        "category": "BASE", "order": 3, "is_active": True,
        "limits_json": {
            "max_assets": None, "max_datasets": None, "max_contracts": None,
            "max_webhooks": None, "max_mesh_domains": None, "max_users": None,
            "max_marketplace_listings": None, "max_marketplace_connections": None,
            "max_marketplace_orders_per_month": None, "max_virtual_datasets": None,
            "max_api_calls_per_month": None, "max_scheduled_ingestions": None,
            "max_scheduled_runs_per_month": None, "max_scheduled_exports": None,
            "max_export_runs_per_month": None, "max_compliance_runs_per_month": None,
            "max_dq_runs_per_month": None, "max_access_requests_per_month": None,
            "max_storage_gb": None, "max_transformation_pipelines": None,
            "max_transformation_runs_per_month": None, "max_odps_documents": None,
        },
    },
    {
        "slug": "ml-starter", "name": "ML Starter", "tier": "FREE",
        "category": "ML_AI", "order": 10, "is_active": True,
        "limits_json": {
            "max_ml_models": 3, "max_ml_training_jobs_per_month": 10,
            "max_ml_inference_requests_per_month": 500, "max_ml_deployed_models": 1,
            "max_ml_storage_gb": 5,
        },
    },
    {
        "slug": "ml-professional", "name": "ML Professional", "tier": "PRO",
        "category": "ML_AI", "order": 11, "is_active": True,
        "limits_json": {
            "max_ml_models": 20, "max_ml_training_jobs_per_month": 100,
            "max_ml_inference_requests_per_month": 10000, "max_ml_deployed_models": 10,
            "max_ml_storage_gb": 100,
        },
    },
    {
        "slug": "ml-enterprise", "name": "ML Enterprise", "tier": "ENTERPRISE",
        "category": "ML_AI", "order": 12, "is_active": True,
        "limits_json": {
            "max_ml_models": None, "max_ml_training_jobs_per_month": None,
            "max_ml_inference_requests_per_month": None, "max_ml_deployed_models": None,
            "max_ml_storage_gb": None,
        },
    },
]


def _seed_plans(apps, schema_editor):
    TenantPlan = apps.get_model("tenants", "TenantPlan")
    for plan_data in _DEFAULT_PLANS:
        slug = plan_data["slug"]
        defaults = {
            k: v for k, v in plan_data.items() if k != "slug"
        }
        # Ensure billing_interval and other NOT NULL fields with model defaults
        # are explicitly supplied.  The historical model's field defaults are
        # not always faithfully applied by the migration state renderer,
        # particularly after merge migrations.
        defaults.setdefault("billing_interval", "month")
        defaults.setdefault("price_amount_cents", 0)
        defaults.setdefault("price_currency", "usd")
        defaults.setdefault("notification_opt_outs", {})
        TenantPlan.objects.get_or_create(slug=slug, defaults=defaults)


def _noop(apps, schema_editor):
    # Reverse is a no-op — we never delete seed plans on rollback.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0098_add_boolean_defaults"),
    ]

    operations = [
        migrations.RunPython(_seed_plans, _noop),
    ]
