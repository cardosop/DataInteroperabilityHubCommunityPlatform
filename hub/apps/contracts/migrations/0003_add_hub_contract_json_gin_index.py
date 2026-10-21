# Generated manually for Django 6 JSONField optimization
# Date: 2025-01-15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0002_rename_contracts_tenant_asset_idx_contracts_tenant__910299_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contract',
            name='hub_contract_json',
            field=models.JSONField(
                blank=True,
                db_index=True,  # GIN index for JSONB queries (Django 6 optimization)
                help_text='Normalized HubContract JSON',
                null=True
            ),
        ),
    ]

