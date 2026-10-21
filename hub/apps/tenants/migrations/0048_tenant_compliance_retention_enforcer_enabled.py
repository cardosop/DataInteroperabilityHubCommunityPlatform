# Phase 232.7 — per-tenant enablement gate for retention auto-enforcement sweep.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0047_tenant_compliance_processor_agreements_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="compliance_retention_enforcer_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When True, the Phase 232.7 retention auto-sweep (tombstone + 90-day grace + "
                    "hard-delete) may process TIME_BASED policies for this tenant when the CronJob runs."
                ),
            ),
        ),
    ]
