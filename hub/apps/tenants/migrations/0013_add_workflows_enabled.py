# Generated for Phase 14 — Workflows UI

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0012_add_versioning_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenantconfig",
            name="workflows_enabled",
            field=models.BooleanField(
                blank=True,
                default=True,
                help_text="Enable workflow orchestration for this tenant",
                null=True,
            ),
        ),
    ]
