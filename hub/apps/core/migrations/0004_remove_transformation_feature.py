# Generated migration to remove transformation feature
# This migration drops all transformation-related tables and cleans up references

from django.db import migrations


def _cleanup_search_index(apps, schema_editor):
    """Safely delete transformation pipeline entries from search index if table exists"""
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        # Check if search_searchindex table exists
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'search_searchindex'
            );
        """
        )
        table_exists = cursor.fetchone()[0]

        if table_exists:
            cursor.execute(
                "DELETE FROM search_searchindex WHERE resource_type = 'TRANSFORMATION_PIPELINE';"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_create_bug_prevention_models"),
        # Note: We don't depend on transformation migrations since we're removing them
        # This migration should run after transformation app is removed from INSTALLED_APPS
    ]

    operations = [
        # Drop tables in reverse dependency order
        # 1. Drop preview_results (depends on transformation_pipelines, assets)
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS preview_results CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 2. Drop wrangling_operations (depends on wrangling_sessions)
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS wrangling_operations CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 3. Drop wrangling_sessions (depends on assets, tenants)
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS wrangling_sessions CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 4. Drop transformation_pipeline_executions (depends on transformation_pipelines, assets)
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS transformation_pipeline_executions CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 5. Drop transformation_nodes (depends on transformation_pipelines)
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS transformation_nodes CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 6. Drop transformation_pipelines (base table)
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS transformation_pipelines CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 7. Clean up search index entries for transformation pipelines (if table exists)
        # Use RunPython to safely check if table exists before deleting
        migrations.RunPython(
            code=_cleanup_search_index,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
