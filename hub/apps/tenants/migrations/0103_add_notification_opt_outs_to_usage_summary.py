"""Add ``notification_opt_outs`` to ``TenantUsageSummary`` model state.

The column already exists in the database (added by a prior migration for
``TenantConfig`` / ``TenantPlan`` that also affected the usage summary table).
This migration is a state-only operation — it tells Django's ORM about the
column so ``get_or_create()`` and other ORM operations include the field
with its ``default=dict``, preventing NOT NULL violations on INSERT.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0102_enable_rls_tenant_usage_summaries"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name="tenantusagesummary",
                    name="notification_opt_outs",
                    field=models.JSONField(
                        default=dict,
                        blank=True,
                        help_text=(
                            "Per-tenant notification opt-out configuration "
                            "at the time of calculation."
                        ),
                    ),
                ),
            ],
        ),
    ]
