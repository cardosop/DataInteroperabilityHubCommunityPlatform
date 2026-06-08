"""Recovery: add back webhook_fired_at + warehouse_config if old 0105 dropped them."""

from django.db import migrations


def _add_columns_if_missing(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'compliance_runs' AND column_name = 'webhook_fired_at'
                ) THEN
                    ALTER TABLE compliance_runs
                        ADD COLUMN webhook_fired_at timestamp with time zone NULL;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'compliance_runs' AND column_name = 'warehouse_config'
                ) THEN
                    ALTER TABLE compliance_runs
                        ADD COLUMN warehouse_config jsonb NULL;
                END IF;
            END $$;
            """
        )


class Migration(migrations.Migration):
    dependencies = [
        ("compliance", "0105_remove_compliancerun_error_code_and_more"),
    ]

    operations = [
        migrations.RunPython(
            _add_columns_if_missing,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
