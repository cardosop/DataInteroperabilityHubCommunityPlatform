# Generated migration for orchestration app

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
            name='WorkflowDefinition',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(db_index=True, help_text="Workflow name (e.g., 'contract_creation', 'scheduled_ingestion')", max_length=255)),
                ('version', models.CharField(default='1.0.0', help_text='Workflow version (semantic versioning: major.minor.patch)', max_length=50)),
                ('description', models.TextField(blank=True, help_text='Workflow description', null=True)),
                ('dsl_json', models.JSONField(help_text='Workflow DSL definition (JSON format)')),
                ('dsl_yaml', models.TextField(blank=True, help_text='Workflow DSL definition (YAML format, optional)', null=True)),
                ('is_active', models.BooleanField(db_index=True, default=True, help_text='Whether this workflow version is active (new instances use active version)')),
                ('dependencies', models.JSONField(default=list, help_text='List of workflow names this workflow depends on')),
                ('metadata', models.JSONField(default=dict, help_text='Workflow metadata (tags, categories, etc.)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created the workflow definition', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_workflow_definitions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'workflow_definitions',
                'ordering': ['name', '-version'],
            },
        ),
        migrations.CreateModel(
            name='WorkflowInstance',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('workflow_name', models.CharField(db_index=True, help_text='Workflow name (denormalized for performance)', max_length=255)),
                ('workflow_version', models.CharField(db_index=True, help_text='Workflow version (denormalized for performance)', max_length=50)),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('RUNNING', 'Running'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed'), ('CANCELLED', 'Cancelled'), ('PAUSED', 'Paused'), ('ROLLING_BACK', 'Rolling Back'), ('ROLLED_BACK', 'Rolled Back')], db_index=True, default='DRAFT', help_text='Workflow instance status', max_length=20)),
                ('current_step_index', models.IntegerField(default=0, help_text='Current step index (0-based)')),
                ('input_data', models.JSONField(default=dict, help_text='Workflow input data')),
                ('output_data', models.JSONField(blank=True, default=dict, help_text='Workflow output data (populated on completion)', null=True)),
                ('state_data', models.JSONField(default=dict, help_text='Workflow state data (shared state between steps)')),
                ('error_message', models.TextField(blank=True, help_text='Error message if workflow failed', null=True)),
                ('error_details', models.JSONField(blank=True, help_text='Detailed error information (stack trace, context, etc.)', null=True)),
                ('retry_count', models.IntegerField(default=0, help_text='Number of retries attempted')),
                ('max_retries', models.IntegerField(default=3, help_text='Maximum number of retries allowed')),
                ('timeout_seconds', models.IntegerField(blank=True, help_text='Workflow timeout in seconds', null=True)),
                ('started_at', models.DateTimeField(blank=True, help_text='When workflow execution started', null=True)),
                ('completed_at', models.DateTimeField(blank=True, help_text='When workflow execution completed (success or failure)', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created the workflow instance', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_workflow_instances', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(blank=True, help_text='Tenant this workflow instance belongs to (nullable for system workflows)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='workflow_instances', to='tenants.tenant')),
                ('workflow_definition', models.ForeignKey(help_text='Workflow definition this instance belongs to', on_delete=django.db.models.deletion.PROTECT, related_name='instances', to='orchestration.workflowdefinition')),
            ],
            options={
                'db_table': 'workflow_instances',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='WorkflowStep',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('step_index', models.IntegerField(db_index=True, help_text='Step index within workflow (0-based)')),
                ('step_name', models.CharField(db_index=True, help_text='Step name (from workflow definition)', max_length=255)),
                ('step_type', models.CharField(help_text='Step type (task, parallel, conditional, etc.)', max_length=50)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('RUNNING', 'Running'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed'), ('SKIPPED', 'Skipped'), ('COMPENSATED', 'Compensated')], db_index=True, default='PENDING', help_text='Step status', max_length=20)),
                ('input_data', models.JSONField(blank=True, default=dict, help_text='Step input data', null=True)),
                ('output_data', models.JSONField(blank=True, default=dict, help_text='Step output data', null=True)),
                ('error_message', models.TextField(blank=True, help_text='Error message if step failed', null=True)),
                ('error_details', models.JSONField(blank=True, help_text='Detailed error information', null=True)),
                ('retry_count', models.IntegerField(default=0, help_text='Number of retries attempted for this step')),
                ('compensation_data', models.JSONField(blank=True, default=dict, help_text='Compensation data (for rollback)', null=True)),
                ('started_at', models.DateTimeField(blank=True, help_text='When step execution started', null=True)),
                ('completed_at', models.DateTimeField(blank=True, help_text='When step execution completed', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('workflow_instance', models.ForeignKey(help_text='Workflow instance this step belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='steps', to='orchestration.workflowinstance')),
            ],
            options={
                'db_table': 'workflow_steps',
                'ordering': ['workflow_instance', 'step_index'],
            },
        ),
        migrations.CreateModel(
            name='WorkflowState',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('snapshot_type', models.CharField(db_index=True, help_text='Snapshot type (checkpoint, recovery, debug, etc.)', max_length=50)),
                ('state_data', models.JSONField(help_text='Complete workflow state snapshot')),
                ('step_states', models.JSONField(default=list, help_text='Step states snapshot')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('workflow_instance', models.ForeignKey(help_text='Workflow instance this state snapshot belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='state_snapshots', to='orchestration.workflowinstance')),
            ],
            options={
                'db_table': 'workflow_states',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='workflowdefinition',
            index=models.Index(fields=['name', 'is_active'], name='workflow_def_name_active_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowdefinition',
            index=models.Index(fields=['name', 'version'], name='workflow_def_name_version_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowdefinition',
            index=models.Index(fields=['is_active', 'created_at'], name='workflow_def_active_created_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowinstance',
            index=models.Index(fields=['tenant', 'status'], name='workflow_inst_tenant_status_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowinstance',
            index=models.Index(fields=['tenant', 'workflow_name', 'status'], name='workflow_inst_tenant_name_status_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowinstance',
            index=models.Index(fields=['status', 'created_at'], name='workflow_inst_status_created_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowinstance',
            index=models.Index(fields=['workflow_name', 'status', 'created_at'], name='workflow_inst_name_status_created_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowinstance',
            index=models.Index(fields=['status', 'started_at'], name='workflow_inst_status_started_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowstep',
            index=models.Index(fields=['workflow_instance', 'status'], name='workflow_step_inst_status_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowstep',
            index=models.Index(fields=['workflow_instance', 'step_index'], name='workflow_step_inst_index_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowstep',
            index=models.Index(fields=['status', 'created_at'], name='workflow_step_status_created_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowstate',
            index=models.Index(fields=['workflow_instance', 'snapshot_type', '-created_at'], name='workflow_state_inst_type_created_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowstate',
            index=models.Index(fields=['snapshot_type', 'created_at'], name='workflow_state_type_created_idx'),
        ),
        migrations.AddConstraint(
            model_name='workflowdefinition',
            constraint=models.UniqueConstraint(fields=['name', 'version'], name='workflow_def_name_version_unique'),
        ),
        migrations.AddConstraint(
            model_name='workflowstep',
            constraint=models.UniqueConstraint(fields=['workflow_instance', 'step_index'], name='workflow_step_inst_index_unique'),
        ),
    ]

