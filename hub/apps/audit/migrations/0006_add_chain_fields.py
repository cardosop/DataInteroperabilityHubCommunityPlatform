"""Phase 234.1.1 — append-only chain fields on ``AuditEvent``.

Three nullable columns + the ``AuditMerkleSnapshot`` table. All chain
columns are nullable so the rollout is non-blocking on large fleets:
the ``backfill_audit_chain`` management command (234.1.9) fills them
in batches per tenant after the schema lands.

The matching ``CREATE INDEX CONCURRENTLY`` for
``(tenant_id, chain_sequence)`` lives in the FOLLOWING migration
(``0007_chain_index_concurrent``) which is marked ``atomic = False`` —
Postgres rejects ``CREATE INDEX CONCURRENTLY`` inside a transaction
block, so it MUST run in its own non-atomic migration.

The ``auto_now_add=True`` removal on ``AuditEvent.timestamp`` is
behaviour-preserving: ``AuditEvent.save()`` now stamps the field
explicitly before computing the chain hash so the hashed and stored
timestamps cannot disagree.
"""
import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0005_enable_rls_audit_events"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        # --- AuditEvent chain columns --------------------------------------
        migrations.AddField(
            model_name="auditevent",
            name="chain_sequence",
            field=models.BigIntegerField(
                null=True,
                blank=True,
                help_text=(
                    "Phase 234.1 — per-tenant monotonic sequence (1-indexed). "
                    "NULL only on pre-backfill rows; save() will never write "
                    "a row with NULL chain_sequence."
                ),
            ),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="prev_chain_hash",
            field=models.CharField(
                max_length=64,
                null=True,
                blank=True,
                help_text=(
                    "Phase 234.1 — SHA-256 hex of the immediately-preceding "
                    "event in this tenant's chain. NULL on the genesis row."
                ),
            ),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="chain_hash",
            field=models.CharField(
                max_length=64,
                null=True,
                blank=True,
                help_text=(
                    "Phase 234.1 — SHA-256 hex of "
                    "canonical_form(self) || prev_chain_hash || timestamp_iso."
                ),
            ),
        ),
        # --- Replace auto_now_add with default=timezone.now ----------------
        # ``save()`` stamps the timestamp explicitly before computing the
        # chain hash; auto_now_add would overwrite our value at pre_save
        # and the hashed-vs-stored microsecond would disagree. Switching to
        # ``default=timezone.now`` preserves the previous "no-caller-set →
        # auto-populated" contract for ALL write paths (including
        # ``bulk_create`` which doesn't call ``save()``), without
        # interfering with the hash-coverage invariant.
        migrations.AlterField(
            model_name="auditevent",
            name="timestamp",
            field=models.DateTimeField(
                db_index=True,
                default=django.utils.timezone.now,
                help_text=(
                    "When the event occurred (UTC). Phase 234.1: auto_now_add "
                    "replaced with default=timezone.now so save() can stamp the "
                    "value BEFORE computing the chain_hash; bulk_create still "
                    "auto-populates via the field default."
                ),
            ),
        ),
        # --- AuditMerkleSnapshot table -------------------------------------
        migrations.CreateModel(
            name="AuditMerkleSnapshot",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("period_start", models.DateTimeField(help_text="Inclusive start of the window covered by this snapshot (UTC).")),
                ("period_end", models.DateTimeField(help_text="Exclusive end of the window covered by this snapshot (UTC).")),
                ("event_count", models.PositiveIntegerField(help_text="Number of AuditEvent rows folded into root_hex.")),
                ("first_chain_sequence", models.BigIntegerField(blank=True, null=True, help_text="chain_sequence of the earliest event in the window (NULL when empty).")),
                ("last_chain_sequence", models.BigIntegerField(blank=True, null=True, help_text="chain_sequence of the latest event in the window (NULL when empty).")),
                ("root_hex", models.CharField(max_length=64, help_text="SHA-256 Merkle root over chain_hash leaves (64 hex chars).")),
                ("signature_hex", models.CharField(max_length=128, help_text="HMAC-SHA256 of root_hex keyed on the tenant's current AUDIT_CHAIN_SIGNING_KEYS_JSON entry.")),
                ("signing_key_index", models.PositiveSmallIntegerField(default=0, help_text="Index of the key in the rolling 3-key ring that produced signature_hex.")),
                ("s3_bucket", models.CharField(blank=True, default="", max_length=255, help_text="S3 bucket the proof was uploaded to (empty when S3 disabled).")),
                ("s3_key", models.CharField(blank=True, default="", max_length=512, help_text="S3 object key for the uploaded proof JSON.")),
                ("s3_version_id", models.CharField(blank=True, default="", max_length=128, help_text="S3 VersionId returned by the Object-Lock PUT (empty on fallback).")),
                ("created_at", models.DateTimeField(auto_now_add=True, help_text="When the snapshot row was persisted (UTC).")),
                (
                    "tenant",
                    models.ForeignKey(
                        blank=True,
                        help_text=(
                            "Tenant whose chain this snapshot covers. NULL for the "
                            "platform-level (no-tenant) audit chain."
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_merkle_snapshots",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "audit_merkle_snapshots",
                "ordering": ["-period_end", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="auditmerklesnapshot",
            index=models.Index(
                fields=["tenant", "period_end"],
                name="audit_merkle_tenant_pend_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="auditmerklesnapshot",
            constraint=models.UniqueConstraint(
                fields=["tenant", "period_start", "period_end"],
                name="audit_merkle_unique_window",
            ),
        ),
    ]
