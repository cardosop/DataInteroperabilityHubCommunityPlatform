"""Recovery: add back deleted_at if old 0013 dropped it."""

from django.db import migrations


def _add_deleted_at_if_missing(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'files' AND column_name = 'deleted_at'
                ) THEN
                    ALTER TABLE files
                        ADD COLUMN deleted_at timestamp with time zone NULL;
                    CREATE INDEX IF NOT EXISTS files_deleted_at_idx
                        ON files (deleted_at);
                END IF;
            END $$;
            """
        )


class Migration(migrations.Migration):
    dependencies = [
        ("files", "0013_remove_file_unique_active_filename_per_tenant_and_more"),
    ]

    operations = [
        migrations.RunPython(
            _add_deleted_at_if_missing,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
