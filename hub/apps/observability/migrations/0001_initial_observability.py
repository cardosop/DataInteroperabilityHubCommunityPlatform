# Generated migration for data observability models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
        ('datasets', '0001_initial'),
        ('assets', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Create DataObservabilityMetric table
        migrations.CreateModel(
            name='DataObservabilityMetric',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('last_update_time', models.DateTimeField(blank=True, help_text='Last time the data was updated', null=True)),
                ('freshness_age_seconds', models.BigIntegerField(blank=True, help_text='Age of data in seconds (time since last update)', null=True)),
                ('freshness_sla', models.CharField(blank=True, choices=[('REAL_TIME', 'Real-time (< 1 minute)'), ('NEAR_REAL_TIME', 'Near Real-time (< 5 minutes)'), ('HOURLY', 'Hourly (< 1 hour)'), ('DAILY', 'Daily (< 24 hours)'), ('WEEKLY', 'Weekly (< 7 days)'), ('MONTHLY', 'Monthly (< 30 days)'), ('ON_DEMAND', 'On-demand (no SLA)')], help_text='Freshness SLA requirement', max_length=50, null=True)),
                ('freshness_sla_seconds', models.BigIntegerField(blank=True, help_text='Freshness SLA in seconds', null=True)),
                ('is_stale', models.BooleanField(db_index=True, default=False, help_text='Whether data is stale (exceeds SLA)')),
                ('row_count', models.BigIntegerField(blank=True, help_text='Number of rows in the dataset', null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ('size_bytes', models.BigIntegerField(blank=True, help_text='Size of dataset in bytes', null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ('schema_hash', models.CharField(blank=True, db_index=True, help_text='SHA-256 hash of schema for drift detection', max_length=64, null=True)),
                ('schema_json', models.JSONField(blank=True, help_text='Schema JSON snapshot for comparison', null=True)),
                ('recorded_at', models.DateTimeField(auto_now_add=True, db_index=True, help_text='When this metric was recorded')),
                ('asset', models.ForeignKey(blank=True, help_text='Asset this metric is for', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='observability_metrics', to='assets.asset')),
                ('dataset', models.ForeignKey(blank=True, help_text='Dataset this metric is for', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='observability_metrics', to='datasets.dataset')),
                ('tenant', models.ForeignKey(help_text='Tenant this metric belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='observability_metrics', to='tenants.tenant')),
            ],
            options={
                'db_table': 'data_observability_metrics',
                'ordering': ['-recorded_at'],
            },
        ),
        # Create VolumeTrend table
        migrations.CreateModel(
            name='VolumeTrend',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('period_start', models.DateTimeField(db_index=True, help_text='Start of aggregation period')),
                ('period_end', models.DateTimeField(db_index=True, help_text='End of aggregation period')),
                ('period_type', models.CharField(choices=[('HOURLY', 'Hourly'), ('DAILY', 'Daily')], help_text='Type of aggregation period', max_length=20)),
                ('avg_row_count', models.BigIntegerField(blank=True, help_text='Average row count during period', null=True)),
                ('min_row_count', models.BigIntegerField(blank=True, help_text='Minimum row count during period', null=True)),
                ('max_row_count', models.BigIntegerField(blank=True, help_text='Maximum row count during period', null=True)),
                ('avg_size_bytes', models.BigIntegerField(blank=True, help_text='Average size in bytes during period', null=True)),
                ('min_size_bytes', models.BigIntegerField(blank=True, help_text='Minimum size in bytes during period', null=True)),
                ('max_size_bytes', models.BigIntegerField(blank=True, help_text='Maximum size in bytes during period', null=True)),
                ('sample_count', models.IntegerField(default=0, help_text='Number of samples in this period')),
                ('is_anomaly', models.BooleanField(db_index=True, default=False, help_text='Whether this period contains anomalies')),
                ('anomaly_type', models.CharField(blank=True, help_text='Type of anomaly detected (SPIKE, DROP, UNUSUAL_PATTERN)', max_length=50, null=True)),
                ('anomaly_score', models.FloatField(blank=True, help_text='Anomaly score (0.0 to 1.0)', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('asset', models.ForeignKey(blank=True, help_text='Asset this trend is for', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='volume_trends', to='assets.asset')),
                ('dataset', models.ForeignKey(blank=True, help_text='Dataset this trend is for', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='volume_trends', to='datasets.dataset')),
                ('tenant', models.ForeignKey(help_text='Tenant this trend belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='volume_trends', to='tenants.tenant')),
            ],
            options={
                'db_table': 'volume_trends',
                'ordering': ['-period_start'],
            },
        ),
        # Create SchemaDrift table
        migrations.CreateModel(
            name='SchemaDrift',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('previous_schema_hash', models.CharField(blank=True, help_text='Hash of previous schema', max_length=64, null=True)),
                ('current_schema_hash', models.CharField(db_index=True, help_text='Hash of current schema', max_length=64)),
                ('previous_schema_json', models.JSONField(blank=True, help_text='Previous schema JSON', null=True)),
                ('current_schema_json', models.JSONField(blank=True, help_text='Current schema JSON', null=True)),
                ('new_fields', models.JSONField(blank=True, default=list, help_text='List of new fields added', null=True)),
                ('removed_fields', models.JSONField(blank=True, default=list, help_text='List of fields removed', null=True)),
                ('type_changes', models.JSONField(blank=True, default=list, help_text='List of type changes (field_name, old_type, new_type)', null=True)),
                ('nullable_changes', models.JSONField(blank=True, default=list, help_text='List of nullable changes (field_name, old_nullable, new_nullable)', null=True)),
                ('drift_severity', models.CharField(choices=[('BREAKING', 'Breaking Change'), ('NON_BREAKING', 'Non-Breaking Change'), ('MINOR', 'Minor Change')], default='MINOR', help_text='Severity of schema drift', max_length=20)),
                ('tolerance_config', models.JSONField(blank=True, default=dict, help_text='Tolerance configuration used for drift detection', null=True)),
                ('is_within_tolerance', models.BooleanField(db_index=True, default=True, help_text='Whether drift is within configured tolerance')),
                ('detected_at', models.DateTimeField(auto_now_add=True, db_index=True, help_text='When this drift was detected')),
                ('asset', models.ForeignKey(blank=True, help_text='Asset this drift is for', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='schema_drifts', to='assets.asset')),
                ('dataset', models.ForeignKey(blank=True, help_text='Dataset this drift is for', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='schema_drifts', to='datasets.dataset')),
                ('tenant', models.ForeignKey(help_text='Tenant this drift record belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='schema_drifts', to='tenants.tenant')),
            ],
            options={
                'db_table': 'schema_drifts',
                'ordering': ['-detected_at'],
            },
        ),
        # Add indexes for DataObservabilityMetric
        migrations.AddIndex(
            model_name='dataobservabilitymetric',
            index=models.Index(fields=['tenant', 'dataset', 'recorded_at'], name='data_observ_tenant__dataset_recorded_idx'),
        ),
        migrations.AddIndex(
            model_name='dataobservabilitymetric',
            index=models.Index(fields=['tenant', 'asset', 'recorded_at'], name='data_observ_tenant__asset_recorded_idx'),
        ),
        migrations.AddIndex(
            model_name='dataobservabilitymetric',
            index=models.Index(fields=['tenant', 'is_stale', 'recorded_at'], name='data_observ_tenant__is_stale_recorded_idx'),
        ),
        migrations.AddIndex(
            model_name='dataobservabilitymetric',
            index=models.Index(fields=['recorded_at'], name='data_observ_recorded_at_idx'),
        ),
        # Add indexes for VolumeTrend
        migrations.AddIndex(
            model_name='volumetrend',
            index=models.Index(fields=['tenant', 'dataset', 'period_type', 'period_start'], name='volume_tren_tenant__dataset_period_type_idx'),
        ),
        migrations.AddIndex(
            model_name='volumetrend',
            index=models.Index(fields=['tenant', 'asset', 'period_type', 'period_start'], name='volume_tren_tenant__asset_period_type_idx'),
        ),
        migrations.AddIndex(
            model_name='volumetrend',
            index=models.Index(fields=['tenant', 'is_anomaly', 'period_start'], name='volume_tren_tenant__is_anomaly_period_idx'),
        ),
        # Add unique constraints for VolumeTrend
        migrations.AddConstraint(
            model_name='volumetrend',
            constraint=models.UniqueConstraint(condition=models.Q(dataset__isnull=False), fields=['tenant', 'dataset', 'period_type', 'period_start'], name='unique_volume_trend_dataset'),
        ),
        migrations.AddConstraint(
            model_name='volumetrend',
            constraint=models.UniqueConstraint(condition=models.Q(asset__isnull=False), fields=['tenant', 'asset', 'period_type', 'period_start'], name='unique_volume_trend_asset'),
        ),
        # Add indexes for SchemaDrift
        migrations.AddIndex(
            model_name='schemadrift',
            index=models.Index(fields=['tenant', 'dataset', 'detected_at'], name='schema_drif_tenant__dataset_detected_idx'),
        ),
        migrations.AddIndex(
            model_name='schemadrift',
            index=models.Index(fields=['tenant', 'asset', 'detected_at'], name='schema_drif_tenant__asset_detected_idx'),
        ),
        migrations.AddIndex(
            model_name='schemadrift',
            index=models.Index(fields=['tenant', 'drift_severity', 'detected_at'], name='schema_drif_tenant__drift_severity_idx'),
        ),
        migrations.AddIndex(
            model_name='schemadrift',
            index=models.Index(fields=['tenant', 'is_within_tolerance', 'detected_at'], name='schema_drif_tenant__is_within_tolerance_idx'),
        ),
    ]

