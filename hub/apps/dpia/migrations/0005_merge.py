"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("dpia", "0003_dpia_derived_from_recursive"),
        ("dpia", "0004_rename_dpia_tenant_i_9f80b2_idx_dpia_tenant__5fcbda_idx_and_more"),
    ]

    operations = [
    ]
