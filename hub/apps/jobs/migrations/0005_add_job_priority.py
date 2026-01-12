# Generated migration for adding job priority field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0004_add_workflow_instance_to_query_execution'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='priority',
            field=models.CharField(
                choices=[
                    ('LOW', 'Low'),
                    ('NORMAL', 'Normal'),
                    ('HIGH', 'High'),
                    ('CRITICAL', 'Critical')
                ],
                default='NORMAL',
                help_text='Job priority: HIGH, NORMAL, LOW',
                max_length=20
            ),
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(fields=['priority', 'status'], name='jobs_priority_status_idx'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(fields=['tenant', 'priority', 'status'], name='jobs_tenant_priority_status_idx'),
        ),
    ]

