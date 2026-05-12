"""
Phase 272.2 — Tenant.access_request_compliance_gate_enabled.

Gates access request approval on a successful ComplianceRun with
allowed_to_store=True for the referenced resource. Default True for
new tenants, False for existing (one-release notice window per D-272.3).
"""
from django.db import migrations, models


def _default_compliance_gate():
    """Env-aware default for the field callable."""
    import os
    return os.environ.get("COMPLIANCE_GATE_DEFAULT", "").lower() != "false"


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0066_phase_271_1_tenant_connect_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="access_request_compliance_gate_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When True, access request approval requires a successful "
                    "ComplianceRun with allowed_to_store=True for the referenced "
                    "resource. New tenants default to True; existing tenants start "
                    "as False for the notice window (Phase 272.7.3)."
                ),
            ),
        ),
    ]
