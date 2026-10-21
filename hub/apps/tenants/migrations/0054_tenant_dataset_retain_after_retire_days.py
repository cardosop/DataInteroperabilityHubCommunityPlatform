# Phase 260.4.A.4 — per-tenant retention window for RETIRED datasets.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0053_tenant_redact_sample_pii_in_ui"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="dataset_retain_after_retire_days",
            field=models.PositiveIntegerField(
                default=90,
                help_text=(
                    "Phase 260.4.A.4 — number of days a dataset row is kept "
                    "after retirement before the cleanup command hard-deletes "
                    "it. Default 90 days; per-tenant override supported."
                ),
            ),
        ),
    ]
