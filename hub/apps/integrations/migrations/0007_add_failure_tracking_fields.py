"""Phase 71: Add consecutive_failure_count and last_error_at for auto-disable."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0006_alter_marketplaceconnection_marketplace_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="marketplaceconnection",
            name="consecutive_failure_count",
            field=models.PositiveIntegerField(default=0, help_text="Number of consecutive sync failures (Phase 71)"),
        ),
        migrations.AddField(
            model_name="marketplaceconnection",
            name="last_error_at",
            field=models.DateTimeField(blank=True, null=True, help_text="Timestamp of the last sync failure (Phase 71)"),
        ),
    ]
