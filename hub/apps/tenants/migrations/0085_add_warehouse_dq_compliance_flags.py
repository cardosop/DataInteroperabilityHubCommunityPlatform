"""
285.10.1.0.3 — Add warehouse_dq_enabled + warehouse_compliance_enabled
BooleanFields to Tenant (default=False).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0084_tenant_mfa_required"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="warehouse_dq_enabled",
            field=models.BooleanField(
                default=False,
                help_text="285.10 — DRAFT. Gates warehouse-native DQ checks (SQL in customer warehouse).",
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="warehouse_compliance_enabled",
            field=models.BooleanField(
                default=False,
                help_text="285.10 — DRAFT. Gates warehouse-native compliance scans (SQL in customer warehouse).",
            ),
        ),
    ]
