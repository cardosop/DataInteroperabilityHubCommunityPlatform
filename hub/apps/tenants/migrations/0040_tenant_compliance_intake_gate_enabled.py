# Phase 231.1 — per-tenant compliance intake gate (auto-scan + activation requirement)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0039_tenant_onboarding_completed_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="compliance_intake_gate_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 231.1 — when True, creating an Asset auto-enqueues a "
                    "compliance intake scan, and activation is blocked until a "
                    "SUCCEEDED ComplianceRun exists with allowed_to_store=true."
                ),
            ),
        ),
    ]
