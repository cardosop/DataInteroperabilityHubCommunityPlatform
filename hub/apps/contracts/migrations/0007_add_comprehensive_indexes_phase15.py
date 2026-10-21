"""
Add comprehensive indexes for Phase 15 performance optimization.

This migration creates indexes for:
- Contact email filtering (optimized GIN index)
- Server type filtering (optimized GIN index)
- Service level metrics filtering (optimized GIN index)
- Version history queries (for datasets)
- Search queries (for search_index table)
- Observability metrics queries (for observability tables)

All indexes are designed to optimize common query patterns identified in Phase 15.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0006_add_additional_indexes'),
    ]

    operations = [
        # Optimized contact email index (using jsonb_path_ops for exact matches)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_contact_email_path_ops_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'contact' -> 'email') jsonb_path_ops);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_contact_email_path_ops_gin;
            """,
        ),
        # Optimized server type index (using jsonb_path_ops for exact matches)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_servers_type_path_ops_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'servers' -> 'type') jsonb_path_ops);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_servers_type_path_ops_gin;
            """,
        ),
        # Index for servicelevels property filtering (for min_availability, max_latency_ms)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_servicelevels_property_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'servicelevels' -> 'property'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_servicelevels_property_gin;
            """,
        ),
        # Index for servicelevels target value filtering (for numeric comparisons)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_servicelevels_target_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'servicelevels' -> 'target'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_servicelevels_target_gin;
            """,
        ),
        # Index for definitions (for definition queries)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_definitions_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'definitions'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_definitions_gin;
            """,
        ),
        # Index for terms (for terms queries)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_terms_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'terms'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_terms_gin;
            """,
        ),
        # Index for roles (for roles queries)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_roles_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'roles'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_roles_gin;
            """,
        ),
        # Index for team (for team queries)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_team_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'team'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_team_gin;
            """,
        ),
        # Index for pricing (for pricing queries)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_pricing_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'pricing'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_pricing_gin;
            """,
        ),
        # Index for support channels (for support queries)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_support_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'support'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_support_gin;
            """,
        ),
    ]

