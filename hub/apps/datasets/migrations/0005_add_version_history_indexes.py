"""
Add indexes for version history queries.

This migration creates indexes to optimize version history queries including:
- Version tree traversal (parent_version lookups)
- Current version queries (is_current flag)
- Semantic version queries
- Version hash lookups
- Archived version queries
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0004_add_schema_evolution_tracking'),
    ]

    operations = [
        # Composite index for version tree traversal (tenant + asset + parent_version)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS datasets_tenant_asset_parent_version_idx
            ON datasets
            (tenant_id, asset_id, parent_version_id)
            WHERE asset_id IS NOT NULL AND parent_version_id IS NOT NULL;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS datasets_tenant_asset_parent_version_idx;
            """,
        ),
        # Index for semantic version queries (tenant + asset + semantic_version)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS datasets_tenant_asset_semantic_version_idx
            ON datasets
            (tenant_id, asset_id, semantic_version)
            WHERE asset_id IS NOT NULL AND semantic_version IS NOT NULL;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS datasets_tenant_asset_semantic_version_idx;
            """,
        ),
        # Index for version tag queries (using GIN for JSONB array)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS datasets_version_tags_gin
            ON datasets
            USING GIN (version_tags)
            WHERE version_tags IS NOT NULL;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS datasets_version_tags_gin;
            """,
        ),
        # Composite index for archived version queries (tenant + asset + archived_at)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS datasets_tenant_asset_archived_at_idx
            ON datasets
            (tenant_id, asset_id, archived_at)
            WHERE asset_id IS NOT NULL AND archived_at IS NOT NULL;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS datasets_tenant_asset_archived_at_idx;
            """,
        ),
        # Index for version hash lookups (already exists but ensure it's there)
        # This is already in the model Meta, but we add it here for completeness
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS datasets_version_hash_idx
            ON datasets
            (version_hash)
            WHERE version_hash IS NOT NULL;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS datasets_version_hash_idx;
            """,
        ),
    ]

