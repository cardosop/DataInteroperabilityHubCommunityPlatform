"""
Migration 0006 — Phase 11.2 + 11.5

* RefreshToken: add family_id (UUIDField) and sequence_number (IntegerField).
  Existing tokens receive a unique family_id each (one-token families) and
  sequence_number=0 so the rotation invariant holds from day one.
* LoginAttempt: new model for account-level lockout.
"""
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hub_auth", "0005_rename_api_keys_tier_id_idx_api_keys_tier_id_811cbc_idx"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── RefreshToken: add family_id ───────────────────────────────────────
        migrations.AddField(
            model_name="refreshtoken",
            name="family_id",
            field=models.UUIDField(
                default=uuid.uuid4,
                help_text="Shared UUID for all tokens in one rotation chain",
            ),
        ),
        # Backfill: each existing token gets its own unique family_id so the
        # rotation invariant (one active token per family) holds immediately.
        migrations.RunSQL(
            sql="UPDATE refresh_tokens SET family_id = gen_random_uuid() "
                "WHERE family_id = '00000000-0000-0000-0000-000000000000'::uuid;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AddIndex(
            model_name="refreshtoken",
            index=models.Index(
                fields=["family_id"], name="refresh_tokens_family_id_idx"
            ),
        ),
        # ── RefreshToken: add sequence_number ────────────────────────────────
        migrations.AddField(
            model_name="refreshtoken",
            name="sequence_number",
            field=models.IntegerField(
                default=0,
                help_text="Monotonically increasing within a family; 0 = first issue",
            ),
        ),
        # ── LoginAttempt (new model) ──────────────────────────────────────────
        migrations.CreateModel(
            name="LoginAttempt",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        db_index=True,
                        help_text="Email address used in the attempt",
                        max_length=254,
                    ),
                ),
                (
                    "ip_address",
                    models.GenericIPAddressField(
                        help_text="Client IP address"
                    ),
                ),
                (
                    "success",
                    models.BooleanField(
                        default=False,
                        help_text="True if the attempt resulted in a successful login",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "login_attempts",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["email", "created_at"],
                        name="login_attempts_email_created_idx",
                    ),
                    models.Index(
                        fields=["ip_address", "created_at"],
                        name="login_attempts_ip_created_idx",
                    ),
                ],
            },
        ),
    ]
