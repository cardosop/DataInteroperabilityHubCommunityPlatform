# Generated migration for bug_prevention models

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_create_event_outbox'),
    ]

    operations = [
        migrations.CreateModel(
            name='IdempotencyKey',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('tenant_id', models.UUIDField(db_index=True, help_text='Tenant UUID')),
                ('idempotency_key', models.CharField(db_index=True, help_text='Client-provided idempotency key', max_length=256)),
                ('method', models.CharField(help_text='HTTP method (e.g., POST)', max_length=10)),
                ('path', models.CharField(help_text='Request path', max_length=512)),
                ('request_fingerprint', models.CharField(help_text='SHA-256 hash of method + path + body', max_length=64)),
                ('response_status', models.IntegerField(help_text='HTTP status code of response')),
                ('response_body', models.JSONField(help_text='Cached response body')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('expires_at', models.DateTimeField(db_index=True, help_text='Expiry time (24 hours from creation)')),
            ],
            options={
                'db_table': 'idempotency_keys',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='RequestDeduplication',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('tenant_id', models.UUIDField(db_index=True, help_text='Tenant UUID')),
                ('request_fingerprint', models.CharField(db_index=True, help_text='SHA-256 hash of request', max_length=64, unique=True)),
                ('method', models.CharField(help_text='HTTP method', max_length=10)),
                ('path', models.CharField(help_text='Request path', max_length=512)),
                ('request_body_hash', models.CharField(help_text='SHA-256 hash of request body', max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('expires_at', models.DateTimeField(db_index=True, help_text='Expiry time (5 minutes from creation)')),
            ],
            options={
                'db_table': 'request_deduplication',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='idempotencykey',
            index=models.Index(fields=['tenant_id', 'idempotency_key', 'method', 'path'], name='idempotency_tenant_key_method_path_idx'),
        ),
        migrations.AddIndex(
            model_name='idempotencykey',
            index=models.Index(fields=['expires_at'], name='idempotency_expires_at_idx'),
        ),
        migrations.AddIndex(
            model_name='requestdeduplication',
            index=models.Index(fields=['tenant_id', 'request_fingerprint'], name='request_dedup_tenant_fingerprint_idx'),
        ),
        migrations.AddIndex(
            model_name='requestdeduplication',
            index=models.Index(fields=['expires_at'], name='request_dedup_expires_at_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='idempotencykey',
            unique_together={('tenant_id', 'idempotency_key', 'method', 'path')},
        ),
    ]

