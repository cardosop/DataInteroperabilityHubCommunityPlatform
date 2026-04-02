"""
Migration: Change Dataset.file on_delete from CASCADE to SET_NULL.

Phase 26-OB.3: Preserves dataset when its source file is deleted.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("datasets", "0007_make_dataset_file_nullable"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dataset",
            name="file",
            field=models.ForeignKey(
                blank=True,
                help_text="File this dataset is based on (nullable; SET_NULL preserves dataset on file deletion)",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="datasets",
                to="files.file",
            ),
        ),
    ]
