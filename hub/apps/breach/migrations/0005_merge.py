"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("breach", "0003_rename_template_override_constraint"),
        ("breach", "0004_rename_breach_inci_tenant__d2ee18_idx_breach_inci_tenant__cd4ae0_idx_and_more"),
    ]

    operations = [
    ]
