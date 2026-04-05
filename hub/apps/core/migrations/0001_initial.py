# Generated manually for event bus models

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]
    
    operations = [
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_id', models.UUIDField(db_index=True, help_text='Event UUID', unique=True)),
                ('event_type', models.CharField(db_index=True, help_text="Event type (e.g., 'contract.created')", max_length=255)),
                ('event_version', models.CharField(help_text='Schema version', max_length=20)),
                ('timestamp', models.DateTimeField(db_index=True, help_text='Event timestamp')),
                ('source_service', models.CharField(help_text='Service that generated the event', max_length=100)),
                ('tenant_id', models.UUIDField(blank=True, db_index=True, help_text='Tenant UUID', null=True)),
                ('user_id', models.UUIDField(blank=True, help_text='User UUID', null=True)),
                ('request_id', models.CharField(blank=True, help_text='Request ID', max_length=255, null=True)),
                ('data', models.JSONField(help_text='Event data payload')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional metadata')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'db_table': 'events',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='DeadLetterQueue',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event', models.JSONField(help_text='Failed event payload')),
                ('event_type', models.CharField(db_index=True, help_text='Event type', max_length=255)),
                ('subscriber', models.CharField(db_index=True, help_text='Subscriber that failed', max_length=255)),
                ('error_message', models.TextField(help_text='Error message')),
                ('error_details', models.JSONField(blank=True, default=dict, help_text='Error details (stack trace, etc.)')),
                ('retry_count', models.IntegerField(default=0, help_text='Number of retries attempted')),
                ('last_attempt_at', models.DateTimeField(auto_now=True, help_text='Last retry attempt timestamp')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('resolved_at', models.DateTimeField(blank=True, help_text='When issue was resolved', null=True)),
                ('resolved_by', models.UUIDField(blank=True, help_text='User who resolved', null=True)),
            ],
            options={
                'db_table': 'dead_letter_queue',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='EventSubscription',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('subscriber_name', models.CharField(db_index=True, help_text='Subscriber identifier', max_length=255)),
                ('event_type_pattern', models.CharField(db_index=True, help_text='Event type pattern (supports wildcards)', max_length=255)),
                ('is_active', models.BooleanField(db_index=True, default=True, help_text='Whether subscription is active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'event_subscriptions',
            },
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['event_type', '-timestamp'], name='events_event_type_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['tenant_id', '-timestamp'], name='events_tenant_id_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['source_service', '-timestamp'], name='events_source_service_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['created_at'], name='events_created_at_idx'),
        ),
        migrations.AddIndex(
            model_name='deadletterqueue',
            index=models.Index(fields=['event_type', '-created_at'], name='dead_letter_queue_event_type_created_at_idx'),
        ),
        migrations.AddIndex(
            model_name='deadletterqueue',
            index=models.Index(fields=['subscriber', '-created_at'], name='dead_letter_queue_subscriber_created_at_idx'),
        ),
        migrations.AddIndex(
            model_name='deadletterqueue',
            index=models.Index(fields=['resolved_at'], name='dead_letter_queue_resolved_at_idx'),
        ),
        migrations.AddIndex(
            model_name='eventsubscription',
            index=models.Index(fields=['subscriber_name', 'is_active'], name='event_subscriptions_subscriber_name_is_active_idx'),
        ),
        migrations.AddIndex(
            model_name='eventsubscription',
            index=models.Index(fields=['event_type_pattern', 'is_active'], name='event_subscriptions_event_type_pattern_is_active_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='eventsubscription',
            unique_together={('subscriber_name', 'event_type_pattern')},
        ),
    ]
