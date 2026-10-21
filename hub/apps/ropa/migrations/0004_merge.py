"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ropa", "0002_enable_rls_ropa_generations"),
        ("ropa", "0003_rename_ropa_gener_tenant__6e4e6d_idx_ropa_genera_tenant__ae8056_idx_and_more"),
    ]

    operations = [
    ]
