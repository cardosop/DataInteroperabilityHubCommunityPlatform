"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("transformation", "0008_add_prefect_flow_run_id"),
        ("transformation", "0009_add_dependency_statuses"),
        ("transformation", "0011_enable_rls_wrangling_operations"),
    ]

    operations = [
    ]
