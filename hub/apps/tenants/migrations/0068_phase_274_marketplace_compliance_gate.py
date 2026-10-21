"""
Phase 274.1 — Tenant.marketplace_publish_compliance_gate_enabled.

Gates listing publication on a successful ComplianceRun where
risk_level does not exceed the tenant's compliance_risk_threshold.
Default False for existing tenants (one-release notice window).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0067_phase_272_compliance_gate"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="marketplace_publish_compliance_gate_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 274.1 — when True, listing publication requires "
                    "a successful ComplianceRun with risk_level at or below "
                    "the tenant's compliance_risk_threshold."
                ),
            ),
        ),
    ]
