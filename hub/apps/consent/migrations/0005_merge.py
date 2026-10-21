"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("consent", "0003_add_purpose_version_and_grant_version"),
        ("consent", "0004_rename_consent_purpos_tenant__bd29e8_idx_consent_pur_tenant__70e7d6_idx_and_more"),
    ]

    operations = [
    ]
