# Generated migration for schema evolution tracking

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0003_add_version_history_fields'),
    ]

    operations = [
        # Create SchemaVersion table
        migrations.CreateModel(
            name='SchemaVersion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('schema_json', models.JSONField(help_text='Complete schema JSON snapshot')),
                ('compatibility_level', models.CharField(help_text='Compatibility level: FULLY_COMPATIBLE, BACKWARD_COMPATIBLE, FORWARD_COMPATIBLE, INCOMPATIBLE', max_length=20)),
                ('change_summary', models.JSONField(default=dict, help_text='Summary of changes (counts by change type)')),
                ('change_log', models.JSONField(default=dict, help_text='Complete change log with all changes')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('dataset', models.OneToOneField(help_text='Dataset version this schema belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='schema_version', to='datasets.dataset')),
                ('parent_schema_version', models.ForeignKey(blank=True, help_text='Parent schema version in evolution chain', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='child_schema_versions', to='datasets.schemaversion')),
            ],
            options={
                'db_table': 'schema_versions',
                'ordering': ['-created_at'],
            },
        ),
        # Add indexes for SchemaVersion
        migrations.AddIndex(
            model_name='schemaversion',
            index=models.Index(fields=['dataset'], name='schema_versions_dataset_idx'),
        ),
        migrations.AddIndex(
            model_name='schemaversion',
            index=models.Index(fields=['parent_schema_version'], name='schema_versions_parent_idx'),
        ),
        migrations.AddIndex(
            model_name='schemaversion',
            index=models.Index(fields=['compatibility_level'], name='schema_versions_compat_idx'),
        ),
        # Create DatasetSnapshot table
        migrations.CreateModel(
            name='DatasetSnapshot',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('snapshot_data', models.JSONField(help_text='Complete dataset snapshot (schema, sample data, metadata)')),
                ('snapshot_type', models.CharField(default='FULL', help_text='Snapshot type: FULL, SCHEMA_ONLY, METADATA_ONLY', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('dataset', models.ForeignKey(help_text='Dataset version this snapshot belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='snapshots', to='datasets.dataset')),
            ],
            options={
                'db_table': 'dataset_snapshots',
                'ordering': ['-created_at'],
            },
        ),
        # Add indexes for DatasetSnapshot
        migrations.AddIndex(
            model_name='datasetsnapshot',
            index=models.Index(fields=['dataset', 'created_at'], name='dataset_snapshots_dataset_created_idx'),
        ),
        migrations.AddIndex(
            model_name='datasetsnapshot',
            index=models.Index(fields=['snapshot_type'], name='dataset_snapshots_type_idx'),
        ),
    ]

