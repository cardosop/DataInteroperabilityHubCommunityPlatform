"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("mesh", "0002_compliancereport_policyapplication"),
        ("mesh", "0004_enable_rls_data_mesh_domains"),
    ]

    operations = [
    ]
