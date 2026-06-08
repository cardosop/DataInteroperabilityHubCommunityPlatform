"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("files", "0009_drop_completed_file_status"),
        ("files", "0011_enable_rls_files"),
    ]

    operations = [
    ]
