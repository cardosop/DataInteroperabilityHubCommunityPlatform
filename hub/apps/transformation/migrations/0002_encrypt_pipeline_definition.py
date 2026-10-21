"""
Phase 121G-D.6 — Encrypt plaintext pipeline_definition rows.

Idempotent: skips rows where pipeline_definition already contains {"_encrypted": ...}.
Batched: processes 100 rows at a time.
"""

import json

from django.db import migrations, connection


BATCH_SIZE = 100


def encrypt_pipeline_definition_forward(apps, schema_editor):
    """Encrypt all plaintext pipeline_definition rows."""
    from hub.apps.integrations.encryption import encrypt_json_field

    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, pipeline_definition FROM transformation_pipelines "
            "WHERE pipeline_definition IS NOT NULL"
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
                    "UPDATE transformation_pipelines "
                    "SET pipeline_definition = %s WHERE id = %s",
                    batch,
                )


def encrypt_pipeline_definition_reverse(apps, schema_editor):
    """Decrypt pipeline_definition rows back to plaintext (rollback)."""
    from hub.apps.integrations.encryption import decrypt_json_field

    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, pipeline_definition FROM transformation_pipelines "
            "WHERE pipeline_definition IS NOT NULL"
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
                    "UPDATE transformation_pipelines "
                    "SET pipeline_definition = %s WHERE id = %s",
                    batch,
                )


class Migration(migrations.Migration):

    dependencies = [
        ("transformation", "0001_initial_115a"),
    ]

    operations = [
        migrations.RunPython(
            encrypt_pipeline_definition_forward,
            encrypt_pipeline_definition_reverse,
        ),
    ]
