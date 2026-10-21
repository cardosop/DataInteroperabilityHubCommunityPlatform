# Generated migration: add last_rotation_reminder_at to APIKey (277.B.069)
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hub_auth", "0009_refreshtoken_tenant_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="apikey",
            name="last_rotation_reminder_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text="Last time a rotation/expiry reminder notification was sent (277.B.069)",
            ),
        ),
    ]
