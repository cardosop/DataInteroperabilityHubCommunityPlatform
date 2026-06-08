# Generated manually — makemigrations DB connectivity issue
# 285.11.1.7 — pipeline_dependency_enabled feature flag
# Column already exists in DB (added by 0087_add_pipeline_dependency_models);
# this migration only registers the state change.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0086_add_tenant_dq_warehouse_profile"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="tenant",
                    name="pipeline_dependency_enabled",
                    field=models.BooleanField(
                        default=False,
                        help_text="285.11 — DRAFT. Gates the pipeline dependency graph, auto-derivation from lineage, and dependency-aware execution ordering.",
                    ),
                ),
            ],
        ),
    ]
