# Generated migration for files app

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
            name='File',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Original filename', max_length=255)),
                ('content_type', models.CharField(help_text='MIME type (e.g., text/csv, application/json)', max_length=100)),
                ('size', models.BigIntegerField(help_text='File size in bytes')),
                ('content_sha256', models.CharField(blank=True, db_index=True, help_text='SHA-256 hash of file content (for deduplication and integrity)', max_length=64, null=True)),
                ('storage_path', models.CharField(help_text='Path in S3-compatible storage (bucket/key)', max_length=500)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('UPLOADING', 'Uploading'), ('ACTIVE', 'Active'), ('FAILED', 'Failed'), ('DELETED', 'Deleted')], default='PENDING', help_text='File status: PENDING, UPLOADING, ACTIVE, FAILED, DELETED', max_length=20)),
                ('metadata_json', models.JSONField(default=dict, help_text='Additional metadata (upload method, chunk info, etc.)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, help_text='User who uploaded the file', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='uploaded_files', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(help_text='Tenant this file belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='files', to='tenants.tenant')),
            ],
            options={
                'db_table': 'files',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='file',
            index=models.Index(fields=['tenant', 'status'], name='files_tenant_status_idx'),
        ),
        migrations.AddIndex(
            model_name='file',
            index=models.Index(fields=['tenant', 'created_at'], name='files_tenant_created_idx'),
        ),
        migrations.AddIndex(
            model_name='file',
            index=models.Index(fields=['content_sha256'], name='files_content_sha256_idx'),
        ),
        migrations.AddIndex(
            model_name='file',
            index=models.Index(fields=['status'], name='files_status_idx'),
        ),
    ]

