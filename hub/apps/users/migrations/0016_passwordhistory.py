# Phase 225.1 — password history for "no-reuse of last N" policy.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0015_alter_user_email_verification_token"),
    ]

    operations = [
        migrations.CreateModel(
            name="PasswordHistory",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "password_hash",
                    models.CharField(
                        help_text=(
                            "Django hasher output "
                            "(algorithm$iterations$salt$hash) "
                            "for a prior password"
                        ),
                        max_length=255,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                (
                    "user",
                    models.ForeignKey(
                        help_text="User whose password was hashed here",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="password_history",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "password_history",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="passwordhistory",
            index=models.Index(
                fields=["user", "-created_at"],
                name="password_history_user_ts_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="passwordhistory",
            constraint=models.UniqueConstraint(
                fields=("user", "password_hash"),
                name="unique_user_password_hash",
            ),
        ),
    ]
