"""
Phase 121G-D.5 — Encrypt plaintext sources rows in virtual_datasets.

Special: sources is a JSON list (not dict). Migration wraps as {"_items": list}
before encryption, matching the model save() pattern.

Idempotent: skips rows where sources is already a dict with {"_encrypted": ...}.
Batched: processes 100 rows at a time.
"""

import json

from django.db import migrations, connection


BATCH_SIZE = 100


def encrypt_sources_forward(apps, schema_editor):
    """Encrypt all plaintext sources rows (list → wrapped dict → encrypted)."""
    from hub.apps.integrations.encryption import encrypt_json_field

    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, sources FROM virtual_datasets "
            "WHERE sources IS NOT NULL"
        )
        rows = cur.fetchall()

    updates = []
    for row_id, raw in rows:
        data = raw if isinstance(raw, (dict, list)) else json.loads(raw) if raw else None
        if not data:
            continue
        # Already encrypted (dict with _encrypted key)
        if isinstance(data, dict) and "_encrypted" in data:
            continue
        # Already a dict but not encrypted (shouldn't happen, but skip)
        if isinstance(data, dict) and "_encrypted" not in data:
            continue
        # Plaintext list → wrap and encrypt
        if isinstance(data, list):
            wrapper = {"_items": data}
            encrypted = encrypt_json_field(wrapper)
            updates.append((json.dumps({"_encrypted": encrypted}), str(row_id)))

    if updates:
        with connection.cursor() as cur:
            for i in range(0, len(updates), BATCH_SIZE):
                batch = updates[i : i + BATCH_SIZE]
                cur.executemany(
                    "UPDATE virtual_datasets "
                    "SET sources = %s WHERE id = %s",
                    batch,
                )


def encrypt_sources_reverse(apps, schema_editor):
    """Decrypt sources rows back to plaintext list (rollback)."""
    from hub.apps.integrations.encryption import decrypt_json_field

    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, sources FROM virtual_datasets "
            "WHERE sources IS NOT NULL"
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
        # Extract the list from the _items wrapper
        items = decrypted.get("_items", []) if isinstance(decrypted, dict) else []
        updates.append((json.dumps(items), str(row_id)))

    if updates:
        with connection.cursor() as cur:
            for i in range(0, len(updates), BATCH_SIZE):
                batch = updates[i : i + BATCH_SIZE]
                cur.executemany(
                    "UPDATE virtual_datasets "
                    "SET sources = %s WHERE id = %s",
                    batch,
                )


class Migration(migrations.Migration):

    dependencies = [
        ("virtualization", "0005_add_workflow_instance_to_query_execution"),
    ]

    operations = [
        migrations.RunPython(
            encrypt_sources_forward,
            encrypt_sources_reverse,
        ),
    ]
