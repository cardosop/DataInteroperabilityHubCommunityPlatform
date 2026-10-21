"""
Migration 0011 — Phase 92.10 (data)

Convert NULL display_name and avatar_url to empty strings
so the schema migration can safely remove null=True.
"""
from django.db import migrations


def convert_null_to_empty(apps, schema_editor):
    User = apps.get_model("users", "User")
    User.objects.filter(
        display_name__isnull=True
    ).update(display_name="")
    User.objects.filter(
        avatar_url__isnull=True
    ).update(avatar_url="")


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0010_add_user_performance_index"),
    ]

    operations = [
        migrations.RunPython(
            convert_null_to_empty,
            migrations.RunPython.noop,
        ),
    ]
