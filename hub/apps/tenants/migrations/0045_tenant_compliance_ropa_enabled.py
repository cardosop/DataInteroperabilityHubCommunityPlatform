# Phase 232.4 — per-tenant RoPA generator toggle.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0044_tenant_compliance_breach_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="compliance_ropa_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When True, RoPA generation APIs and artefacts are enabled for this tenant."
                ),
            ),
        ),
    ]
