# Phase 204 review: widen token column to match spec (255) and future token formats

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0014_user_email_verification"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="email_verification_token",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Hash of the email verification token (SHA-256 hex = 64 chars; 255 for spec/future formats)",
                max_length=255,
                null=True,
            ),
        ),
    ]
