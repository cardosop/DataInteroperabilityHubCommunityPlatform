"""Recovery: add back warehouse_config if old 0105 dropped it."""

from django.db import migrations


def _add_warehouse_config_if_missing(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'dq_runs' AND column_name = 'warehouse_config'
                ) THEN
                    ALTER TABLE dq_runs
                        ADD COLUMN warehouse_config jsonb NULL;
                END IF;
            END $$;
            """
        )


class Migration(migrations.Migration):
    dependencies = [
        ("dq", "0105_remove_dqrun_error_code_remove_dqrun_error_message_and_more"),
    ]

    operations = [
        migrations.RunPython(
            _add_warehouse_config_if_missing,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
