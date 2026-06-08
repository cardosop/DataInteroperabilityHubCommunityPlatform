from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0041_tenantconfig_compliance_risk_threshold"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="compliance_consent_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 232.1 — when True, consent subsystem APIs, banner "
                    "flows, and integration gates are enforced for this tenant."
                ),
            ),
        ),
    ]
