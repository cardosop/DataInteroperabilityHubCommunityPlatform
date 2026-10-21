# Generated migration for datasets app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants', '0001_initial'),
        ('files', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Dataset',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('schema_json', models.JSONField(blank=True, help_text='Inferred schema as JSON (fields, types, nullable flags, etc.)', null=True)),
                ('sample_data_json', models.JSONField(blank=True, help_text='Sample data (first 100 rows) as JSON array', null=True)),
                ('row_count', models.BigIntegerField(blank=True, help_text='Total number of rows in the dataset', null=True)),
                ('format', models.CharField(help_text='File format: CSV, JSON, PARQUET', max_length=20)),
                ('version', models.IntegerField(default=1, help_text='Dataset version (per-asset version counter)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('asset', models.ForeignKey(blank=True, help_text='Asset this dataset belongs to (nullable for MVP)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='datasets', to='assets.asset')),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created the dataset', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_datasets', to=settings.AUTH_USER_MODEL)),
                ('file', models.ForeignKey(help_text='File this dataset is based on', on_delete=django.db.models.deletion.CASCADE, related_name='datasets', to='files.file')),
                ('tenant', models.ForeignKey(help_text='Tenant this dataset belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='datasets', to='tenants.tenant')),
            ],
            options={
                'db_table': 'datasets',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='dataset',
            index=models.Index(fields=['tenant', 'asset'], name='datasets_tenant_asset_idx'),
        ),
        migrations.AddIndex(
            model_name='dataset',
            index=models.Index(fields=['tenant', 'file'], name='datasets_tenant_file_idx'),
        ),
        migrations.AddIndex(
            model_name='dataset',
            index=models.Index(fields=['tenant', 'format'], name='datasets_tenant_format_idx'),
        ),
    ]

