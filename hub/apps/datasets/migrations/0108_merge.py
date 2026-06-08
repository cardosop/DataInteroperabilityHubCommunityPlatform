"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("datasets", "0002_rename_datasets_tenant_asset_idx_datasets_tenant__5d12ce_idx_and_more"),
        ("datasets", "0003_add_version_history_fields"),
        ("datasets", "0004_add_schema_evolution_tracking"),
        ("datasets", "0005_add_version_history_indexes"),
        ("datasets", "0006_initial"),
        ("datasets", "0106_dataset_kind_field"),
        ("datasets", "0107_rename_datasets_tenant_status_idx_datasets_tenant__f0c0c8_idx"),
    ]

    operations = [
    ]
