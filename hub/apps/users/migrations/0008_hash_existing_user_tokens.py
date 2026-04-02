"""
Migration 0008 — Phase 11.3 (data)

For every user row that still has a non-null invitation_token or
password_reset_token stored as a plain UUID string (32 hex chars or
36-char hyphenated UUID format) this migration replaces the value with
sha256(str(value)) so the column consistently holds a 64-char hex digest.

Rows whose tokens have already been hashed (len == 64, all hex) are left
untouched — idempotent.

NULL values are left NULL.
"""
import hashlib

from django.db import migrations


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _looks_like_hash(value: str) -> bool:
    """True if the string is already a 64-char lowercase hex digest."""
    return len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def hash_existing_tokens(apps, schema_editor):
    User = apps.get_model("users", "User")
    to_update = []
    for user in User.objects.filter(
        invitation_token__isnull=False
    ).only("id", "invitation_token"):
        raw = str(user.invitation_token)
        if not _looks_like_hash(raw):
            user.invitation_token = _sha256(raw)
            to_update.append(user)
    if to_update:
        User.objects.bulk_update(to_update, ["invitation_token"])

    to_update = []
    for user in User.objects.filter(
        password_reset_token__isnull=False
    ).only("id", "password_reset_token"):
        raw = str(user.password_reset_token)
        if not _looks_like_hash(raw):
            user.password_reset_token = _sha256(raw)
            to_update.append(user)
    if to_update:
        User.objects.bulk_update(to_update, ["password_reset_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0007_user_token_fields_hashed"),
    ]

    operations = [
        migrations.RunPython(hash_existing_tokens, reverse_code=migrations.RunPython.noop),
    ]
