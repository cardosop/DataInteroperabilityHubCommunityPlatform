# Phase 260.6.A — drop ``COMPLETED`` from ``FileStatus`` enum.
#
# Per ADR-DSF (the ``files.status`` reconciliation tracked under
# ``InputDocs/Database_Schema.md`` §3.2.3), the canonical lifecycle
# states are ``{PENDING, UPLOADING, ACTIVE, FAILED, DELETING,
# DELETED}``. ``COMPLETED`` was a transient denormalisation
# introduced in ``0005_file_active_to_completed`` (canonicalising
# ACTIVE → COMPLETED at the time) and has been redundant with
# ``ACTIVE`` since the platform's lifecycle model settled on
# ACTIVE as the terminal upload state.
#
# Three operations in this migration:
#
# 1. **Data migration**: every row currently with ``status='COMPLETED'``
#    becomes ``status='ACTIVE'``. ``ACTIVE`` is the canonical
#    "upload finished and the file is usable" state per
#    ``models.FileStatus``. Idempotent: re-running yields zero
#    changes.
#
# 2. **DB CHECK constraint**: ``files`` is forbidden from carrying
#    ``status='COMPLETED'`` going forward. The constraint
#    enforces the post-migration invariant at the DB layer
#    regardless of how a future write reaches the row (Django ORM
#    save, ``objects.update``, ``bulk_create``, raw SQL, signals).
#    ``NOT VALID`` + asynchronous ``VALIDATE CONSTRAINT`` is the
#    standard pattern for adding CHECK to an existing table —
#    skip the synchronous full-table scan at deploy time, run
#    validation post-deploy.  Since step 1 already removed all
#    legacy COMPLETED rows, the validation will succeed; if a new
#    row had landed during the migration with COMPLETED (race
#    window), the validation would surface it as a constraint
#    violation rather than silently admitting.
#
# 3. **Choices update**: ``files.status`` field's Python-side
#    ``choices`` no longer enumerates COMPLETED. Forms / DRF
#    serializers built off the field reflect the new set
#    immediately. The DB column type is unchanged
#    (``CharField(max_length=20)``); only the Python validation
#    surface changes.

from django.db import migrations, models


def _rewrite_completed_to_active(apps, schema_editor):
    File = apps.get_model("files", "File")
    File.objects.filter(status="COMPLETED").update(status="ACTIVE")


def _noop_reverse_rewrite(apps, schema_editor):
    # Irreversible by design: once COMPLETED is collapsed into
    # ACTIVE, we cannot distinguish migrated rows from genuinely
    # ACTIVE rows. The reverse is a safe no-op rather than
    # corrupting historical state. Mirrors the irreversibility
    # disclaimer in ``0005_file_active_to_completed``.
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("files", "0008_metadata_json_size_cap"),
    ]

    operations = [
        # 1. Data migration — every COMPLETED row becomes ACTIVE.
        migrations.RunPython(
            _rewrite_completed_to_active,
            reverse_code=_noop_reverse_rewrite,
        ),
        # 2. DB CHECK constraint forbidding COMPLETED. NOT VALID
        #    skips the synchronous scan; the next operation runs
        #    asynchronous validation.
        migrations.RunSQL(
            sql=(
                "ALTER TABLE files "
                "ADD CONSTRAINT file_status_no_completed "
                "CHECK (status <> 'COMPLETED') "
                "NOT VALID;"
            ),
            reverse_sql=(
                "ALTER TABLE files DROP CONSTRAINT IF EXISTS "
                "file_status_no_completed;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE files VALIDATE CONSTRAINT "
                "file_status_no_completed;"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 3. Python-side choices no longer enumerate COMPLETED.
        migrations.AlterField(
            model_name="file",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("UPLOADING", "Uploading"),
                    ("ACTIVE", "Active"),
                    ("FAILED", "Failed"),
                    ("DELETING", "Deleting"),
                    ("DELETED", "Deleted"),
                ],
                default="PENDING",
                help_text=(
                    "File lifecycle status. Phase 260.6.A removed "
                    "the legacy ``COMPLETED`` value (it was "
                    "redundant with ACTIVE and is now forbidden "
                    "by a Postgres CHECK constraint)."
                ),
                max_length=20,
            ),
        ),
    ]
