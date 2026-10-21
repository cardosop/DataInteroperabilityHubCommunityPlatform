# Generated manually for TenantConfig model

import django.core.validators
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TenantConfig',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('default_dq_profile', models.CharField(blank=True, help_text='Default DQ profile key (e.g., intake_basic_gx, intake_basic_soda)', max_length=100, null=True)),
                ('allowed_compliance_regimes', models.JSONField(default=list, help_text="List of compliance regimes available to this tenant (e.g., ['GDPR', 'LGPD', 'CCPA'])")),
                ('default_compliance_regimes', models.JSONField(default=list, help_text='Default compliance regimes applied to intake flows (subset of allowed_compliance_regimes)')),
                ('data_retention_days', models.IntegerField(blank=True, help_text='Data retention period in days (90-3650)', null=True, validators=[django.core.validators.MinValueValidator(90, message='Data retention must be at least 90 days'), django.core.validators.MaxValueValidator(3650, message='Data retention cannot exceed 3650 days (10 years)')])),
                ('rate_limits', models.JSONField(default=dict, help_text='Per-endpoint category rate limits (JSON structure)')),
                ('max_file_size_bytes', models.BigIntegerField(blank=True, help_text='Maximum file size for uploads in bytes', null=True, validators=[django.core.validators.MinValueValidator(1)])),
                ('max_job_concurrency', models.IntegerField(blank=True, help_text='Maximum concurrent running jobs for this tenant', null=True, validators=[django.core.validators.MinValueValidator(1)])),
                ('max_queued_jobs', models.IntegerField(blank=True, help_text='Maximum queued jobs for this tenant', null=True, validators=[django.core.validators.MinValueValidator(1)])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.OneToOneField(help_text='Tenant this configuration belongs to', on_delete=models.CASCADE, related_name='config', to='tenants.tenant')),
            ],
            options={
                'db_table': 'tenant_configs',
                'ordering': ['tenant'],
                'indexes': [models.Index(fields=['tenant'], name='tenant_configs_tenant_idx')],
            },
        ),
    ]

