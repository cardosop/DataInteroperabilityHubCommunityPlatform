"""
Phase 274.12.4 — add ``Tenant.continuous_compliance_enforcement_enabled``.

Companion to the model field declared at
``hub/apps/tenants/models.py::Tenant.continuous_compliance_enforcement_enabled``.
Default False so existing tenants stay in observe-only mode; opt-in is per-tenant.

When True, SUCCEEDED ComplianceRun transitions that regress (risk_level exceeds
threshold or ``allowed_to_store=False``) auto-unpublish affected listings.

Depends on the 0069 merge node so the migration graph stays single-leaf.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0069_merge_compliance_gates"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="continuous_compliance_enforcement_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 274.12 — when True, compliance regressions on "
                    "published listings trigger auto-unpublish."
                ),
            ),
        ),
    ]
