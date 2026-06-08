# D232.16 — Compliance Pro packaging entitlement on base plan SKUs

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0048_tenant_compliance_retention_enforcer_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenantplan",
            name="compliance_pro_pack",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "D232.16 — when True, commercial terms allow Compliance Pro packaging; "
                    "individual subsystem flags on Tenant still default off."
                ),
            ),
        ),
    ]
