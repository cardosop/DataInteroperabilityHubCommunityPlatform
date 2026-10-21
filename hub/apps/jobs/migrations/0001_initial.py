# Generated migration for jobs app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Job',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('type', models.CharField(choices=[('DQ_RUN', 'Data Quality Run'), ('COMPLIANCE_RUN', 'Compliance Run'), ('CONTRACT_VALIDATION', 'Contract Validation'), ('SEMANTIC_MAPPING', 'Semantic Mapping'), ('CONTRACT_MIGRATION', 'Contract Migration')], help_text='Job type: DQ_RUN, COMPLIANCE_RUN, CONTRACT_VALIDATION, etc.', max_length=50)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('RUNNING', 'Running'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed'), ('CANCELLED', 'Cancelled')], default='PENDING', help_text='Job status: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED', max_length=20)),
                ('resource_type', models.CharField(help_text='Resource type: CONTRACT, DATASET, FILE, ASSET, etc.', max_length=50)),
                ('resource_id', models.UUIDField(help_text='ID of the resource this job operates on')),
                ('started_at', models.DateTimeField(blank=True, help_text='When job started running', null=True)),
                ('completed_at', models.DateTimeField(blank=True, help_text='When job completed (success or failure)', null=True)),
                ('error_message', models.TextField(blank=True, help_text='Error message if job failed', null=True)),
                ('result_json', models.JSONField(blank=True, default=dict, help_text='Job result data (partial results supported)', null=True)),
                ('details_json', models.JSONField(blank=True, default=dict, help_text='Job details (engine versions, progress, etc.)', null=True)),
                ('timeout_seconds', models.IntegerField(blank=True, help_text='Job timeout in seconds (configurable per job type)', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created the job', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_jobs', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(blank=True, help_text='Tenant this job belongs to (nullable for system jobs)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='jobs', to='tenants.tenant')),
            ],
            options={
                'db_table': 'jobs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(fields=['tenant', 'status'], name='jobs_tenant_status_idx'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(fields=['tenant', 'type', 'status'], name='jobs_tenant_type_status_idx'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(fields=['resource_type', 'resource_id'], name='jobs_resource_idx'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(fields=['status', 'created_at'], name='jobs_status_created_idx'),
        ),
    ]

