# Generated migration for Access Analytics and Certification

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('governance', '0002_add_compliance_reports_and_abac'),
        ('tenants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('assets', '0001_initial'),
        ('datasets', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccessLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('resource_type', models.CharField(help_text='Resource type (ASSET, DATASET, FILE, etc.)', max_length=50)),
                ('resource_id', models.UUIDField(help_text='Resource UUID')),
                ('action', models.CharField(choices=[('READ', 'Read'), ('WRITE', 'Write'), ('DELETE', 'Delete'), ('DOWNLOAD', 'Download'), ('UPLOAD', 'Upload')], help_text='Action attempted', max_length=20)),
                ('result', models.CharField(choices=[('ALLOWED', 'Allowed'), ('DENIED', 'Denied'), ('MASKED', 'Masked'), ('PARTIAL', 'Partial')], help_text='Access result', max_length=20)),
                ('policy_evaluation', models.JSONField(blank=True, help_text='Policy evaluation details (policy ID, conditions matched, etc.)', null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, help_text='IP address of the request', null=True)),
                ('user_agent', models.CharField(blank=True, help_text='User agent string', max_length=500, null=True)),
                ('is_anomaly', models.BooleanField(default=False, help_text='Whether this access was flagged as anomalous')),
                ('anomaly_reason', models.TextField(blank=True, help_text='Reason for anomaly flag', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(help_text='Tenant this access log belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='access_logs', to='tenants.tenant')),
                ('user', models.ForeignKey(blank=True, help_text='User who made the access attempt', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='access_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'access_logs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AccessCertification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('certification_type', models.CharField(choices=[('USER_LEVEL', 'User Level'), ('ASSET_LEVEL', 'Asset Level'), ('DATASET_LEVEL', 'Dataset Level')], help_text='Type of certification', max_length=50)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('IN_PROGRESS', 'In Progress'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'), ('EXPIRED', 'Expired')], default='PENDING', help_text='Certification status', max_length=20)),
                ('review_notes', models.TextField(blank=True, help_text='Review notes from certifier', null=True)),
                ('expires_at', models.DateTimeField(help_text='Certification expiration date')),
                ('certified_at', models.DateTimeField(blank=True, help_text='When certification was approved', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('asset', models.ForeignKey(blank=True, help_text='Asset access being certified (nullable for user-level certification)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='access_certifications', to='assets.asset')),
                ('dataset', models.ForeignKey(blank=True, help_text='Dataset access being certified (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='access_certifications', to='datasets.dataset')),
                ('reviewer', models.ForeignKey(blank=True, help_text='User reviewing this certification', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_certifications', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(help_text='Tenant this certification belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='access_certifications', to='tenants.tenant')),
                ('user', models.ForeignKey(help_text='User being certified', on_delete=django.db.models.deletion.CASCADE, related_name='access_certifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'access_certifications',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='accesslog',
            index=models.Index(fields=['tenant', 'user', 'created_at'], name='access_logs_tenant_user_idx'),
        ),
        migrations.AddIndex(
            model_name='accesslog',
            index=models.Index(fields=['tenant', 'resource_type', 'resource_id', 'created_at'], name='access_logs_tenant_resource_idx'),
        ),
        migrations.AddIndex(
            model_name='accesslog',
            index=models.Index(fields=['tenant', 'action', 'result', 'created_at'], name='access_logs_tenant_action_idx'),
        ),
        migrations.AddIndex(
            model_name='accesslog',
            index=models.Index(fields=['tenant', 'is_anomaly', 'created_at'], name='access_logs_tenant_anomaly_idx'),
        ),
        migrations.AddIndex(
            model_name='accesslog',
            index=models.Index(fields=['created_at'], name='access_logs_created_at_idx'),
        ),
        migrations.AddIndex(
            model_name='accesscertification',
            index=models.Index(fields=['tenant', 'user', 'status'], name='access_certifications_tenant_user_idx'),
        ),
        migrations.AddIndex(
            model_name='accesscertification',
            index=models.Index(fields=['tenant', 'asset', 'status'], name='access_certifications_tenant_asset_idx'),
        ),
        migrations.AddIndex(
            model_name='accesscertification',
            index=models.Index(fields=['tenant', 'dataset', 'status'], name='access_certifications_tenant_dataset_idx'),
        ),
        migrations.AddIndex(
            model_name='accesscertification',
            index=models.Index(fields=['tenant', 'expires_at'], name='access_certifications_tenant_expires_idx'),
        ),
        migrations.AddIndex(
            model_name='accesscertification',
            index=models.Index(fields=['status', 'expires_at'], name='access_certifications_status_expires_idx'),
        ),
    ]

