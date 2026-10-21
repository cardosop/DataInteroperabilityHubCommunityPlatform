# Generated manually for Phase 203 — ClamAV scan fields + backfill.

from django.db import migrations, models


def backfill_scan_status_clean(apps, schema_editor):
    File = apps.get_model("files", "File")
    File.objects.filter(status__in=["ACTIVE", "COMPLETED"]).update(scan_status="CLEAN")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("files", "0002_rename_files_tenant_status_idx_files_tenant__3f0e67_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="file",
            name="scan_status",
            field=models.CharField(
                choices=[
                    ("PENDING_SCAN", "Pending scan"),
                    ("CLEAN", "Clean"),
                    ("INFECTED", "Infected"),
                    ("SCAN_UNAVAILABLE", "Scan unavailable"),
                    ("SCAN_ERROR", "Scan error"),
                ],
                db_index=True,
                default="PENDING_SCAN",
                help_text="Malware scan status (ClamAV); independent of upload status",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="file",
            name="scanned_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the last malware scan finished (any outcome)",
                null=True,
            ),
        ),
        migrations.RunPython(backfill_scan_status_clean, noop_reverse),
    ]
