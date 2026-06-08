"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0001_initial"),
        ("contracts", "0002_rename_contracts_tenant_asset_idx_contracts_tenant__910299_idx_and_more"),
        ("contracts", "0002_set_default_hub_contract_version"),
        ("contracts", "0003_add_hub_contract_json_gin_index"),
        ("contracts", "0004_remove_datacontract_com_from_original_spec_type"),
        ("contracts", "0005_add_lineage_indexes"),
        ("contracts", "0006_add_additional_indexes"),
        ("contracts", "0008_merge_20251210_0237"),
        ("contracts", "0009_add_odps_to_original_spec_type"),
        ("contracts", "0010_add_odps_link_index"),
        ("contracts", "0011_add_odps_query_indexes"),
        ("contracts", "0029_alter_migrationcheckpoint_migration_name_and_more"),
        ("contracts", "0039_merge"),
    ]

    operations = [
    ]
