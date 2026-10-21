# Increase download_url max_length for presigned URLs (can exceed 2KB).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gdpr", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dataexportjob",
            name="download_url",
            field=models.URLField(
                blank=True,
                help_text=(
                    "Signed URL for downloading export (short-lived); "
                    "presigned URLs can exceed 2KB"
                ),
                max_length=4096,
                null=True,
            ),
        ),
    ]
