# Generated manually for Phase 204 — email verification

import django.utils.timezone
from django.db import migrations, models


def mark_existing_users_verified(apps, schema_editor):
    User = apps.get_model("users", "User")
    now = django.utils.timezone.now()
    User.objects.all().update(email_verified=True, email_verified_at=now)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0013_remove_user_users_tenant_created_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email_verified",
            field=models.BooleanField(
                default=False,
                help_text="Whether the user has confirmed ownership of their email address",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="email_verified_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When email was verified",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="email_verification_token",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="SHA-256 hex hash of the email verification token (plaintext only in email link)",
                max_length=64,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="email_verification_sent_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the current verification token was issued (expiry + resend throttling)",
                null=True,
            ),
        ),
        migrations.RunPython(mark_existing_users_verified, migrations.RunPython.noop),
    ]
