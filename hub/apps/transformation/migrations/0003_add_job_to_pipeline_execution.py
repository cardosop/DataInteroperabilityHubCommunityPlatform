# Generated manually for adding job field to PipelineExecution

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0001_initial'),  # Adjust if needed based on actual jobs migration
        ('transformation', '0002_pipelineexecution_transformationnode'),
    ]

    operations = [
        migrations.AddField(
            model_name='pipelineexecution',
            name='job',
            field=models.ForeignKey(
                blank=True,
                help_text='Job record for async execution (null for sync executions)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pipeline_executions',
                to='jobs.job'
            ),
        ),
    ]

