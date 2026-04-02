"""Phase 71: Add consecutive_failure_count and last_error_at for auto-pause."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheduled_ingestion", "0006_add_deployment_sync_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="scheduledingestion",
            name="consecutive_failure_count",
            field=models.PositiveIntegerField(default=0, help_text="Number of consecutive failed runs (Phase 71 — auto-pause)"),
        ),
        migrations.AddField(
            model_name="scheduledingestion",
            name="last_error_at",
            field=models.DateTimeField(blank=True, null=True, help_text="Timestamp of the last failure (Phase 71)"),
        ),
    ]
