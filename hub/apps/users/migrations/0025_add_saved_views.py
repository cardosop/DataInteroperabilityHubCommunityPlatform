# Generated manually — Phase 278.E.3 (User.saved_views JSONField)
# Fixes: "column users.saved_views does not exist" causing 500 on /auth/login/
# in e2e batch 3 (2026-05-13).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0024_add_unsubscribe_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="saved_views",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Per-user saved filters/views for list pages. URL-shareable via ?saved=<name>.",
            ),
        ),
    ]
