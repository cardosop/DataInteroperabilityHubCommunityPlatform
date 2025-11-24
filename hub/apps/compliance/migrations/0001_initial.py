# Generated migration for compliance app

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
            name='ComplianceRun',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('regulations', models.JSONField(blank=True, help_text="List of applicable regulations (e.g., ['GDPR', 'LGPD'])", null=True)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('RUNNING', 'Running'), ('SUCCEEDED', 'Succeeded'), ('FAILED', 'Failed')], default='PENDING', help_text='Compliance run status: PENDING, RUNNING, SUCCEEDED, FAILED', max_length=20)),
                ('overall_status', models.CharField(blank=True, help_text='Overall compliance status: PASS, WARN, FAIL (from result)', max_length=20, null=True)),
                ('risk_level', models.CharField(blank=True, choices=[('NONE', 'None'), ('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High'), ('CRITICAL', 'Critical')], help_text='Risk level: NONE, LOW, MEDIUM, HIGH, CRITICAL', max_length=20, null=True)),
                ('allowed_to_store', models.BooleanField(blank=True, help_text='Whether data is allowed to be stored (NULL if check not completed)', null=True)),
                ('detected_categories_json', models.JSONField(blank=True, help_text='Summary of detected PII categories and counts', null=True)),
                ('column_findings_json', models.JSONField(blank=True, help_text='Per-column PII detection findings', null=True)),
                ('regulation_mapping_json', models.JSONField(blank=True, help_text='Regulatory mapping details (GDPR, LGPD, CCPA, HIPAA, SOX)', null=True)),
                ('started_at', models.DateTimeField(blank=True, help_text='When compliance run started', null=True)),
                ('completed_at', models.DateTimeField(blank=True, help_text='When compliance run completed', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('asset', models.ForeignKey(blank=True, help_text='Asset this compliance run is for (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='compliance_runs', to='assets.asset')),
                ('dataset', models.ForeignKey(blank=True, help_text='Dataset this compliance run is for (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='compliance_runs', to='datasets.dataset')),
                ('file', models.ForeignKey(blank=True, help_text='File this compliance run is for (scan-only, nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='compliance_runs', to='files.file')),
                ('job', models.ForeignKey(help_text='Job that orchestrates this compliance run', on_delete=django.db.models.deletion.CASCADE, related_name='compliance_runs', to='jobs.job')),
                ('tenant', models.ForeignKey(help_text='Tenant this compliance run belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='compliance_runs', to='tenants.tenant')),
            ],
            options={
                'db_table': 'compliance_runs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='compliancerun',
            index=models.Index(fields=['tenant', 'asset'], name='compliance_runs_tenant_asset_idx'),
        ),
        migrations.AddIndex(
            model_name='compliancerun',
            index=models.Index(fields=['tenant', 'dataset'], name='compliance_runs_tenant_dataset_idx'),
        ),
        migrations.AddIndex(
            model_name='compliancerun',
            index=models.Index(fields=['tenant', 'status'], name='compliance_runs_tenant_status_idx'),
        ),
        migrations.AddIndex(
            model_name='compliancerun',
            index=models.Index(fields=['tenant', 'file'], name='compliance_runs_tenant_file_idx'),
        ),
        migrations.AddIndex(
            model_name='compliancerun',
            index=models.Index(fields=['job'], name='compliance_runs_job_idx'),
        ),
    ]

