# Generated migration for adding idempotency_key field to PipelineExecution

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transformation', '0003_add_job_to_pipeline_execution'),
    ]

    operations = [
        migrations.AddField(
            model_name='pipelineexecution',
            name='idempotency_key',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Idempotency key for retry safety (uses execution_id by default)',
                max_length=255,
                null=True,
                unique=True
            ),
        ),
        migrations.AddIndex(
            model_name='pipelineexecution',
            index=models.Index(fields=['idempotency_key'], name='transformat_idempo_idx'),
        ),
        migrations.AddConstraint(
            model_name='pipelineexecution',
            constraint=models.UniqueConstraint(
                condition=models.Q(('idempotency_key__isnull', False)),
                fields=['idempotency_key'],
                name='unique_idempotency_key_when_set'
            ),
        ),
    ]

