# Generated migration for DQ Alerting Rules model

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('dq', '0002_add_anomaly_and_trend_models'),
        ('tenants', '0001_initial'),
        ('assets', '0002_rename_assets_tenant_key_idx_assets_tenant__76965e_idx_and_more'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DQAlertingRule',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Rule name', max_length=255)),
                ('description', models.TextField(blank=True, help_text='Rule description', null=True)),
                ('metric_type', models.CharField(help_text='Type of metric (e.g., quality_score, completeness, accuracy)', max_length=100)),
                ('threshold', models.FloatField(help_text='Threshold value (e.g., quality_score < 0.9)')),
                ('comparison_operator', models.CharField(choices=[('<', 'Less than'), ('<=', 'Less than or equal'), ('>', 'Greater than'), ('>=', 'Greater than or equal'), ('==', 'Equal to'), ('!=', 'Not equal to')], default='<', help_text='Comparison operator', max_length=10)),
                ('severity', models.CharField(choices=[('CRITICAL', 'Critical'), ('HIGH', 'High'), ('MEDIUM', 'Medium'), ('LOW', 'Low')], default='MEDIUM', help_text='Alert severity: CRITICAL, HIGH, MEDIUM, LOW', max_length=20)),
                ('alert_channels', models.JSONField(default=list, help_text='List of alert channels (EMAIL, SLACK, WEBHOOK, PAGERDUTY)')),
                ('channel_config', models.JSONField(blank=True, default=dict, help_text='Channel-specific configuration (e.g., email addresses, webhook URLs)', null=True)),
                ('enabled', models.BooleanField(default=True, help_text='Whether the rule is enabled')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('asset', models.ForeignKey(blank=True, help_text='Asset this rule applies to (nullable for global rules)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='dq_alerting_rules', to='assets.asset')),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created the rule', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_dq_alerting_rules', to='users.user')),
                ('tenant', models.ForeignKey(help_text='Tenant this rule belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='dq_alerting_rules', to='tenants.tenant')),
            ],
            options={
                'db_table': 'dq_alerting_rules',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='dqalertingrule',
            index=models.Index(fields=['tenant', 'asset'], name='dq_alertin_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='dqalertingrule',
            index=models.Index(fields=['tenant', 'enabled'], name='dq_alertin_tenant__idx2'),
        ),
        migrations.AddIndex(
            model_name='dqalertingrule',
            index=models.Index(fields=['tenant', 'metric_type'], name='dq_alertin_tenant__idx3'),
        ),
        migrations.AddIndex(
            model_name='dqalertingrule',
            index=models.Index(fields=['tenant', 'severity'], name='dq_alertin_tenant__idx4'),
        ),
    ]

