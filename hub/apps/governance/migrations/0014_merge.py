"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("governance", "0001_initial"),
        ("governance", "0002_add_compliance_reports_and_abac"),
        ("governance", "0004_rename_access_certifications_tenant_user_idx_access_cert_tenant__6415d5_idx_and_more"),
        ("governance", "0011_approval_delegation"),
        ("governance", "0013_enable_rls_governance"),
    ]

    operations = [
    ]
