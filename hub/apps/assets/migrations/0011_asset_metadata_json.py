# Generated manually for Phase 205 — contract invalidation warnings on assets

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0010_asset_status_check_constraint"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="metadata_json",
            field=models.JSONField(
                blank=True,
                help_text="Hub-managed metadata (e.g. contract_warnings from invalidation cascade)",
                null=True,
            ),
        ),
    ]
