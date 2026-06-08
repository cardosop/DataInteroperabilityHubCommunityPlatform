# Phase 260.1.A.3 — DELETING status + deleted_at for grace window before hard purge.

from django.db import migrations, models


def _backfill_deleted_at_for_deleted_rows(apps, schema_editor):
    File = apps.get_model("files", "File")
    # Legacy rows: status=DELETED without deleted_at (immediate-delete era).
    for row in File.objects.filter(status="DELETED", deleted_at__isnull=True).iterator(
        chunk_size=500
    ):
        File.objects.filter(pk=row.pk).update(deleted_at=row.updated_at)


def _noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("files", "0005_file_active_to_completed"),
        ("tenants", "0050_tenant_file_soft_delete_grace_days"),
    ]

    operations = [
        migrations.AddField(
            model_name="file",
            name="deleted_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="When the file entered DELETING (API delete) or legacy DELETED.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="file",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("UPLOADING", "Uploading"),
                    ("ACTIVE", "Active"),
                    ("COMPLETED", "Completed"),
                    ("FAILED", "Failed"),
                    ("DELETING", "Deleting"),
                    ("DELETED", "Deleted"),
                ],
                default="PENDING",
                help_text=(
                    "File status: PENDING, UPLOADING, ACTIVE, COMPLETED, FAILED, "
                    "DELETING (grace), DELETED (legacy tombstone)"
                ),
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name="file",
            index=models.Index(
                fields=["tenant", "status", "deleted_at"],
                name="files_tenant_status_deleted_idx",
            ),
        ),
        migrations.RunPython(
            _backfill_deleted_at_for_deleted_rows,
            reverse_code=_noop_reverse,
        ),
    ]
