"""
Add JSONB indexes for lineage queries.

This migration creates GIN indexes on lineage-related JSONB paths to optimize
lineage queries at contract, model, and field levels.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0004_remove_datacontract_com_from_original_spec_type'),
    ]

    operations = [
        # Index for contract-level lineage
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_lineage_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'lineage'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_lineage_gin;
            """,
        ),
        # Index for model-level lineage
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_models_lineage_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'models'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_models_lineage_gin;
            """,
        ),
        # Index for field-level lineage (nested in models)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_models_fields_lineage_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'models' -> 'fields' -> 'lineage'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_models_fields_lineage_gin;
            """,
        ),
    ]

