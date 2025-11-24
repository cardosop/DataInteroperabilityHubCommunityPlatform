# Generated migration for dq app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants', '0001_initial'),
        ('assets', '0001_initial'),
        ('datasets', '0001_initial'),
        ('files', '0001_initial'),
        ('jobs', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DQRun',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('profile_key', models.CharField(help_text='DQ profile key (e.g., intake_basic_gx, intake_basic_soda)', max_length=100)),
                ('engine', models.CharField(choices=[('GREAT_EXPECTATIONS', 'Great Expectations'), ('SODA', 'Soda')], help_text='DQ engine used: GREAT_EXPECTATIONS or SODA', max_length=50)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('RUNNING', 'Running'), ('SUCCEEDED', 'Succeeded'), ('FAILED', 'Failed')], default='PENDING', help_text='DQ run status: PENDING, RUNNING, SUCCEEDED, FAILED', max_length=20)),
                ('overall_status', models.CharField(blank=True, help_text='Overall DQ status: PASS, FAIL, WARN, UNKNOWN (from result)', max_length=20, null=True)),
                ('quality_score', models.FloatField(blank=True, help_text='Quality score (0-100)', null=True)),
                ('checks_json', models.JSONField(blank=True, help_text='List of DQ checks with results', null=True)),
                ('details_json', models.JSONField(blank=True, help_text='Detailed DQ results and metadata', null=True)),
                ('started_at', models.DateTimeField(blank=True, help_text='When DQ run started', null=True)),
                ('completed_at', models.DateTimeField(blank=True, help_text='When DQ run completed', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('asset', models.ForeignKey(blank=True, help_text='Asset this DQ run is for (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='dq_runs', to='assets.asset')),
                ('dataset', models.ForeignKey(blank=True, help_text='Dataset this DQ run is for (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='dq_runs', to='datasets.dataset')),
                ('file', models.ForeignKey(blank=True, help_text='File this DQ run is for (scan-only, nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='dq_runs', to='files.file')),
                ('job', models.ForeignKey(help_text='Job that orchestrates this DQ run', on_delete=django.db.models.deletion.CASCADE, related_name='dq_runs', to='jobs.job')),
                ('tenant', models.ForeignKey(help_text='Tenant this DQ run belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='dq_runs', to='tenants.tenant')),
            ],
            options={
                'db_table': 'dq_runs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='dqrun',
            index=models.Index(fields=['tenant', 'asset'], name='dq_runs_tenant_asset_idx'),
        ),
        migrations.AddIndex(
            model_name='dqrun',
            index=models.Index(fields=['tenant', 'dataset'], name='dq_runs_tenant_dataset_idx'),
        ),
        migrations.AddIndex(
            model_name='dqrun',
            index=models.Index(fields=['tenant', 'status'], name='dq_runs_tenant_status_idx'),
        ),
        migrations.AddIndex(
            model_name='dqrun',
            index=models.Index(fields=['tenant', 'file'], name='dq_runs_tenant_file_idx'),
        ),
        migrations.AddIndex(
            model_name='dqrun',
            index=models.Index(fields=['job'], name='dq_runs_job_idx'),
        ),
    ]

