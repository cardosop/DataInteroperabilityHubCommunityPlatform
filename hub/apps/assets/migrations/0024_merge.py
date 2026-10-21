"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0002_rename_assets_tenant_key_idx_assets_tenant__76965e_idx_and_more"),
        ("assets", "0003_add_popularity_metrics"),
        ("assets", "0004_remove_asset_assets_tenant_health_idx_and_more"),
        ("assets", "0005_asset_source_metadata_asset_source_type_and_more"),
        ("assets", "0006_add_external_resource_reference"),
        ("assets", "0021_asset_warehouse_connection"),
        ("assets", "0023_scope_version_trigger_to_user_facing_columns"),
    ]

    operations = [
    ]
