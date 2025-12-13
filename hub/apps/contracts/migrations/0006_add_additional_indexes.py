"""
Add additional JSONB indexes for filtering and performance optimization.

This migration creates GIN indexes on additional JSONB paths to optimize
filtering queries for contact, server, servicelevel, and model fields.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0005_add_lineage_indexes'),
    ]

    operations = [
        # Index for servers (already exists in 0005, but ensure it's there)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_servers_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'servers'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_servers_gin;
            """,
        ),
        # Index for contact array (for contact_email, contact_name filtering)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_contact_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'contact'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_contact_gin;
            """,
        ),
        # Index for servicelevels array (for min_availability, max_latency_ms filtering)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_servicelevels_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'servicelevels'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_servicelevels_gin;
            """,
        ),
        # Index for models array (for model_name filtering)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_models_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'models'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_models_gin;
            """,
        ),
        # Index for server type filtering (optimize server_type queries)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_servers_type_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'servers' -> 'type'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_servers_type_gin;
            """,
        ),
        # Index for contact email filtering (optimize contact_email queries)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_contact_email_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'contact' -> 'email'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_contact_email_gin;
            """,
        ),
        # Index for models name filtering (optimize model_name queries)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS contracts_hub_contract_json_models_name_gin
            ON contracts
            USING GIN ((hub_contract_json -> 'models' -> 'name'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS contracts_hub_contract_json_models_name_gin;
            """,
        ),
    ]

