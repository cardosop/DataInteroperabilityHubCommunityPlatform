"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("hub_auth", "0010_enable_rls_impersonation_sessions"),
        ("hub_auth", "0012_merge_20260513_1157"),
    ]

    operations = [
    ]
