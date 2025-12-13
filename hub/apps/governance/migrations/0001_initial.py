# Generated migration for governance app

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
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DataClassification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('field_name', models.CharField(blank=True, help_text='Field name for field-level classification (nullable)', max_length=255, null=True)),
                ('category', models.CharField(choices=[('PUBLIC', 'Public'), ('INTERNAL', 'Internal'), ('CONFIDENTIAL', 'Confidential'), ('RESTRICTED', 'Restricted'), ('PII', 'Personally Identifiable Information'), ('PHI', 'Protected Health Information'), ('PCI', 'Payment Card Information'), ('FINANCIAL', 'Financial Information'), ('LEGAL', 'Legal Information')], help_text='Classification category', max_length=50)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('AUTO_CLASSIFIED', 'Auto-Classified'), ('MANUAL_REVIEW', 'Manual Review'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected')], default='AUTO_CLASSIFIED', help_text='Classification status', max_length=20)),
                ('confidence_score', models.FloatField(blank=True, help_text='Confidence score (0.0-1.0) for automatic classification', null=True)),
                ('classification_rules', models.JSONField(blank=True, default=list, help_text='Rules that matched for this classification', null=True)),
                ('detected_patterns', models.JSONField(blank=True, default=list, help_text='Detected patterns (PII types, keywords, etc.)', null=True)),
                ('manual_review_notes', models.TextField(blank=True, help_text='Notes from manual review', null=True)),
                ('reviewed_at', models.DateTimeField(blank=True, help_text='When classification was reviewed', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('asset', models.ForeignKey(blank=True, help_text='Asset this classification is for (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='classifications', to='assets.asset')),
                ('dataset', models.ForeignKey(blank=True, help_text='Dataset this classification is for (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='classifications', to='datasets.dataset')),
                ('reviewed_by', models.ForeignKey(blank=True, help_text='User who reviewed this classification', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_classifications', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(help_text='Tenant this classification belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='data_classifications', to='tenants.tenant')),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created this classification', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_classifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'data_classifications',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='RetentionPolicy',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Policy name', max_length=255)),
                ('description', models.TextField(blank=True, help_text='Policy description', null=True)),
                ('policy_type', models.CharField(choices=[('TIME_BASED', 'Time-Based'), ('EVENT_BASED', 'Event-Based')], help_text='Policy type: TIME_BASED or EVENT_BASED', max_length=20)),
                ('retention_period_days', models.IntegerField(blank=True, help_text='Retention period in days (for time-based policies)', null=True)),
                ('event_trigger', models.CharField(blank=True, help_text="Event trigger (e.g., 'contract_expired', 'project_completed')", max_length=255, null=True)),
                ('action', models.CharField(choices=[('SOFT_DELETE', 'Soft Delete'), ('HARD_DELETE', 'Hard Delete'), ('ARCHIVE', 'Archive')], default='SOFT_DELETE', help_text='Action to take when retention period expires', max_length=20)),
                ('grace_period_days', models.IntegerField(default=30, help_text='Grace period in days before hard delete (for soft delete)')),
                ('legal_hold', models.BooleanField(default=False, help_text='Whether data is under legal hold (prevents deletion)')),
                ('legal_hold_reason', models.TextField(blank=True, help_text='Reason for legal hold', null=True)),
                ('legal_hold_expires_at', models.DateTimeField(blank=True, help_text='When legal hold expires (nullable for indefinite hold)', null=True)),
                ('enabled', models.BooleanField(default=True, help_text='Whether policy is enabled')),
                ('last_enforced_at', models.DateTimeField(blank=True, help_text='When policy was last enforced', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('asset', models.ForeignKey(blank=True, help_text='Asset this policy applies to (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='retention_policies', to='assets.asset')),
                ('dataset', models.ForeignKey(blank=True, help_text='Dataset this policy applies to (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='retention_policies', to='datasets.dataset')),
                ('file', models.ForeignKey(blank=True, help_text='File this policy applies to (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='retention_policies', to='files.file')),
                ('tenant', models.ForeignKey(help_text='Tenant this retention policy belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='retention_policies', to='tenants.tenant')),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created this policy', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_retention_policies', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'retention_policies',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AccessRequest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('reason', models.TextField(help_text='Reason for access request')),
                ('requested_access_type', models.CharField(help_text="Type of access requested (e.g., 'READ', 'WRITE', 'DOWNLOAD')", max_length=50)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'), ('EXPIRED', 'Expired'), ('REVOKED', 'Revoked')], default='PENDING', help_text='Access request status', max_length=20)),
                ('requires_approval', models.BooleanField(default=True, help_text='Whether request requires approval')),
                ('approval_workflow', models.JSONField(blank=True, default=list, help_text='Approval workflow steps (for multi-step approval)', null=True)),
                ('current_approval_step', models.IntegerField(default=0, help_text='Current approval step index')),
                ('approvers', models.JSONField(blank=True, default=list, help_text='List of approver user IDs', null=True)),
                ('approved_at', models.DateTimeField(blank=True, help_text='When request was approved', null=True)),
                ('rejection_reason', models.TextField(blank=True, help_text='Reason for rejection', null=True)),
                ('rejected_at', models.DateTimeField(blank=True, help_text='When request was rejected', null=True)),
                ('expires_at', models.DateTimeField(blank=True, help_text='When access expires (nullable for permanent access)', null=True)),
                ('access_granted_at', models.DateTimeField(blank=True, help_text='When access was granted', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('asset', models.ForeignKey(blank=True, help_text='Asset access is requested for (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='access_requests', to='assets.asset')),
                ('dataset', models.ForeignKey(blank=True, help_text='Dataset access is requested for (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='access_requests', to='datasets.dataset')),
                ('file', models.ForeignKey(blank=True, help_text='File access is requested for (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='access_requests', to='files.file')),
                ('requested_by', models.ForeignKey(help_text='User requesting access', on_delete=django.db.models.deletion.CASCADE, related_name='requested_access', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(help_text='Tenant this access request belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='access_requests', to='tenants.tenant')),
                ('approved_by', models.ForeignKey(blank=True, help_text='User who approved this request', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_access_requests', to=settings.AUTH_USER_MODEL)),
                ('rejected_by', models.ForeignKey(blank=True, help_text='User who rejected this request', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rejected_access_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'access_requests',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='dataclassification',
            index=models.Index(fields=['tenant', 'asset'], name='data_classif_tenant_asset_idx'),
        ),
        migrations.AddIndex(
            model_name='dataclassification',
            index=models.Index(fields=['tenant', 'dataset'], name='data_classif_tenant_dataset_idx'),
        ),
        migrations.AddIndex(
            model_name='dataclassification',
            index=models.Index(fields=['tenant', 'category'], name='data_classif_tenant_category_idx'),
        ),
        migrations.AddIndex(
            model_name='dataclassification',
            index=models.Index(fields=['tenant', 'status'], name='data_classif_tenant_status_idx'),
        ),
        migrations.AddIndex(
            model_name='dataclassification',
            index=models.Index(fields=['tenant', 'asset', 'field_name'], name='data_classif_tenant_asset_field_idx'),
        ),
        migrations.AddIndex(
            model_name='retentionpolicy',
            index=models.Index(fields=['tenant', 'asset'], name='retention_po_tenant_asset_idx'),
        ),
        migrations.AddIndex(
            model_name='retentionpolicy',
            index=models.Index(fields=['tenant', 'dataset'], name='retention_po_tenant_dataset_idx'),
        ),
        migrations.AddIndex(
            model_name='retentionpolicy',
            index=models.Index(fields=['tenant', 'file'], name='retention_po_tenant__file_idx'),
        ),
        migrations.AddIndex(
            model_name='retentionpolicy',
            index=models.Index(fields=['tenant', 'enabled'], name='retention_po_tenant__enabled_idx'),
        ),
        migrations.AddIndex(
            model_name='retentionpolicy',
            index=models.Index(fields=['tenant', 'legal_hold'], name='retention_po_tenant__legal_idx'),
        ),
        migrations.AddIndex(
            model_name='retentionpolicy',
            index=models.Index(fields=['legal_hold_expires_at'], name='retention_po_legal_hold_expires_idx'),
        ),
        migrations.AddIndex(
            model_name='accessrequest',
            index=models.Index(fields=['tenant', 'requested_by'], name='access_reque_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='accessrequest',
            index=models.Index(fields=['tenant', 'asset'], name='access_reque_tenant__asset_idx'),
        ),
        migrations.AddIndex(
            model_name='accessrequest',
            index=models.Index(fields=['tenant', 'dataset'], name='access_reque_tenant__dataset_idx'),
        ),
        migrations.AddIndex(
            model_name='accessrequest',
            index=models.Index(fields=['tenant', 'file'], name='access_reque_tenant__file_idx'),
        ),
        migrations.AddIndex(
            model_name='accessrequest',
            index=models.Index(fields=['tenant', 'status'], name='access_reque_tenant__status_idx'),
        ),
        migrations.AddIndex(
            model_name='accessrequest',
            index=models.Index(fields=['expires_at'], name='access_reque_expires_at_idx'),
        ),
        migrations.AddConstraint(
            model_name='dataclassification',
            constraint=models.UniqueConstraint(condition=models.Q(('asset__isnull', False), ('field_name__isnull', False)), fields=['tenant', 'asset', 'field_name'], name='unique_field_classification'),
        ),
        migrations.AddConstraint(
            model_name='dataclassification',
            constraint=models.UniqueConstraint(condition=models.Q(('dataset__isnull', False), ('field_name__isnull', False)), fields=['tenant', 'dataset', 'field_name'], name='unique_dataset_field_classification'),
        ),
    ]

