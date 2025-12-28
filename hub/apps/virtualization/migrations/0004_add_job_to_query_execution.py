# Generated manually for job queue integration

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('virtualization', '0003_add_query_execution'),
        ('jobs', '0001_initial'),  # Assuming jobs app has initial migration
    ]

    operations = [
        migrations.AddField(
            model_name='queryexecution',
            name='job',
            field=models.ForeignKey(
                blank=True,
                help_text='Job record for async execution (null for sync executions)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='query_executions',
                to='jobs.job'
            ),
        ),
    ]

