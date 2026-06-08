"""
Migration 0004 — Phase 233.1 (schema).

Creates the ``WebhookSigningKey`` table to support the rolling 3-key
signature window. The table replaces the single ``Webhook.secret``
column as the source of truth for HMAC signing, with three lifecycle
states (ACTIVE / RETIRING / RETIRED) and a partial unique index that
enforces the "at most one ACTIVE row per webhook" invariant
(REQ-WH-ROT-001).

The legacy ``Webhook.secret`` column is preserved for the duration of
the deprecation window — the data migration ``0005`` backfills one
``WebhookSigningKey`` row per existing ``Webhook``, and the delivery
path reads the new table; the legacy column is dropped in a future
migration once all consumers have cut over.
"""
import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("webhooks", "0003_encrypt_webhook_secrets"),
    ]

    operations = [
        migrations.CreateModel(
            name="WebhookSigningKey",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "key_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                        help_text="Public key identifier (sent in delivery header).",
                    ),
                ),
                (
                    "secret_encrypted",
                    models.CharField(
                        max_length=4096,
                        help_text="Encrypted HMAC secret (KMS or Fernet wrapper).",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ACTIVE", "Active"),
                            ("RETIRING", "Retiring"),
                            ("RETIRED", "Retired"),
                        ],
                        default="ACTIVE",
                        max_length=10,
                        help_text="Lifecycle state — see WebhookSigningKeyStatus.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "retired_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        help_text="When the key transitions out of ACTIVE (24h overlap target).",
                    ),
                ),
                (
                    "webhook",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="signing_keys",
                        to="webhooks.webhook",
                        help_text="Parent webhook this key signs deliveries for.",
                    ),
                ),
            ],
            options={
                "db_table": "webhook_signing_keys",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["webhook", "status"],
                        name="wh_signing_keys_wh_stat_idx",
                    ),
                    models.Index(
                        fields=["status", "retired_at"],
                        name="wh_signing_keys_stat_ret_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("status", "ACTIVE")),
                        fields=("webhook",),
                        name="webhook_signing_keys_one_active_per_webhook",
                    ),
                ],
            },
        ),
    ]
