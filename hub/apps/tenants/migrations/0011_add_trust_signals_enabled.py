# Generated for Phase 11 — Trust Signals Config UI

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0010_ensure_free_plan_exists"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenantconfig",
            name="trust_signals_enabled",
            field=models.BooleanField(
                blank=True,
                default=True,
                help_text="Enable trust signals (badges, quality SLAs) for marketplace listings",
                null=True,
            ),
        ),
    ]
