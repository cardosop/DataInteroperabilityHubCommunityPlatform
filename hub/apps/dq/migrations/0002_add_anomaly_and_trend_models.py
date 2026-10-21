# Generated migration for DQ Anomaly and Trend models

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('dq', '0001_initial'),
        ('tenants', '0001_initial'),
        ('assets', '0002_rename_assets_tenant_key_idx_assets_tenant__76965e_idx_and_more'),
        ('datasets', '0003_add_version_history_fields'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DQAnomaly',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('metric_type', models.CharField(help_text='Type of metric (e.g., quality_score, completeness, accuracy)', max_length=100)),
                ('expected_value', models.FloatField(blank=True, help_text='Expected value for this metric', null=True)),
                ('actual_value', models.FloatField(help_text='Actual value that triggered the anomaly')),
                ('deviation', models.FloatField(help_text='Deviation from expected value')),
                ('severity', models.CharField(choices=[('CRITICAL', 'Critical'), ('HIGH', 'High'), ('MEDIUM', 'Medium'), ('LOW', 'Low')], default='MEDIUM', help_text='Anomaly severity: CRITICAL, HIGH, MEDIUM, LOW', max_length=20)),
                ('anomaly_type', models.CharField(help_text='Type of anomaly (e.g., z_score_outlier, iqr_outlier, sudden_drop)', max_length=50)),
                ('description', models.TextField(blank=True, help_text='Description of the anomaly', null=True)),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional metadata about the anomaly', null=True)),
                ('detected_at', models.DateTimeField(auto_now_add=True, help_text='When the anomaly was detected')),
                ('acknowledged', models.BooleanField(default=False, help_text='Whether the anomaly has been acknowledged')),
                ('acknowledged_at', models.DateTimeField(blank=True, help_text='When the anomaly was acknowledged', null=True)),
                ('asset', models.ForeignKey(blank=True, help_text='Asset this anomaly is for (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='dq_anomalies', to='assets.asset')),
                ('dataset', models.ForeignKey(blank=True, help_text='Dataset this anomaly is for (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='dq_anomalies', to='datasets.dataset')),
                ('dq_run', models.ForeignKey(blank=True, help_text='DQ run that detected this anomaly (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='anomalies', to='dq.dqrun')),
                ('acknowledged_by', models.ForeignKey(blank=True, help_text='User who acknowledged the anomaly', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='acknowledged_dq_anomalies', to='users.user')),
                ('tenant', models.ForeignKey(help_text='Tenant this anomaly belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='dq_anomalies', to='tenants.tenant')),
            ],
            options={
                'db_table': 'dq_anomalies',
                'ordering': ['-detected_at'],
            },
        ),
        migrations.AddIndex(
            model_name='dqanomaly',
            index=models.Index(fields=['tenant', 'asset'], name='dq_anomalie_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='dqanomaly',
            index=models.Index(fields=['tenant', 'dataset'], name='dq_anomalie_tenant__idx2'),
        ),
        migrations.AddIndex(
            model_name='dqanomaly',
            index=models.Index(fields=['tenant', 'severity'], name='dq_anomalie_tenant__idx3'),
        ),
        migrations.AddIndex(
            model_name='dqanomaly',
            index=models.Index(fields=['tenant', 'metric_type'], name='dq_anomalie_tenant__idx4'),
        ),
        migrations.AddIndex(
            model_name='dqanomaly',
            index=models.Index(fields=['tenant', 'acknowledged'], name='dq_anomalie_tenant__idx5'),
        ),
        migrations.AddIndex(
            model_name='dqanomaly',
            index=models.Index(fields=['detected_at'], name='dq_anomalie_detecte_idx'),
        ),
        migrations.CreateModel(
            name='DQTrend',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('metric_type', models.CharField(help_text='Type of metric (e.g., quality_score, completeness, accuracy)', max_length=100)),
                ('period_start', models.DateTimeField(help_text='Start of the trend period')),
                ('period_end', models.DateTimeField(help_text='End of the trend period')),
                ('period_type', models.CharField(help_text='Period type: HOURLY, DAILY, WEEKLY, MONTHLY', max_length=20)),
                ('current_value', models.FloatField(help_text='Current value for this metric')),
                ('previous_value', models.FloatField(blank=True, help_text='Previous value for comparison', null=True)),
                ('change_amount', models.FloatField(blank=True, help_text='Change amount (current - previous)', null=True)),
                ('change_percent', models.FloatField(blank=True, help_text='Percentage change', null=True)),
                ('direction', models.CharField(choices=[('IMPROVING', 'Improving'), ('DEGRADING', 'Degrading'), ('STABLE', 'Stable')], help_text='Trend direction: IMPROVING, DEGRADING, STABLE', max_length=20)),
                ('trend_strength', models.FloatField(blank=True, help_text='Trend strength (0-1, higher = stronger trend)', null=True)),
                ('forecast_value', models.FloatField(blank=True, help_text='Forecasted value for next period', null=True)),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional metadata about the trend', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('asset', models.ForeignKey(blank=True, help_text='Asset this trend is for (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='dq_trends', to='assets.asset')),
                ('dataset', models.ForeignKey(blank=True, help_text='Dataset this trend is for (nullable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='dq_trends', to='datasets.dataset')),
                ('tenant', models.ForeignKey(help_text='Tenant this trend belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='dq_trends', to='tenants.tenant')),
            ],
            options={
                'db_table': 'dq_trends',
                'ordering': ['-period_start'],
            },
        ),
        migrations.AddIndex(
            model_name='dqtrend',
            index=models.Index(fields=['tenant', 'asset'], name='dq_trends_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='dqtrend',
            index=models.Index(fields=['tenant', 'dataset'], name='dq_trends_tenant__idx2'),
        ),
        migrations.AddIndex(
            model_name='dqtrend',
            index=models.Index(fields=['tenant', 'metric_type'], name='dq_trends_tenant__idx3'),
        ),
        migrations.AddIndex(
            model_name='dqtrend',
            index=models.Index(fields=['tenant', 'period_type'], name='dq_trends_tenant__idx4'),
        ),
        migrations.AddIndex(
            model_name='dqtrend',
            index=models.Index(fields=['period_start', 'period_end'], name='dq_trends_period__idx'),
        ),
        migrations.AddIndex(
            model_name='dqtrend',
            index=models.Index(fields=['direction'], name='dq_trends_directi_idx'),
        ),
    ]

