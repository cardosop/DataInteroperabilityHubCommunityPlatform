# Phase 233.3 — per-tenant outbound webhook rate limit (REQ-WH-RL-001).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0054_tenant_dataset_retain_after_retire_days"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="webhook_outbound_rate_limit_per_minute",
            field=models.PositiveIntegerField(
                default=300,
                help_text=(
                    "Phase 233.3 — per-minute cap on outbound webhook "
                    "deliveries for this tenant. 0 disables outbound "
                    "webhooks entirely (kill-switch). Default 300."
                ),
            ),
        ),
    ]
