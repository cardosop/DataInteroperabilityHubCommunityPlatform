"""Add database-level DEFAULT false for every NOT NULL boolean column
on ``tenants`` that currently lacks a default.

Without a DB-level default, test factories that use ``bulk_create``
or raw SQL inserts produce ``IntegrityError: null value in column
"<name>" violates not-null constraint`` because Django's model-level
``default=False`` only applies to ORM ``.save()`` / ``.create()``.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0097_fix_notification_opt_outs_on_tenant"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            DECLARE r RECORD;
            BEGIN
              FOR r IN
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='tenants'
                  AND table_schema='public'
                  AND is_nullable='NO'
                  AND column_default IS NULL
                  AND data_type='boolean'
              LOOP
                EXECUTE format(
                  'ALTER TABLE tenants ALTER COLUMN %I SET DEFAULT false',
                  r.column_name
                );
              END LOOP;
            END $$;
            """,
            reverse_sql="SELECT 1;  -- no-op: defaults are harmless to keep",
        ),
    ]
