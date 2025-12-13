"""
Migration: Set default HubContract version to 1.0.0

Sets all existing contracts to hub_contract_version = "1.0.0" during development.
"""
from django.db import migrations


def set_default_version(apps, schema_editor):
    """Set all contracts to version 1.0.0"""
    Contract = apps.get_model('contracts', 'Contract')
    Contract.objects.filter(hub_contract_version__isnull=True).update(
        hub_contract_version='1.0.0'
    )
    # Also update contracts with empty string or invalid versions
    Contract.objects.filter(hub_contract_version='').update(
        hub_contract_version='1.0.0'
    )


def reverse_set_default_version(apps, schema_editor):
    """Reverse migration - set version to NULL"""
    Contract = apps.get_model('contracts', 'Contract')
    Contract.objects.filter(hub_contract_version='1.0.0').update(
        hub_contract_version=None
    )


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(set_default_version, reverse_set_default_version),
    ]

