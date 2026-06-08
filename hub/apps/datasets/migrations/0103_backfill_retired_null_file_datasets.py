# 260.1.C — legacy ACTIVE rows with NULL file_id → RETIRED (data migration).

from django.db import migrations

from hub.apps.datasets import retirement


def forwards(apps, schema_editor):
    Dataset = apps.get_model("datasets", "Dataset")
    retirement.backfill_orphan_active_datasets_qs(Dataset.objects.all())


class Migration(migrations.Migration):

    dependencies = [
        ("datasets", "0102_dataset_status_retired_at"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
