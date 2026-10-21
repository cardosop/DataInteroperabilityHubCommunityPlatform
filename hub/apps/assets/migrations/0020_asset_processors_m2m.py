# Phase 232.6 — Asset.processors M2M via processor_agreements.AssetProcessorMembership

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("processor_agreements", "0002_asset_processor_membership"),
        ("assets", "0019_asset_ropa_metadata_and_purposes"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="processors",
            field=models.ManyToManyField(
                blank=True,
                help_text="Processors (data processing agreements) linked to this asset.",
                related_name="assets",
                through="processor_agreements.AssetProcessorMembership",
                to="processor_agreements.processor",
            ),
        ),
    ]
