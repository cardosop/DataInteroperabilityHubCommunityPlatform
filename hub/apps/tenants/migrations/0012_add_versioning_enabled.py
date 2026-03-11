# Generated for Phase 12 — Versioning UI

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0011_add_trust_signals_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenantconfig",
            name="versioning_enabled",
            field=models.BooleanField(
                blank=True,
                default=True,
                help_text="Enable dataset versioning (semantic versions, version history) for this tenant",
                null=True,
            ),
        ),
    ]
