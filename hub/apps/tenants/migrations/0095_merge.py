"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0057_enable_rls_feature_flag_flip_approval"),
        ("tenants", "0060_enable_rls_impersonation_session"),
        ("tenants", "0094_alter_tenantplan_tier"),
    ]

    operations = [
    ]
