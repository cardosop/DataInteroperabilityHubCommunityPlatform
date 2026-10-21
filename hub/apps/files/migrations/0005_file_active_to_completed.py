from django.db import migrations


def _backfill_active_to_completed(apps, schema_editor):
    File = apps.get_model("files", "File")
    File.objects.filter(status="ACTIVE").update(status="COMPLETED")


def _rollback_completed_to_active(apps, schema_editor):
    # Irreversible backfill: once ACTIVE rows are canonicalized to COMPLETED,
    # we cannot distinguish migrated rows from genuinely COMPLETED rows.
    # Keep reverse as a safe no-op rather than corrupting historical state.
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("files", "0004_file_scan_status_index"),
    ]

    operations = [
        migrations.RunPython(
            _backfill_active_to_completed,
            reverse_code=_rollback_completed_to_active,
        ),
    ]
