"""
Phase 121G-D.3 — Encrypt plaintext sso_config rows in tenant_configs.

Idempotent: skips rows where sso_config already contains {"_encrypted": ...}.
Batched: processes 100 rows at a time.
"""

import json

from django.db import migrations, connection


BATCH_SIZE = 100


def encrypt_sso_config_forward(apps, schema_editor):
    """Encrypt all plaintext sso_config rows."""
    from hub.apps.integrations.encryption import encrypt_json_field

    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, sso_config FROM tenant_configs "
            "WHERE sso_config IS NOT NULL"
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
                    "UPDATE tenant_configs "
                    "SET sso_config = %s WHERE id = %s",
                    batch,
                )


def encrypt_sso_config_reverse(apps, schema_editor):
    """Decrypt sso_config rows back to plaintext (rollback)."""
    from hub.apps.integrations.encryption import decrypt_json_field

    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, sso_config FROM tenant_configs "
            "WHERE sso_config IS NOT NULL"
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
                    "UPDATE tenant_configs "
                    "SET sso_config = %s WHERE id = %s",
                    batch,
                )


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0020_add_kyc_date_fields"),
    ]

    operations = [
        migrations.RunPython(
            encrypt_sso_config_forward,
            encrypt_sso_config_reverse,
        ),
    ]
