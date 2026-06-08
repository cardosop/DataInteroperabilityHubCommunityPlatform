# Generated manually — Phase 278.R.6 (User.has_seen_tour BooleanField)
# Adds first-login product tour completion flag to User model.
# Pattern: mirrors 0025_add_saved_views.py.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0025_add_saved_views"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="has_seen_tour",
            field=models.BooleanField(
                default=False,
                help_text="Whether the user has completed the first-login product tour.",
            ),
        ),
    ]
