# Generated migration for API Analytics

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='APIUsageMetric',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('endpoint_path', models.CharField(help_text='API endpoint path', max_length=500)),
                ('method', models.CharField(help_text='HTTP method', max_length=10)),
                ('status_code', models.IntegerField(help_text='HTTP status code')),
                ('latency_ms', models.FloatField(blank=True, help_text='Request latency in milliseconds', null=True)),
                ('request_size_bytes', models.IntegerField(blank=True, help_text='Request size in bytes', null=True)),
                ('response_size_bytes', models.IntegerField(blank=True, help_text='Response size in bytes', null=True)),
                ('api_version', models.CharField(default='v1', help_text='API version used', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(help_text='Tenant this metric belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='api_usage_metrics', to='tenants.tenant')),
                ('user', models.ForeignKey(blank=True, help_text='User who made the request', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='api_usage_metrics', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'api_usage_metrics',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='apiusagemetric',
            index=models.Index(fields=['tenant', 'endpoint_path', 'created_at'], name='api_usage_metrics_tenant_endpoint_idx'),
        ),
        migrations.AddIndex(
            model_name='apiusagemetric',
            index=models.Index(fields=['tenant', 'method', 'created_at'], name='api_usage_metrics_tenant_method_idx'),
        ),
        migrations.AddIndex(
            model_name='apiusagemetric',
            index=models.Index(fields=['tenant', 'status_code', 'created_at'], name='api_usage_metrics_tenant_status_idx'),
        ),
        migrations.AddIndex(
            model_name='apiusagemetric',
            index=models.Index(fields=['created_at'], name='api_usage_metrics_created_at_idx'),
        ),
    ]

