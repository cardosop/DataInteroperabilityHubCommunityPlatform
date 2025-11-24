# Generated migration for contracts app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants', '0001_initial'),
        ('assets', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Contract',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('version', models.IntegerField(default=1, help_text='Per-asset contract version counter')),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('ACTIVE', 'Active'), ('RETIRED', 'Retired')], default='DRAFT', help_text='Contract lifecycle status: DRAFT, ACTIVE, RETIRED', max_length=20)),
                ('original_spec_type', models.CharField(choices=[('ODCS', 'ODCS'), ('DATACONTRACT_COM', 'DataContract.com')], help_text='Original spec type: ODCS or DATACONTRACT_COM', max_length=50)),
                ('original_spec_version', models.CharField(help_text='Original spec version (e.g., 3.0.2, 2.2.2)', max_length=20)),
                ('original_format', models.CharField(choices=[('JSON', 'JSON'), ('YAML', 'YAML')], help_text='Original format: JSON or YAML', max_length=10)),
                ('original_raw', models.TextField(help_text='Original contract file content (verbatim)')),
                ('hub_contract_version', models.CharField(blank=True, help_text='HubContract version (e.g., 1.0.0)', max_length=20, null=True)),
                ('hub_contract_json', models.JSONField(blank=True, help_text='Normalized HubContract JSON', null=True)),
                ('normalization_status', models.CharField(blank=True, choices=[('NOT_NORMALIZED', 'Not Normalized'), ('NORMALIZED_OK', 'Normalized OK'), ('NORMALIZED_WITH_WARNINGS', 'Normalized With Warnings'), ('NORMALIZATION_FAILED', 'Normalization Failed')], default='NOT_NORMALIZED', help_text='Normalization status', max_length=30, null=True)),
                ('normalization_errors', models.JSONField(blank=True, default=list, help_text='Normalization errors (JSON array)', null=True)),
                ('normalization_warnings', models.JSONField(blank=True, default=list, help_text='Normalization warnings (JSON array)', null=True)),
                ('validation_status', models.CharField(blank=True, choices=[('VALID', 'Valid'), ('INVALID', 'Invalid'), ('WARNING_ONLY', 'Warning Only'), ('ERROR', 'Error')], help_text='CLI validation status: VALID, INVALID, WARNING_ONLY, ERROR', max_length=20, null=True)),
                ('validation_errors', models.JSONField(blank=True, default=list, help_text='Validation errors (JSON array)', null=True)),
                ('validation_warnings', models.JSONField(blank=True, default=list, help_text='Validation warnings (JSON array)', null=True)),
                ('cli_version', models.CharField(blank=True, help_text='DataContract CLI version used', max_length=20, null=True)),
                ('last_validated_at', models.DateTimeField(blank=True, help_text='Last validation timestamp', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('asset', models.ForeignKey(blank=True, help_text='Asset this contract belongs to (nullable for contract-only assets)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='contracts', to='assets.asset')),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created the contract', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_contracts', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(help_text='Tenant this contract belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='contracts', to='tenants.tenant')),
            ],
            options={
                'db_table': 'contracts',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='contract',
            index=models.Index(fields=['tenant', 'asset'], name='contracts_tenant_asset_idx'),
        ),
        migrations.AddIndex(
            model_name='contract',
            index=models.Index(fields=['tenant', 'status'], name='contracts_tenant_status_idx'),
        ),
        migrations.AddIndex(
            model_name='contract',
            index=models.Index(fields=['tenant', 'validation_status'], name='contracts_tenant_validation_idx'),
        ),
    ]

