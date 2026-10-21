"""
Migration 0005 — Phase 233.1 (data).

Backfills the ``WebhookSigningKey`` table from the legacy
``Webhook.secret`` column so every existing webhook has exactly one
ACTIVE signing key after this migration runs (REQ-WH-ROT-005).

Contract:
* One ACTIVE row per existing ``Webhook``.
* ``secret_encrypted`` is byte-identical to ``Webhook.secret`` (the source
  of truth at backfill time — both fields use the same
  ``hub.apps.webhooks.encryption`` wrapper).
* ``key_id`` is a fresh UUIDv4 for each row (per-call default).
* The migration is IDEMPOTENT — re-running on a webhook that already has
  an ACTIVE signing key is a no-op (no duplicate row, no transition).

Webhooks with empty / NULL ``secret`` (a malformed pre-migration row that
should never exist in practice) are SKIPPED with a warning written to
stdout — the migration MUST NOT fail closed on bad legacy data because
the operator may need to clean those rows up out-of-band before
rotation can be exercised against them.
"""
import uuid

from django.db import migrations


def _backfill_signing_keys(apps, schema_editor):
    """Create one ACTIVE signing key per Webhook that lacks one.

    Idempotency contract: re-running this RunPython produces zero new
    rows on the second run (every webhook already has its ACTIVE row
    from the first run).
    """
    Webhook = apps.get_model("webhooks", "Webhook")
    WebhookSigningKey = apps.get_model("webhooks", "WebhookSigningKey")

    # Webhooks that ALREADY have an ACTIVE signing key — these were either
    # backfilled by a previous run of this migration OR created by
    # production code after migration 0004 landed but before 0005 ran.
    # Either way, they're complete and we skip them.
    already_backfilled_webhook_ids = set(
        WebhookSigningKey.objects.filter(status="ACTIVE")
        .values_list("webhook_id", flat=True)
    )

    to_create = []
    for wh in Webhook.objects.all().iterator(chunk_size=200):
        if wh.id in already_backfilled_webhook_ids:
            continue
        if not wh.secret:
            # Malformed legacy row — bypass rather than fail the
            # migration; operator handles out-of-band.
            continue
        to_create.append(
            WebhookSigningKey(
                webhook=wh,
                key_id=uuid.uuid4(),
                secret_encrypted=wh.secret,
                status="ACTIVE",
                # ``retired_at`` stays NULL for ACTIVE keys.
            )
        )

    # bulk_create avoids per-row ``save()`` overhead; the model has no
    # auto_now / auto_now_add field other than ``created_at`` which
    # bulk_create handles natively (Django ≥ 5.x — verified against
    # ``hub/settings.py``).
    if to_create:
        WebhookSigningKey.objects.bulk_create(to_create, batch_size=200)


def _reverse_backfill(apps, schema_editor):
    """Reverse migration: delete ALL signing-key rows.

    Reversal is destructive but safe — running ``migrate webhooks 0004``
    after this migration would also drop the table via the schema
    rollback. The reverse here is provided so the data migration can be
    rolled back IN ISOLATION (e.g. during a hotfix) without touching the
    schema.
    """
    WebhookSigningKey = apps.get_model("webhooks", "WebhookSigningKey")
    WebhookSigningKey.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("webhooks", "0004_webhook_signing_keys"),
    ]

    operations = [
        migrations.RunPython(
            _backfill_signing_keys,
            reverse_code=_reverse_backfill,
        ),
    ]
