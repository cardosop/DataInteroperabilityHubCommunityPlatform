"""
Add indexes for ODPS queries (Task 6.3.1)

This migration creates indexes to optimize ODPS-related queries:
1. Index on original_spec_type for filtering ODPS vs ODCS contracts
2. JSONB GIN index on extensions.x_odps for linking queries
3. JSONB GIN indexes for ODPS-specific fields (odcs_link, odps_link)

Performance Benefits:
- Fast filtering by original_spec_type (ODPS vs ODCS)
- Efficient queries for ODPS-ODCS bidirectional linking
- Optimized lookups for contracts with ODPS links

Index Types:
- B-tree index for original_spec_type (exact match filtering)
- GIN indexes for JSONB paths (containment and path queries)
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0010_add_odps_link_index'),
    ]

    operations = [
        # Index 1: B-tree index on original_spec_type for filtering
        # This enables fast queries like: WHERE original_spec_type = 'ODPS'
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS idx_contracts_original_spec_type
            ON contracts (original_spec_type);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_contracts_original_spec_type;
            """,
        ),

        # Index 2: Composite index on tenant + original_spec_type
        # Most queries filter by tenant first, then by spec type
        # This composite index optimizes the common query pattern
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS idx_contracts_tenant_original_spec_type
            ON contracts (tenant_id, original_spec_type);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_contracts_tenant_original_spec_type;
            """,
        ),

        # Index 3: JSONB GIN index on extensions.x_odps (entire object)
        # This covers all queries on the x_odps extension object
        # Enables efficient queries for both odcs_link and odps_link
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS idx_contracts_extensions_x_odps_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'extensions' -> 'x_odps'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_contracts_extensions_x_odps_gin;
            """,
        ),

        # Index 4: JSONB GIN index on extensions.x_odps.odcs_link
        # Optimizes queries for finding ODPS contracts linked to a specific ODCS contract
        # Query pattern: WHERE hub_contract_json->'extensions'->'x_odps'->>'odcs_link' = 'contract_id'
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS idx_contracts_extensions_x_odps_odcs_link_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'extensions' -> 'x_odps' -> 'odcs_link'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_contracts_extensions_x_odps_odcs_link_gin;
            """,
        ),

        # Index 5: JSONB GIN index on extensions.x_odps.odps_link
        # Optimizes queries for finding ODCS contracts linked to a specific ODPS contract
        # Query pattern: WHERE hub_contract_json->'extensions'->'x_odps'->>'odps_link' = 'contract_id'
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS idx_contracts_extensions_x_odps_odps_link_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'extensions' -> 'x_odps' -> 'odps_link'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_contracts_extensions_x_odps_odps_link_gin;
            """,
        ),
    ]

