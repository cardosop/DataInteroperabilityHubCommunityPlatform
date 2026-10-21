# Allow file_pattern to be null/blank; processor and workflow use ".*" as default (match-all)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduled_ingestion', '0003_add_dlq_and_cost_tracking'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scheduledingestion',
            name='file_pattern',
            field=models.CharField(
                blank=True,
                help_text='File pattern (regex for matching files). Omit or leave blank to match all files (.*).',
                max_length=255,
                null=True,
            ),
        ),
    ]
