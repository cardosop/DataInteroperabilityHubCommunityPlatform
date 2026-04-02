"""
Migration 0012 — Phase 92.10 (schema)

Remove null=True from display_name and avatar_url, add default="".
Runs after the data migration that converted NULLs to empty strings.
"""
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0011_convert_null_charfields_to_empty"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="display_name",
            field=models.CharField(
                max_length=255,
                default="",
                blank=True,
                help_text="User display name",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="avatar_url",
            field=models.URLField(
                max_length=500,
                default="",
                blank=True,
                help_text="URL to user avatar image (e.g. gravatar, CDN)",
            ),
        ),
    ]
