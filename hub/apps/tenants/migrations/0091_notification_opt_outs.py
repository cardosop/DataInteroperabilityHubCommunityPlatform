"""285.13.9.4 -- add ``notification_opt_outs`` JSONField to TenantConfig.

Per-tenant opt-out for non-critical notification categories.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0090_plan_price_change_approval"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenantconfig",
            name="notification_opt_outs",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Per-category notification opt-outs. "
                    "Keys are trigger names; True = opted out."
                ),
            ),
        ),
    ]
