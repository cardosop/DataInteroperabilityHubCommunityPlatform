"""
Add JSONB GIN index for extensions.x_odps_link (Task 1.1.2)

This migration creates a GIN index on hub_contract_json->'extensions'->'x_odps_link'
to enable efficient queries for ODPS-ODCS bidirectional linking.

The index is idempotent (uses IF NOT EXISTS) to handle cases where the index
may have been created in a previous migration (e.g., 0009_add_odps_to_original_spec_type).

Performance Benefits:
- Enables fast lookups of contracts by ODPS link ID
- Optimizes queries for finding all ODCS contracts linked to a specific ODPS contract
- Supports efficient bidirectional linking queries

Index Type: GIN (Generalized Inverted Index)
- Best for JSONB queries with containment operators (->, ->>, @>, etc.)
- Supports efficient lookups on nested JSONB paths
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0009_add_odps_to_original_spec_type'),
    ]

    operations = [
        # Create JSONB GIN index for extensions.x_odps_link
        # This index enables efficient queries for ODPS-ODCS bidirectional linking
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS idx_contracts_extensions_odps_link
            ON contracts
            USING GIN ((hub_contract_json -> 'extensions' -> 'x_odps_link'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_contracts_extensions_odps_link;
            """,
        ),
    ]

