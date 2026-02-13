# Migration to make workflow_instances.workflow_definition_id FK deferrable
# so tests can simulate orphaned instances (instance with missing definition).

from django.db import migrations


def make_fk_deferrable(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            JOIN pg_class r ON c.confrelid = r.oid
            WHERE t.relname = 'workflow_instances'
              AND r.relname = 'workflow_definitions'
              AND c.contype = 'f';
        """)
        row = cursor.fetchone()
    if not row:
        return
    constraint_name = row[0]
    quoted = schema_editor.connection.ops.quote_name(constraint_name)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE workflow_instances ALTER CONSTRAINT " + quoted + " DEFERRABLE INITIALLY IMMEDIATE"
        )


def reverse_fk_deferrable(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            JOIN pg_class r ON c.confrelid = r.oid
            WHERE t.relname = 'workflow_instances'
              AND r.relname = 'workflow_definitions'
              AND c.contype = 'f';
        """)
        row = cursor.fetchone()
    if not row:
        return
    constraint_name = row[0]
    quoted = schema_editor.connection.ops.quote_name(constraint_name)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE workflow_instances ALTER CONSTRAINT " + quoted + " NOT DEFERRABLE"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("orchestration", "0003_merge_20260116_1227"),
    ]

    operations = [
        migrations.RunPython(make_fk_deferrable, reverse_fk_deferrable),
    ]
