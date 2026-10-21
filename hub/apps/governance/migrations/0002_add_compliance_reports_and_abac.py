# Generated migration for compliance reports and ABAC

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('governance', '0001_initial'),
        ('tenants', '0001_initial'),
        ('assets', '0001_initial'),
        ('datasets', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Create ComplianceReport table
        migrations.CreateModel(
            name='ComplianceReport',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('regulation', models.CharField(help_text='Regulation: GDPR, HIPAA, SOX, LGPD, CCPA', max_length=20)),
                ('report_type', models.CharField(default='STANDARD', help_text='Report type: STANDARD, SUMMARY, DETAILED', max_length=50)),
                ('report_data', models.JSONField(help_text='Report data (JSON structure)')),
                ('start_date', models.DateTimeField(help_text='Start date for report period')),
                ('end_date', models.DateTimeField(help_text='End date for report period')),
                ('scheduled', models.BooleanField(default=False, help_text='Whether report is scheduled')),
                ('schedule_frequency', models.CharField(blank=True, help_text='Schedule frequency: DAILY, WEEKLY, MONTHLY, QUARTERLY', max_length=20, null=True)),
                ('email_recipients', models.JSONField(blank=True, default=list, help_text='List of email addresses to send report to', null=True)),
                ('email_sent', models.BooleanField(default=False, help_text='Whether report was sent via email')),
                ('email_sent_at', models.DateTimeField(blank=True, help_text='When report was sent via email', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(help_text='Tenant this report belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='compliance_reports', to='tenants.tenant')),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created this report', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_compliance_reports', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'compliance_reports',
                'ordering': ['-created_at'],
            },
        ),
        # Create AccessPolicy table
        migrations.CreateModel(
            name='AccessPolicy',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Policy name', max_length=255)),
                ('description', models.TextField(blank=True, help_text='Policy description', null=True)),
                ('conditions', models.JSONField(help_text='Policy conditions (user attributes, resource attributes, environment)')),
                ('effect', models.CharField(choices=[('ALLOW', 'Allow'), ('DENY', 'Deny')], default='ALLOW', help_text='Policy effect: ALLOW or DENY', max_length=10)),
                ('enabled', models.BooleanField(default=True, help_text='Whether policy is enabled')),
                ('priority', models.IntegerField(default=100, help_text='Policy priority (lower number = higher priority)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('asset', models.ForeignKey(blank=True, help_text='Asset this policy applies to (nullable for tenant-wide)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='access_policies', to='assets.asset')),
                ('dataset', models.ForeignKey(blank=True, help_text='Dataset this policy applies to (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='access_policies', to='datasets.dataset')),
                ('tenant', models.ForeignKey(help_text='Tenant this policy belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='access_policies', to='tenants.tenant')),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created this policy', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_access_policies', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'access_policies',
                'ordering': ['priority', '-created_at'],
            },
        ),
        # Create FieldAccessPolicy table
        migrations.CreateModel(
            name='FieldAccessPolicy',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('field_name', models.CharField(help_text='Field name this policy applies to', max_length=255)),
                ('access_type', models.CharField(choices=[('READ', 'Read'), ('WRITE', 'Write'), ('NONE', 'None')], default='READ', help_text='Access type allowed for this field', max_length=20)),
                ('masking_strategy', models.CharField(blank=True, help_text='Masking strategy: REDACT, HASH, PARTIAL, FORMAT_PRESERVING, NONE', max_length=50, null=True)),
                ('masking_config', models.JSONField(blank=True, help_text='Masking configuration (e.g., partial mask characters, hash algorithm)', null=True)),
                ('enabled', models.BooleanField(default=True, help_text='Whether field policy is enabled')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('access_policy', models.ForeignKey(help_text='Parent access policy', on_delete=django.db.models.deletion.CASCADE, related_name='field_policies', to='governance.accesspolicy')),
                ('dataset', models.ForeignKey(help_text='Dataset this field policy applies to', on_delete=django.db.models.deletion.CASCADE, related_name='field_access_policies', to='datasets.dataset')),
                ('tenant', models.ForeignKey(help_text='Tenant this policy belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='field_access_policies', to='tenants.tenant')),
            ],
            options={
                'db_table': 'field_access_policies',
                'ordering': ['-created_at'],
            },
        ),
        # Add indexes for ComplianceReport
        migrations.AddIndex(
            model_name='compliancereport',
            index=models.Index(fields=['tenant', 'regulation'], name='compliance_r_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='compliancereport',
            index=models.Index(fields=['tenant', 'scheduled'], name='compliance_r_tenant__scheduled_idx'),
        ),
        migrations.AddIndex(
            model_name='compliancereport',
            index=models.Index(fields=['start_date', 'end_date'], name='compliance_r_start_date_end_date_idx'),
        ),
        # Add indexes for AccessPolicy
        migrations.AddIndex(
            model_name='accesspolicy',
            index=models.Index(fields=['tenant', 'enabled'], name='access_polic_tenant__enabled_idx'),
        ),
        migrations.AddIndex(
            model_name='accesspolicy',
            index=models.Index(fields=['tenant', 'asset'], name='access_polic_tenant__asset_idx'),
        ),
        migrations.AddIndex(
            model_name='accesspolicy',
            index=models.Index(fields=['tenant', 'dataset'], name='access_polic_tenant__dataset_idx'),
        ),
        migrations.AddIndex(
            model_name='accesspolicy',
            index=models.Index(fields=['tenant', 'priority'], name='access_polic_tenant__priority_idx'),
        ),
        # Add indexes for FieldAccessPolicy
        migrations.AddIndex(
            model_name='fieldaccesspolicy',
            index=models.Index(fields=['tenant', 'dataset', 'field_name'], name='field_access_tenant__dataset_field_idx'),
        ),
        migrations.AddIndex(
            model_name='fieldaccesspolicy',
            index=models.Index(fields=['tenant', 'access_policy'], name='field_access_tenant__access_policy_idx'),
        ),
        migrations.AddIndex(
            model_name='fieldaccesspolicy',
            index=models.Index(fields=['tenant', 'enabled'], name='field_access_tenant__enabled_idx'),
        ),
        # Add unique constraint for FieldAccessPolicy
        migrations.AddConstraint(
            model_name='fieldaccesspolicy',
            constraint=models.UniqueConstraint(fields=['tenant', 'dataset', 'field_name', 'access_policy'], name='unique_field_access_policy'),
        ),
    ]

