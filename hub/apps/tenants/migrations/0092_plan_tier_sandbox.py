"""303.1 -- add SANDBOX to PlanTier enum.

No schema change (tier is CharField).  Migration documents the
addition for audit trail and seed compatibility.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0091_notification_opt_outs"),
    ]

    operations = [
        migrations.RunSQL(
            sql="SELECT 1;",  # No schema change — enum addition only
            reverse_sql="SELECT 1;",
        ),
    ]
