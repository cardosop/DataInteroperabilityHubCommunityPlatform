# Generated migration for Webhook models

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
            name='Webhook',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Webhook name/description', max_length=255)),
                ('url', models.URLField(help_text='Webhook delivery URL', max_length=2048)),
                ('secret', models.CharField(help_text='Webhook secret for HMAC signature (encrypted)', max_length=255)),
                ('event_types', models.JSONField(default=list, help_text='List of event types to subscribe to')),
                ('status', models.CharField(choices=[('ACTIVE', 'Active'), ('PAUSED', 'Paused'), ('DISABLED', 'Disabled')], default='ACTIVE', help_text='Webhook status', max_length=20)),
                ('max_retries', models.IntegerField(default=5, help_text='Maximum number of delivery retries')),
                ('retry_intervals', models.JSONField(default=list, help_text='Retry intervals in seconds: [1, 5, 30, 300, 1800]')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created the webhook', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_webhooks', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(help_text='Tenant this webhook belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='webhooks', to='tenants.tenant')),
            ],
            options={
                'db_table': 'webhooks',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='WebhookDelivery',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_type', models.CharField(help_text='Event type that triggered the delivery', max_length=100)),
                ('payload', models.JSONField(help_text='Webhook payload (event data)')),
                ('signature', models.CharField(help_text='HMAC signature of the payload', max_length=64)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('SUCCESS', 'Success'), ('FAILED', 'Failed'), ('DEAD_LETTER', 'Dead Letter')], default='PENDING', help_text='Delivery status', max_length=20)),
                ('attempt_number', models.IntegerField(default=0, help_text='Current attempt number (0-indexed)')),
                ('http_status_code', models.IntegerField(blank=True, help_text='HTTP status code from delivery attempt', null=True)),
                ('response_body', models.TextField(blank=True, help_text='Response body from delivery attempt', null=True)),
                ('error_message', models.TextField(blank=True, help_text='Error message if delivery failed', null=True)),
                ('delivered_at', models.DateTimeField(blank=True, help_text='When delivery succeeded', null=True)),
                ('next_retry_at', models.DateTimeField(blank=True, help_text='When to retry delivery (if failed)', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('webhook', models.ForeignKey(help_text='Webhook subscription', on_delete=django.db.models.deletion.CASCADE, related_name='deliveries', to='webhooks.webhook')),
            ],
            options={
                'db_table': 'webhook_deliveries',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='webhook',
            index=models.Index(fields=['tenant', 'status'], name='webhooks_tenant_status_idx'),
        ),
        migrations.AddIndex(
            model_name='webhook',
            index=models.Index(fields=['tenant', 'event_types'], name='webhooks_tenant_events_idx'),
        ),
        migrations.AddIndex(
            model_name='webhookdelivery',
            index=models.Index(fields=['webhook', 'status'], name='webhook_deliveries_webhook_status_idx'),
        ),
        migrations.AddIndex(
            model_name='webhookdelivery',
            index=models.Index(fields=['webhook', 'next_retry_at'], name='webhook_deliveries_webhook_retry_idx'),
        ),
        migrations.AddIndex(
            model_name='webhookdelivery',
            index=models.Index(fields=['status', 'next_retry_at'], name='webhook_deliveries_status_retry_idx'),
        ),
    ]

