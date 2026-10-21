"""Phase 53 (53.4): Add performance indexes for contract queries."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0018_remove_temp_spec_version_index"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="contract",
            index=models.Index(
                fields=["tenant_id", "hub_contract_version"],
                name="contracts_tenant_version_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="contract",
            index=models.Index(
                fields=["normalization_status", "created_at"],
                name="contracts_norm_status_created_idx",
            ),
        ),
    ]
