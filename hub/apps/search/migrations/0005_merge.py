"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("search", "0001_initial"),
        ("search", "0002_add_search_query_indexes"),
        ("search", "0003_rename_search_anal_tenant__created_at_idx_search_anal_tenant__f24a36_idx_and_more"),
        ("search", "0004_enable_rls_search_index"),
    ]

    operations = [
    ]
