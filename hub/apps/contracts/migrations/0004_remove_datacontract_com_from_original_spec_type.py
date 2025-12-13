# Generated manually for DCS removal (Phase 0.2)
# Date: 2025-01-15
# BREAKING CHANGE: Removes DATACONTRACT_COM from OriginalSpecType enum

from django.db import migrations, models
from django.db.models import Q


def migrate_datacontract_com_contracts(apps, schema_editor):
    """
    Data migration: Convert existing DATACONTRACT_COM contracts to ODCS.
    
    This migration:
    1. Identifies all contracts with original_spec_type = 'DATACONTRACT_COM'
    2. Updates them to 'ODCS' with a default version of '3.0.2'
    3. Adds a warning to normalization_warnings indicating the migration
    
    Note: This is a best-effort conversion. Users should review migrated contracts
    and may need to manually update them to proper ODCS format.
    """
    try:
        Contract = apps.get_model('contracts', 'Contract')
        
        # Find all contracts with DATACONTRACT_COM
        dcs_contracts = Contract.objects.filter(original_spec_type='DATACONTRACT_COM')
        count = dcs_contracts.count()
    except Exception as e:
        # If query fails (e.g., table doesn't exist in test database), skip migration
        print(f"Could not query contracts table: {e}. Migration skipped.")
        return
    
    if count > 0:
        print(f"\n[WARNING] Found {count} contract(s) with original_spec_type='DATACONTRACT_COM'")
        print(f"These will be converted to ODCS with version '3.0.2'")
        print(f"Please review these contracts after migration and update them to proper ODCS format if needed.\n")
        
        # Update each contract
        for contract in dcs_contracts:
            # Update spec type and version
            contract.original_spec_type = 'ODCS'
            contract.original_spec_version = '3.0.2'
            
            # Add migration warning to normalization_warnings
            if contract.normalization_warnings is None:
                contract.normalization_warnings = []
            
            warning_msg = (
                "This contract was migrated from Data Contract Specification (DCS) to "
                "Open Data Contract Standard (ODCS). Please review and update to proper ODCS format."
            )
            
            if warning_msg not in contract.normalization_warnings:
                contract.normalization_warnings.append(warning_msg)
            
            contract.save(update_fields=['original_spec_type', 'original_spec_version', 'normalization_warnings'])
        
        print(f"Successfully migrated {count} contract(s) from DATACONTRACT_COM to ODCS")
    else:
        print("No contracts with original_spec_type='DATACONTRACT_COM' found. Migration skipped.")


def reverse_migration(apps, schema_editor):
    """
    Reverse migration: Cannot fully reverse as we don't know which contracts were originally DCS.
    
    This is a one-way migration. If rollback is needed, contracts would need to be manually
    identified and updated.
    """
    # Note: We cannot reliably reverse this migration as we don't track which contracts
    # were originally DATACONTRACT_COM vs ODCS. Manual intervention would be required.
    print("\n[WARNING] Reverse migration not supported. Manual intervention required if rollback is needed.\n")
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0003_add_hub_contract_json_gin_index'),
    ]

    operations = [
        # Step 1: Run data migration to convert existing DATACONTRACT_COM contracts
        migrations.RunPython(
            migrate_datacontract_com_contracts,
            reverse_migration,
        ),
        # Step 2: Update the field to remove DATACONTRACT_COM from choices
        migrations.AlterField(
            model_name='contract',
            name='original_spec_type',
            field=models.CharField(
                choices=[('ODCS', 'ODCS')],
                help_text='Original spec type: ODCS (Open Data Contract Standard)',
                max_length=50
            ),
        ),
    ]

