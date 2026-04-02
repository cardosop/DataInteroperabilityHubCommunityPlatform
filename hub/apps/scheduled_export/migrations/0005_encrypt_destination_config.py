"""
Phase 121G-D.2 — Encrypt plaintext destination_config rows.

Idempotent: skips rows where destination_config already contains {"_encrypted": ...}.
Batched: processes 100 rows at a time.
"""

import json

from django.db import migrations, connection


BATCH_SIZE = 100


def encrypt_destination_config_forward(apps, schema_editor):
    """Encrypt all plaintext destination_config rows."""
    from hub.apps.integrations.encryption import encrypt_json_field

    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, destination_config FROM scheduled_exports "
            "WHERE destination_config IS NOT NULL"
        )
        rows = cur.fetchall()

    updates = []
    for row_id, raw in rows:
        data = raw if isinstance(raw, dict) else json.loads(raw) if raw else None
        if not data or not isinstance(data, dict):
            continue
        if "_encrypted" in data:
            continue
        encrypted = encrypt_json_field(data)
        updates.append((json.dumps({"_encrypted": encrypted}), str(row_id)))

    if updates:
        with connection.cursor() as cur:
            for i in range(0, len(updates), BATCH_SIZE):
                batch = updates[i : i + BATCH_SIZE]
                cur.executemany(
                    "UPDATE scheduled_exports "
                    "SET destination_config = %s WHERE id = %s",
                    batch,
                )


def encrypt_destination_config_reverse(apps, schema_editor):
    """Decrypt destination_config rows back to plaintext (rollback)."""
    from hub.apps.integrations.encryption import decrypt_json_field

    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, destination_config FROM scheduled_exports "
            "WHERE destination_config IS NOT NULL"
        )
        rows = cur.fetchall()

    updates = []
    for row_id, raw in rows:
        data = raw if isinstance(raw, dict) else json.loads(raw) if raw else None
        if not data or not isinstance(data, dict):
            continue
        if "_encrypted" not in data:
            continue
        decrypted = decrypt_json_field(data["_encrypted"])
        updates.append((json.dumps(decrypted), str(row_id)))

    if updates:
        with connection.cursor() as cur:
            for i in range(0, len(updates), BATCH_SIZE):
                batch = updates[i : i + BATCH_SIZE]
                cur.executemany(
                    "UPDATE scheduled_exports "
                    "SET destination_config = %s WHERE id = %s",
                    batch,
                )


class Migration(migrations.Migration):

    dependencies = [
        ("scheduled_export", "0004_add_failure_tracking_fields"),
    ]

    operations = [
        migrations.RunPython(
            encrypt_destination_config_forward,
            encrypt_destination_config_reverse,
        ),
    ]
