"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("warehouses", "0003_enable_rls_warehouse_connection_acls"),
        ("warehouses", "0005_merge_20260520_1606"),
    ]

    operations = [
    ]
