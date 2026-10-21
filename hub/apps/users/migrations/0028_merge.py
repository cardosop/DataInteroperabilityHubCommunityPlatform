"""Merge conflicting migration leaves (0023 merge already resolved 0020+0022 divergence)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0027_alter_user_saved_views"),
    ]

    operations = [
    ]
