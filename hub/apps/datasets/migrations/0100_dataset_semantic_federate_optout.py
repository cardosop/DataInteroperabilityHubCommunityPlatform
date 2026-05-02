# Phase 230.8.9 (REQ-SEM-FED-002) — additive-only:
# AddField semantic_federate_optout (BooleanField, default=False) on
# Dataset.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("datasets", "0099_alter_dataset_file_set_null"),
    ]

    operations = [
        migrations.AddField(
            model_name="dataset",
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
