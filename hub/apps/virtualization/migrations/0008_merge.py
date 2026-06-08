"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("virtualization", "0001_initial"),
        ("virtualization", "0002_alter_virtualdataset_schema_and_more"),
        ("virtualization", "0003_add_query_execution"),
        ("virtualization", "0004_add_job_to_query_execution"),
        ("virtualization", "0007_enable_rls_virtual_datasets"),
    ]

    operations = [
    ]
