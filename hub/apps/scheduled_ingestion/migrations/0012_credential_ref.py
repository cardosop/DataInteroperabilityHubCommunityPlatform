"""
285.6.2.6 — Add credential_ref CharField to ScheduledIngestion.

Nullable — migration window supports both inline creds and credential_ref.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheduled_ingestion", "0011_rename_ingestion_te_tenant__idx_ingestion_t_tenant__766711_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="scheduledingestion",
            name="credential_ref",
            field=models.CharField(
                blank=True, default=None, help_text="AWS SM ARN or dlt secrets key", max_length=1024, null=True
            ),
        ),
    ]
