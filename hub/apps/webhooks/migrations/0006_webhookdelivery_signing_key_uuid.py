"""
Migration 0006 — Phase 233.1 (schema).

Adds ``WebhookDelivery.signing_key_uuid`` to pin the public ``key_id`` of
the ``WebhookSigningKey`` used to sign each delivery (REQ-WH-ROT-002).

This decoupling matters for async dispatch: the trigger path computes the
signature using the active key at trigger-time, then enqueues the delivery
record for async fan-out. If a rotation runs between trigger and dispatch,
the dispatcher MUST send the header with the key_id used at sign-time, NOT
the key_id of the current active key — otherwise subscribers verify with
the wrong cached secret.

The field is nullable so:
* Pre-Phase-233 deliveries (in flight at deploy time) keep working — they
  carry no key_id and the dispatcher omits the header, falling back to
  legacy single-key verification on the subscriber side.
* The migration is non-blocking on tables of any size — adding a nullable
  column is a metadata-only change in PostgreSQL ≥ 11.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("webhooks", "0005_backfill_webhook_signing_keys"),
    ]

    operations = [
        migrations.AddField(
            model_name="webhookdelivery",
            name="signing_key_uuid",
            field=models.UUIDField(
                blank=True,
                null=True,
                help_text=(
                    "Public key_id used to sign "
                    "(X-Meshant-Signature-Key-Id header)."
                ),
            ),
        ),
    ]
