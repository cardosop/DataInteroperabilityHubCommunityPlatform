"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("processor_agreements", "0003_enable_rls_processor_agreements"),
        ("processor_agreements", "0004_rename_pa_ast_proc_tenant__2c8d_idx_pa_asset_pr_tenant__16b98f_idx_and_more"),
    ]

    operations = [
    ]
