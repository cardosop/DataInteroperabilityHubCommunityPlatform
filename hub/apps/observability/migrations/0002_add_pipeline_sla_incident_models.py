# Generated migration for pipeline monitoring, data SLAs, and incident management models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('observability', '0001_initial_observability'),
        ('tenants', '0001_initial'),
        ('datasets', '0001_initial'),
        ('assets', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Create PipelineExecution table
        migrations.CreateModel(
            name='PipelineExecution',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('pipeline_type', models.CharField(choices=[('SCHEDULED_INGESTION', 'Scheduled Ingestion'), ('DQ_RUN', 'Data Quality Run'), ('COMPLIANCE_RUN', 'Compliance Run'), ('CONTRACT_VALIDATION', 'Contract Validation'), ('SEMANTIC_MAPPING', 'Semantic Mapping')], db_index=True, help_text='Type of pipeline', max_length=50)),
                ('pipeline_id', models.UUIDField(db_index=True, help_text='ID of the pipeline (scheduled_ingestion_id, job_id, etc.)')),
                ('pipeline_name', models.CharField(blank=True, help_text='Name of the pipeline', max_length=255, null=True)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('RUNNING', 'Running'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed'), ('CANCELLED', 'Cancelled')], db_index=True, help_text='Execution status', max_length=20)),
                ('started_at', models.DateTimeField(blank=True, db_index=True, help_text='When execution started', null=True)),
                ('completed_at', models.DateTimeField(blank=True, db_index=True, help_text='When execution completed', null=True)),
                ('execution_time_seconds', models.FloatField(blank=True, help_text='Execution time in seconds', null=True)),
                ('latency_ms', models.FloatField(blank=True, help_text='Latency in milliseconds', null=True)),
                ('throughput_items_per_second', models.FloatField(blank=True, help_text='Throughput (items processed per second)', null=True)),
                ('items_processed', models.IntegerField(default=0, help_text='Number of items processed')),
                ('items_failed', models.IntegerField(default=0, help_text='Number of items that failed')),
                ('error_message', models.TextField(blank=True, help_text='Error message if execution failed', null=True)),
                ('error_code', models.CharField(blank=True, db_index=True, help_text='Error code for categorization', max_length=50, null=True)),
                ('resource_type', models.CharField(blank=True, help_text='Resource type: DATASET, ASSET, CONTRACT, etc.', max_length=50, null=True)),
                ('resource_id', models.UUIDField(blank=True, help_text='ID of the resource', null=True)),
                ('result_json', models.JSONField(blank=True, default=dict, help_text='Execution result data', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(help_text='Tenant this execution belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='pipeline_executions', to='tenants.tenant')),
            ],
            options={
                'db_table': 'pipeline_executions',
                'ordering': ['-created_at'],
            },
        ),
        # Create DataSLA table
        migrations.CreateModel(
            name='DataSLA',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='SLA name', max_length=255)),
                ('description', models.TextField(blank=True, help_text='SLA description', null=True)),
                ('sla_type', models.CharField(choices=[('AVAILABILITY', 'Availability'), ('FRESHNESS', 'Freshness'), ('QUALITY', 'Quality')], db_index=True, help_text='Type of SLA', max_length=50)),
                ('availability_target_percent', models.FloatField(blank=True, help_text='Availability target percentage (e.g., 99.9)', null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('freshness_sla_seconds', models.BigIntegerField(blank=True, help_text='Freshness SLA in seconds (maximum age of data)', null=True)),
                ('quality_target_score', models.FloatField(blank=True, help_text='Quality target score (0.0 to 1.0)', null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1)])),
                ('is_active', models.BooleanField(db_index=True, default=True, help_text='Whether SLA is active')),
                ('current_compliance_percent', models.FloatField(blank=True, help_text='Current compliance percentage', null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('last_compliance_check', models.DateTimeField(blank=True, help_text='Last time compliance was checked', null=True)),
                ('is_violated', models.BooleanField(db_index=True, default=False, help_text='Whether SLA is currently violated')),
                ('violation_count', models.IntegerField(default=0, help_text='Number of times SLA has been violated')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('asset', models.ForeignKey(blank=True, help_text='Asset this SLA is for', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='data_slas', to='assets.asset')),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created the SLA', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_slas', to=settings.AUTH_USER_MODEL)),
                ('dataset', models.ForeignKey(blank=True, help_text='Dataset this SLA is for', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='data_slas', to='datasets.dataset')),
                ('tenant', models.ForeignKey(help_text='Tenant this SLA belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='data_slas', to='tenants.tenant')),
            ],
            options={
                'db_table': 'data_slas',
                'ordering': ['-created_at'],
            },
        ),
        # Create DataIncident table
        migrations.CreateModel(
            name='DataIncident',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(help_text='Incident title', max_length=255)),
                ('description', models.TextField(help_text='Incident description')),
                ('incident_type', models.CharField(choices=[('FRESHNESS_VIOLATION', 'Freshness Violation'), ('QUALITY_VIOLATION', 'Quality Violation'), ('AVAILABILITY_VIOLATION', 'Availability Violation'), ('SCHEMA_DRIFT', 'Schema Drift'), ('PIPELINE_FAILURE', 'Pipeline Failure'), ('DATA_LOSS', 'Data Loss'), ('COMPLIANCE_VIOLATION', 'Compliance Violation'), ('OTHER', 'Other')], db_index=True, help_text='Type of incident', max_length=50)),
                ('severity', models.CharField(choices=[('CRITICAL', 'Critical'), ('HIGH', 'High'), ('MEDIUM', 'Medium'), ('LOW', 'Low')], db_index=True, default='MEDIUM', help_text='Incident severity', max_length=20)),
                ('status', models.CharField(choices=[('DETECTED', 'Detected'), ('TRIAGED', 'Triaged'), ('IN_PROGRESS', 'In Progress'), ('RESOLVED', 'Resolved')], db_index=True, default='DETECTED', help_text='Incident status', max_length=20)),
                ('detected_at', models.DateTimeField(auto_now_add=True, db_index=True, help_text='When incident was detected')),
                ('triaged_at', models.DateTimeField(blank=True, help_text='When incident was triaged', null=True)),
                ('in_progress_at', models.DateTimeField(blank=True, help_text='When incident was marked as in progress', null=True)),
                ('resolved_at', models.DateTimeField(blank=True, db_index=True, help_text='When incident was resolved', null=True)),
                ('resolution_time_seconds', models.BigIntegerField(blank=True, help_text='Time to resolve in seconds', null=True)),
                ('resource_type', models.CharField(blank=True, help_text='Resource type: DATASET, ASSET, CONTRACT, PIPELINE, etc.', max_length=50, null=True)),
                ('resource_id', models.UUIDField(blank=True, help_text='ID of the resource', null=True)),
                ('root_cause', models.TextField(blank=True, help_text='Root cause analysis', null=True)),
                ('resolution_notes', models.TextField(blank=True, help_text='Resolution notes', null=True)),
                ('metadata_json', models.JSONField(blank=True, default=dict, help_text='Additional incident metadata', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_to', models.ForeignKey(blank=True, help_text='User assigned to resolve the incident', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_incidents', to=settings.AUTH_USER_MODEL)),
                ('detected_by', models.ForeignKey(blank=True, help_text='User or system that detected the incident', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='detected_incidents', to=settings.AUTH_USER_MODEL)),
                ('resolved_by', models.ForeignKey(blank=True, help_text='User who resolved the incident', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_incidents', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(help_text='Tenant this incident belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='data_incidents', to='tenants.tenant')),
            ],
            options={
                'db_table': 'data_incidents',
                'ordering': ['-detected_at'],
            },
        ),
        # Add indexes for PipelineExecution
        migrations.AddIndex(
            model_name='pipelineexecution',
            index=models.Index(fields=['tenant', 'pipeline_type', 'status'], name='pipeline_ex_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='pipelineexecution',
            index=models.Index(fields=['tenant', 'pipeline_type', 'created_at'], name='pipeline_ex_tenant__idx2'),
        ),
        migrations.AddIndex(
            model_name='pipelineexecution',
            index=models.Index(fields=['pipeline_id', 'status'], name='pipeline_ex_pipelin_idx'),
        ),
        migrations.AddIndex(
            model_name='pipelineexecution',
            index=models.Index(fields=['status', 'created_at'], name='pipeline_ex_status__idx'),
        ),
        migrations.AddIndex(
            model_name='pipelineexecution',
            index=models.Index(fields=['resource_type', 'resource_id'], name='pipeline_ex_resour_idx'),
        ),
        # Add indexes for DataSLA
        migrations.AddIndex(
            model_name='datasla',
            index=models.Index(fields=['tenant', 'sla_type', 'is_active'], name='data_slas_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='datasla',
            index=models.Index(fields=['tenant', 'dataset', 'sla_type'], name='data_slas_tenant__idx2'),
        ),
        migrations.AddIndex(
            model_name='datasla',
            index=models.Index(fields=['tenant', 'asset', 'sla_type'], name='data_slas_tenant__idx3'),
        ),
        migrations.AddIndex(
            model_name='datasla',
            index=models.Index(fields=['tenant', 'is_violated', 'is_active'], name='data_slas_tenant__idx4'),
        ),
        # Add constraint for DataSLA
        migrations.AddConstraint(
            model_name='datasla',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(sla_type='AVAILABILITY', availability_target_percent__isnull=False) |
                    models.Q(sla_type='FRESHNESS', freshness_sla_seconds__isnull=False) |
                    models.Q(sla_type='QUALITY', quality_target_score__isnull=False)
                ),
                name='sla_has_appropriate_target'
            ),
        ),
        # Add indexes for DataIncident
        migrations.AddIndex(
            model_name='dataincident',
            index=models.Index(fields=['tenant', 'status', 'severity'], name='data_incid_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='dataincident',
            index=models.Index(fields=['tenant', 'incident_type', 'status'], name='data_incid_tenant__idx2'),
        ),
        migrations.AddIndex(
            model_name='dataincident',
            index=models.Index(fields=['tenant', 'assigned_to', 'status'], name='data_incid_tenant__idx3'),
        ),
        migrations.AddIndex(
            model_name='dataincident',
            index=models.Index(fields=['status', 'detected_at'], name='data_incid_status__idx'),
        ),
        migrations.AddIndex(
            model_name='dataincident',
            index=models.Index(fields=['resource_type', 'resource_id'], name='data_incid_resour_idx'),
        ),
    ]

