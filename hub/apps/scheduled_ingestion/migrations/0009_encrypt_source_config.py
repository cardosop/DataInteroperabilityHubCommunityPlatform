"""
Phase 121G-D.1 — Encrypt plaintext source_config rows.

Idempotent: skips rows where source_config already contains {"_encrypted": ...}.
Batched: processes 100 rows at a time to avoid memory issues.
"""

import json

from django.db import migrations, connection


BATCH_SIZE = 100


def encrypt_source_config_forward(apps, schema_editor):
    """Encrypt all plaintext source_config rows."""
    from hub.apps.integrations.encryption import encrypt_json_field

    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, source_config FROM scheduled_ingestions "
            "WHERE source_config IS NOT NULL"
        )
        rows = cur.fetchall()

    updates = []
    for row_id, raw in rows:
        data = raw if isinstance(raw, dict) else json.loads(raw) if raw else None
        if not data or not isinstance(data, dict):
            continue
        if "_encrypted" in data:
            continue  # already encrypted
        encrypted = encrypt_json_field(data)
        updates.append((json.dumps({"_encrypted": encrypted}), str(row_id)))

    if updates:
        with connection.cursor() as cur:
            for i in range(0, len(updates), BATCH_SIZE):
                batch = updates[i : i + BATCH_SIZE]
                cur.executemany(
                    "UPDATE scheduled_ingestions "
                    "SET source_config = %s WHERE id = %s",
                    batch,
                )


def encrypt_source_config_reverse(apps, schema_editor):
    """Decrypt source_config rows back to plaintext (rollback)."""
    from hub.apps.integrations.encryption import decrypt_json_field

    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, source_config FROM scheduled_ingestions "
            "WHERE source_config IS NOT NULL"
        )
        rows = cur.fetchall()

    updates = []
    for row_id, raw in rows:
        data = raw if isinstance(raw, dict) else json.loads(raw) if raw else None
        if not data or not isinstance(data, dict):
            continue
        if "_encrypted" not in data:
            continue  # already plaintext
        decrypted = decrypt_json_field(data["_encrypted"])
        updates.append((json.dumps(decrypted), str(row_id)))

    if updates:
        with connection.cursor() as cur:
            for i in range(0, len(updates), BATCH_SIZE):
                batch = updates[i : i + BATCH_SIZE]
                cur.executemany(
                    "UPDATE scheduled_ingestions "
                    "SET source_config = %s WHERE id = %s",
                    batch,
                )


class Migration(migrations.Migration):

    dependencies = [
        ("scheduled_ingestion", "0008_phase72_dlq_sync_status"),
    ]

    operations = [
        migrations.RunPython(
            encrypt_source_config_forward,
            encrypt_source_config_reverse,
        ),
    ]
