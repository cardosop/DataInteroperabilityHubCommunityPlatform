# Generated migration for scheduled ingestion models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants', '0001_initial'),
        ('assets', '0001_initial'),
        ('contracts', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ScheduledIngestion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('name', models.CharField(help_text='Scheduled ingestion name (unique per tenant)', max_length=255)),
                ('description', models.TextField(blank=True, help_text='Optional description', null=True)),
                ('source_type', models.CharField(choices=[('S3', 'Amazon S3'), ('GCS', 'Google Cloud Storage'), ('AZURE_BLOB', 'Azure Blob Storage'), ('HTTP', 'HTTP'), ('HTTPS', 'HTTPS'), ('FTP', 'FTP'), ('SFTP', 'SFTP'), ('DATABASE', 'Database')], help_text='Source type: S3, GCS, AZURE_BLOB, HTTP, FTP, SFTP, DATABASE', max_length=50)),
                ('source_config', models.JSONField(help_text='Source configuration (connection details, credentials, paths) stored securely')),
                ('schedule_type', models.CharField(choices=[('DAILY', 'Daily'), ('WEEKLY', 'Weekly'), ('MONTHLY', 'Monthly'), ('CUSTOM_CRON', 'Custom Cron')], default='DAILY', help_text='Schedule type: DAILY, WEEKLY, MONTHLY, CUSTOM_CRON', max_length=20)),
                ('schedule_config', models.JSONField(help_text='Schedule configuration (cron expression, timezone, days of week)')),
                ('file_pattern', models.CharField(help_text='File pattern (regex pattern for matching files, e.g., orders_YYYY-MM-DD.csv)', max_length=255)),
                ('auto_create_asset', models.BooleanField(default=False, help_text='Create asset if it does not exist')),
                ('auto_activate', models.BooleanField(default=False, help_text='Auto-activate asset after ingestion')),
                ('status', models.CharField(choices=[('ACTIVE', 'Active'), ('PAUSED', 'Paused'), ('ERROR', 'Error')], default='ACTIVE', help_text='Status: ACTIVE, PAUSED, ERROR', max_length=20)),
                ('next_run_at', models.DateTimeField(blank=True, help_text='Next scheduled run time (calculated based on schedule)', null=True)),
                ('prefect_deployment_id', models.CharField(blank=True, help_text='Prefect deployment ID (format: {tenant_id}-{scheduled_ingestion_id})', max_length=255, null=True)),
                ('prefect_work_pool_name', models.CharField(default='default', help_text='Prefect work pool name', max_length=255)),
                ('last_processed_file', models.CharField(blank=True, help_text='Last processed file path/key (for incremental ingestion)', max_length=500, null=True)),
                ('last_processed_timestamp', models.DateTimeField(blank=True, help_text='Last processed file timestamp (for incremental ingestion)', null=True)),
                ('ingestion_state', models.JSONField(blank=True, default=dict, help_text='Ingestion state (processed files list, incremental state, etc.)', null=True)),
                ('error_message', models.TextField(blank=True, help_text='Error message if status is ERROR', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('asset', models.ForeignKey(blank=True, help_text='Asset to associate ingested data with (optional)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='scheduled_ingestions', to='assets.asset')),
                ('contract', models.ForeignKey(blank=True, help_text='Contract to use for ingested data (optional - can create new contract per ingestion)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='scheduled_ingestions', to='contracts.contract')),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created the scheduled ingestion', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_scheduled_ingestions', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(help_text='Tenant this scheduled ingestion belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='scheduled_ingestions', to='tenants.tenant')),
            ],
            options={
                'db_table': 'scheduled_ingestions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ScheduledIngestionRun',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('RUNNING', 'Running'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed'), ('CANCELLED', 'Cancelled')], default='PENDING', help_text='Run status: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED', max_length=20)),
                ('started_at', models.DateTimeField(blank=True, help_text='When run started', null=True)),
                ('completed_at', models.DateTimeField(blank=True, help_text='When run completed (success or failure)', null=True)),
                ('prefect_flow_run_id', models.CharField(blank=True, help_text='Prefect flow run ID', max_length=255, null=True)),
                ('job_id', models.UUIDField(blank=True, help_text='Job ID (FK to jobs table)', null=True)),
                ('files_found', models.IntegerField(default=0, help_text='Number of files found')),
                ('files_processed', models.IntegerField(default=0, help_text='Number of files successfully processed')),
                ('files_failed', models.IntegerField(default=0, help_text='Number of files that failed to process')),
                ('datasets_created', models.IntegerField(default=0, help_text='Number of datasets created')),
                ('error_message', models.TextField(blank=True, help_text='Error message if run failed', null=True)),
                ('result_json', models.JSONField(blank=True, default=dict, help_text='Run result data (files processed, datasets created, etc.)', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('scheduled_ingestion', models.ForeignKey(help_text='Scheduled ingestion this run belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='runs', to='scheduled_ingestion.scheduledingestion')),
            ],
            options={
                'db_table': 'scheduled_ingestion_runs',
                'ordering': ['-created_at'],
            },
        ),
        # Note: Indexes for ScheduledIngestion are defined in model Meta class
        # and will be created automatically, so we don't need to add them here
        migrations.AddConstraint(
            model_name='scheduledingestion',
            constraint=models.UniqueConstraint(fields=['tenant', 'name'], name='unique_scheduled_ingestion_name_per_tenant'),
        ),
        # Note: Indexes for ScheduledIngestionRun are defined in model Meta class
        # and will be created automatically, so we don't need to add them here
    ]

