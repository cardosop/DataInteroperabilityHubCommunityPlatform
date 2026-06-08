# Generated manually — syncs table names with the model's db_table
# after migration 0010 incorrectly renamed them to orchestration_*.
#
# The models declare:
#   PipelineDependency.Meta.db_table = "pipeline_dependencies"
#   PipelineRunDependency.Meta.db_table = "pipeline_run_dependencies"
#
# Migration 0010 used AlterModelTable to rename them to
# orchestration_pipeline_dependencies / orchestration_pipeline_run_dependencies
# (auto-detector picked up a transient model change that was later reverted).
# This migration renames them back so the physical tables match the model.

from django.db import migrations


def _table_exists(cursor, table_name):
    cursor.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
        [table_name],
    )
    return cursor.fetchone() is not None


def rename_forward(apps, schema_editor):
    """Rename orchestration_* → pipeline_* if the old names exist."""
    with schema_editor.connection.cursor() as cursor:
        if _table_exists(cursor, "orchestration_pipeline_dependencies"):
            schema_editor.execute(
                "ALTER TABLE orchestration_pipeline_dependencies "
                "RENAME TO pipeline_dependencies"
            )
        if _table_exists(cursor, "orchestration_pipeline_run_dependencies"):
            schema_editor.execute(
                "ALTER TABLE orchestration_pipeline_run_dependencies "
                "RENAME TO pipeline_run_dependencies"
            )


def rename_reverse(apps, schema_editor):
    """Reverse: rename pipeline_* → orchestration_* if pipeline_* exist."""
    with schema_editor.connection.cursor() as cursor:
        if _table_exists(cursor, "pipeline_dependencies"):
            schema_editor.execute(
                "ALTER TABLE pipeline_dependencies "
                "RENAME TO orchestration_pipeline_dependencies"
            )
        if _table_exists(cursor, "pipeline_run_dependencies"):
            schema_editor.execute(
                "ALTER TABLE pipeline_run_dependencies "
                "RENAME TO orchestration_pipeline_run_dependencies"
            )


class Migration(migrations.Migration):
    dependencies = [
        ("orchestration", "0010_remove_pipelinedependency_uq_pipeline_dependency_scope_and_more"),
    ]

    operations = [
        migrations.RunPython(rename_forward, rename_reverse),
    ]
