"""
Migration 0007 — Phase 11.3

Convert invitation_token and password_reset_token from UUIDField to
CharField(max_length=64) so that the columns store SHA-256 hex digests
(64 chars) instead of raw UUIDs.

Both fields are nullable; NULL stays NULL.  Existing non-null values are
handled by the *next* data migration (0008) which replaces each UUID
string with sha256(uuid_string).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_populate_user_tenant_memberships"),
    ]

    operations = [
        # ── invitation_token ──────────────────────────────────────────────
        migrations.AlterField(
            model_name="user",
            name="invitation_token",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="SHA-256 hex hash of the invitation UUID token",
                max_length=64,
                null=True,
            ),
        ),
        # ── password_reset_token ──────────────────────────────────────────
        migrations.AlterField(
            model_name="user",
            name="password_reset_token",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="SHA-256 hex hash of the password-reset UUID token",
                max_length=64,
                null=True,
            ),
        ),
    ]
