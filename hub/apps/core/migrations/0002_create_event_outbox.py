# Generated migration for EventOutbox model

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EventOutbox',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('tenant_id', models.UUIDField(blank=True, db_index=True, help_text='Tenant ID for tenant isolation', null=True)),
                ('event_type', models.CharField(db_index=True, help_text="Event type (e.g., 'asset.created')", max_length=255)),
                ('event_data', models.JSONField(help_text='Event payload (JSON)')),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('PUBLISHED', 'Published'), ('FAILED', 'Failed')], db_index=True, default='PENDING', help_text='Event status', max_length=50)),
                ('retry_count', models.IntegerField(default=0, help_text='Number of retry attempts')),
                ('max_retries', models.IntegerField(default=5, help_text='Maximum number of retries')),
                ('error_message', models.TextField(blank=True, help_text='Error message if publishing failed', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, help_text='When event was created')),
                ('published_at', models.DateTimeField(blank=True, help_text='When event was published', null=True)),
            ],
            options={
                'db_table': 'event_outbox',
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='eventoutbox',
            index=models.Index(fields=['status', 'created_at'], name='event_outbox_status_created_idx'),
        ),
        migrations.AddIndex(
            model_name='eventoutbox',
            index=models.Index(fields=['tenant_id', 'status'], name='event_outbox_tenant_status_idx'),
        ),
    ]
