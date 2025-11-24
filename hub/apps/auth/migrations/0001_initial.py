# Generated migration for auth app

import django.core.validators
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
            name='APIKey',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('key_hash', models.CharField(help_text='SHA-256 hash of the API key (stored, not plaintext)', max_length=128, unique=True)),
                ('name', models.CharField(help_text='Human-readable name for the API key', max_length=255)),
                ('scopes', models.JSONField(default=list, help_text="List of scopes (e.g., ['assets:read', 'assets:write'])")),
                ('expires_at', models.DateTimeField(blank=True, help_text='Expiration timestamp (null for non-expiring keys)', null=True)),
                ('last_used_at', models.DateTimeField(blank=True, help_text='Last time this API key was used', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(help_text='Tenant this API key belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='api_keys', to='tenants.tenant')),
                ('user', models.ForeignKey(blank=True, help_text='User this API key belongs to (optional, for user-scoped keys)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='api_keys', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'api_keys',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='RefreshToken',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('token_hash', models.CharField(help_text='SHA-256 hash of the refresh token (stored, not plaintext)', max_length=128, unique=True)),
                ('expires_at', models.DateTimeField(help_text='Expiration timestamp')),
                ('revoked_at', models.DateTimeField(blank=True, help_text='When this token was revoked (null if active)', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(help_text='User this refresh token belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='refresh_tokens', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'refresh_tokens',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='apikey',
            index=models.Index(fields=['tenant', 'user'], name='api_keys_tenant_user_idx'),
        ),
        migrations.AddIndex(
            model_name='apikey',
            index=models.Index(fields=['key_hash'], name='api_keys_key_hash_idx'),
        ),
        migrations.AddIndex(
            model_name='refreshtoken',
            index=models.Index(fields=['user', 'revoked_at'], name='refresh_tokens_user_revoked_idx'),
        ),
        migrations.AddIndex(
            model_name='refreshtoken',
            index=models.Index(fields=['token_hash'], name='refresh_tokens_token_hash_idx'),
        ),
        migrations.AddIndex(
            model_name='refreshtoken',
            index=models.Index(fields=['expires_at'], name='refresh_tokens_expires_at_idx'),
        ),
    ]

