# Phase 230.8.9 (REQ-SEM-FED-002) — additive-only:
# AddField semantic_federate_optout (BooleanField, default=False) on
# Contract.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0027_lineage_subscription"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
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
