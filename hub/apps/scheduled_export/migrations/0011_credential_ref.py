"""
285.6.2.6 — Add credential_ref CharField to ScheduledExport.

Nullable — migration window supports both inline creds and credential_ref.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheduled_export", "0010_alter_scheduledexport_destination_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="scheduledexport",
            name="credential_ref",
            field=models.CharField(
                blank=True, default=None, help_text="AWS SM ARN or dlt secrets key", max_length=1024, null=True
            ),
        ),
    ]
