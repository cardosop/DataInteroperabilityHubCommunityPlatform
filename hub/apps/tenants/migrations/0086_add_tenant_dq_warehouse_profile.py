"""
285.10.2.1.5 — Add tenant_dq_warehouse_profile CharField to Tenant.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0085_add_warehouse_dq_compliance_flags"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="tenant_dq_warehouse_profile",
            field=models.CharField(
                blank=True,
                default="",
                help_text="285.10 — Default warehouse DQ profile key (e.g. 'warehouse_basic'). Empty = not configured.",
                max_length=100,
            ),
        ),
    ]
