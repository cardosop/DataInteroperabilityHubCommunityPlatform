# Generated manually — Phase 231.2

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0040_tenant_compliance_intake_gate_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenantconfig",
            name="compliance_risk_threshold",
            field=models.CharField(
                choices=[
                    ("NONE", "None"),
                    ("LOW", "Low"),
                    ("MEDIUM", "Medium"),
                    ("HIGH", "High"),
                    ("CRITICAL", "Critical"),
                ],
                default="HIGH",
                help_text=(
                    "Maximum acceptable compliance risk level for publishing listings and activating assets; "
                    "risk strictly above this threshold blocks publish/activation."
                ),
                max_length=20,
            ),
        ),
    ]
