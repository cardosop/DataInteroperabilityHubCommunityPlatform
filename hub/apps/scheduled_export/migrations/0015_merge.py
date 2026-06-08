"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("scheduled_export", "0009_enable_rls_export_run_costs"),
        ("scheduled_export", "0012_alter_scheduledexport_credential_ref_and_more"),
        ("scheduled_export", "0013_add_dependency_statuses"),
        ("scheduled_export", "0014_add_metadata_field"),
    ]

    operations = [
    ]
