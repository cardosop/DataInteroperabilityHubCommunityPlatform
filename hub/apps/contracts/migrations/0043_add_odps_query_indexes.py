"""
Add indexes for ODPS query performance.

- Composite B-tree on (tenant, original_spec_type) for filtered lookups.
- GIN on hub_contract_json (jsonb_path_ops) for JSONB containment queries.
- Expression B-tree on the ODPS odcs_link JSONB path for path-equality queries.
"""
from django.db import migrations, models
import django.contrib.postgres.indexes


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0042_remove_datacontract_com_from_original_spec_type_phase2"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="contract",
            index=models.Index(
                fields=["tenant", "original_spec_type"],
                name="contracts_tenant_spec_type_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="contract",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["hub_contract_json"],
                name="contracts_hub_json_gin_idx",
            ),
        ),
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS
                contracts_odps_odcs_link_expr_idx
            ON contracts
            ((hub_contract_json -> 'extensions' -> 'x_odps' ->> 'odcs_link'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_odps_odcs_link_expr_idx;
            """,
        ),
    ]
