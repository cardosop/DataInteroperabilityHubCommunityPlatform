from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0016_asset_semantic_status_field"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION assets_force_version_increment()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                -- Phase 250.7.B.2: every row edit bumps version exactly once.
                NEW.version := COALESCE(OLD.version, 0) + 1;
                RETURN NEW;
            END;
            $$;

            DROP TRIGGER IF EXISTS
                assets_force_version_increment_trg
            ON assets;
            CREATE TRIGGER assets_force_version_increment_trg
            BEFORE UPDATE ON assets
            FOR EACH ROW
            EXECUTE FUNCTION assets_force_version_increment();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS
                assets_force_version_increment_trg
            ON assets;
            DROP FUNCTION IF EXISTS assets_force_version_increment();
            """,
        ),
    ]
