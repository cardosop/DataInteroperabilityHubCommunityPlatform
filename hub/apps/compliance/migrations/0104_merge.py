"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("compliance", "0102_add_scan_mode_warehouse_config"),
        ("compliance", "0103_add_error_code_and_message_to_compliancerun"),
    ]

    operations = [
    ]
