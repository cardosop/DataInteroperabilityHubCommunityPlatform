# Phase 230.8.9 (REQ-SEM-FED-002) — additive-only:
# AddField semantic_federate_optout (BooleanField, default=False) on
# Asset.  Default False so the new field is the explicit opt-out
# (no surprise data exposure on existing rows).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0011_asset_metadata_json"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="semantic_federate_optout",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When True, this resource's triples are NOT exposed "
                    "to external federated SERVICE queries "
                    "(REQ-SEM-FED-002)."
                ),
            ),
        ),
    ]
