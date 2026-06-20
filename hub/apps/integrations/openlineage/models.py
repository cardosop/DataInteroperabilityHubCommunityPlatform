"""
Phase 228 F4 (228.F4.6) — OpenLineage integration data model.

Two append-mostly tables:

* :class:`OpenLineageIngestApiKey` — per-tenant ingest keys for the
  inbound ``POST /lineage/openlineage/events/`` endpoint. The
  plaintext key is shown ONCE at creation; we persist only the
  ``key_hash`` (bcrypt) so a DB compromise can't replay events.
* :class:`OpenLineageDeadLetter` — archive of events that exhausted
  the adapter's retry budget. ``event_payload`` is encrypted at rest
  via the existing ``hub.apps.webhooks.encryption`` helper (the
  spec calls for ``django-encrypted-fields``; using the in-house
  helper matches the convention every other secret in the codebase
  follows + avoids introducing a parallel encryption substrate).
"""

from __future__ import annotations

import secrets
import uuid

from django.conf import settings
from django.db import models


def generate_ingest_key_plaintext() -> str:
    """Generate a high-entropy plaintext ingest key.

    Returns a URL-safe 48-character string (~256 bits of entropy)
    prefixed with ``msh_ol_`` so leaked keys are greppable in logs.
    The plaintext is shown ONCE at creation; only the bcrypt'd hash
    persists.
    """
    return f"msh_ol_{secrets.token_urlsafe(48)}"


def hash_ingest_key(plaintext: str) -> str:
    """Bcrypt hash of an ingest key.

    The cost factor is fixed at 12 (same as the auth-app password
    hash) so verifying a request against the stored hash takes ~50 ms
    on the production instance class. Higher than 12 would burn
    request CPU; lower would weaken brute-force resistance.
    """
    import bcrypt  # local import — keep module-load cheap.

    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")


def verify_ingest_key(plaintext: str, key_hash: str) -> bool:
    """Constant-time check of plaintext against the stored bcrypt hash."""
    import bcrypt

    try:
        return bcrypt.checkpw(plaintext.encode("utf-8"), key_hash.encode("utf-8"))
    except Exception:
        return False


class OpenLineageIngestApiKey(models.Model):
    """Per-tenant ingest API key for the inbound OpenLineage endpoint.

    The ingest endpoint authenticates by ``Authorization: Bearer
    <plaintext>`` + a per-request HMAC signature (REQ-LIN-F4-002).
    The plaintext is stored ONCE at creation time and surfaced to the
    operator via the response of ``POST /lineage/openlineage/keys/``;
    persisted state holds only ``key_hash``.

    Rotation lives outside this model: see
    ``rotate_openlineage_keys --tenant=<id>`` (228.F4.11) for the
    7-day grace window logic.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="openlineage_ingest_keys",
        db_index=True,
        help_text="Tenant this key belongs to.",
    )
    label = models.CharField(
        max_length=120,
        help_text="Human-readable label (e.g. 'staging-marquez', 'datakin-prod').",
    )
    key_prefix = models.CharField(
        max_length=16,
        db_index=True,
        help_text=(
            "First 8 characters of the plaintext key after the "
            "``msh_ol_`` namespace prefix. Used for log-grep + UI "
            "display so operators can identify a key without seeing "
            "the secret."
        ),
    )
    key_hash = models.CharField(
        max_length=255,
        help_text="Bcrypt hash of the plaintext key (cost factor 12).",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_openlineage_keys",
        null=True,
        blank=True,
        help_text="Admin user who created this key.",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "When the key stops authenticating. NULL = never expires. "
            "The rotate command sets this to ``now + 7 days`` on the "
            "outgoing key when issuing a fresh successor (REQ-LIN-F4-003)."
        ),
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Set when an operator explicitly revokes the key. A revoked "
            "key fails authentication immediately regardless of "
            "``expires_at``."
        ),
    )
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Best-effort last-authenticated-request timestamp.",
    )
    # Phase 228 F4 (REQ-LIN-F4-003 spec scenario "Quarterly rotation grace")
    # — once-per-key latch for the grace-usage audit event. NULL means
    # "no grace-period authentication has been recorded yet"; set to the
    # timestamp of the FIRST grace-period authentication so subsequent
    # requests don't generate one audit row per request.
    grace_audit_emitted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Set to the moment the first grace-period authentication "
            "fired the OPENLINEAGE_KEY_GRACE_USED audit event. NULL = "
            "the key has never authenticated inside its grace window. "
            "Once non-NULL, subsequent grace-period authentications are "
            "NOT audited (the spec scenario only requires the audit "
            "trail capture grace USAGE, not every grace request)."
        ),
    )

    class Meta:
        db_table = "openlineage_ingest_api_key"
        verbose_name = "OpenLineage Ingest API Key"
        verbose_name_plural = "OpenLineage Ingest API Keys"
        indexes = [
            # Operators query by tenant + active-state on the key-mgmt page.
            models.Index(
                fields=["tenant", "revoked_at", "expires_at"],
                name="ol_key_tenant_active_idx",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover — repr only
        return f"OpenLineageIngestApiKey(tenant={self.tenant_id}, prefix={self.key_prefix})"

    def is_active(self, *, now=None) -> bool:
        """True iff the key authenticates: not revoked, not expired."""
        from django.utils import timezone

        n = now or timezone.now()
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at <= n:
            return False
        return True


class OpenLineageDeadLetter(models.Model):
    """Encrypted archive of events that exhausted the adapter's
    retry budget (REQ-LIN-F4-002).

    The payload is encrypted at rest because OpenLineage events
    embed schema details + job metadata that the producer tenant
    classifies as confidential. Decryption is via
    :func:`hub.apps.webhooks.encryption.decrypt_secret` — the same
    helper that gates webhook secret reads, so the audit-trail of
    decryption events is unified.

    Replay is operator-driven (``replay_openlineage_dlq --max=N``)
    or scheduled (``openlineage_dlq_replay`` RQ task). After 10
    permanent-fail attempts the row is marked
    ``permanently_failed=true`` so the next sweep skips it.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="openlineage_dead_letters",
        db_index=True,
        help_text="Tenant whose event landed in the DLQ.",
    )
    # ``event_payload`` is encrypted at rest. We use TextField (not
    # BinaryField) because the encryption helper produces a base64
    # ASCII envelope that round-trips cleanly through JSON / API
    # responses without binary-handling concerns.
    event_payload_encrypted = models.TextField(
        help_text=(
            "Encrypted OpenLineage event payload. Decrypt via "
            "``hub.apps.webhooks.encryption.decrypt_secret``; never "
            "log decrypted contents."
        ),
    )
    event_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text=(
            "OpenLineage event id (run.runId). Used for idempotent "
            "replay — a re-emitted event keeps the same id so Marquez "
            "deduplicates."
        ),
    )
    target_url = models.URLField(
        max_length=2048,
        help_text="Marquez (or other receiver) URL the adapter was POSTing to.",
    )
    failure_reason = models.CharField(
        max_length=255,
        help_text="HTTP status / exception summary that caused the DLQ.",
    )
    failure_detail = models.TextField(
        blank=True,
        default="",
        help_text="Full error body / stack trace (truncated to 2KB).",
    )
    attempts = models.IntegerField(
        default=1,
        help_text="Total adapter delivery attempts before DLQ insert.",
    )
    replay_attempts = models.IntegerField(
        default=0,
        help_text="DLQ-replay attempts (separate from the original adapter retries).",
    )
    permanently_failed = models.BooleanField(
        default=False,
        db_index=True,
        help_text=(
            "Set when ``replay_attempts >= 10``. Replay sweeps skip "
            "permanently-failed rows; ops investigates each one."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    last_replay_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set when a replay finally succeeded; nulled rows are still pending.",
    )
    # Phase 228 F4 (REQ-LIN-F4-004 / DoD self-audit GAP-D9) — scheduled
    # next-retry timestamp. Population is done by the sweep when a
    # row is replayed-and-still-failing: ``next_retry_at = NOW() +
    # backoff(replay_attempts)``. The sweep query filters
    # ``next_retry_at__lte=NOW()`` so a row that just failed isn't
    # immediately re-tried in the same sweep.
    next_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Earliest time the replay sweep will re-try this row. "
            "NULL = ready immediately (initial DLQ insert). The sweep "
            "filters ``next_retry_at__isnull=True OR next_retry_at <= NOW()``."
        ),
    )

    class Meta:
        db_table = "openlineage_dead_letter"
        verbose_name = "OpenLineage Dead Letter"
        verbose_name_plural = "OpenLineage Dead Letters"
        indexes = [
            models.Index(
                fields=["tenant", "permanently_failed", "delivered_at"],
                name="ol_dlq_pending_idx",
            ),
            models.Index(
                fields=["event_id"],
                name="ol_dlq_eventid_idx",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover — repr only
        return f"OpenLineageDeadLetter(tenant={self.tenant_id}, event_id={self.event_id})"

    @property
    def event_payload(self) -> dict:
        """Decrypt the payload on demand. Callers MUST treat the
        result as confidential — never log."""
        import json

        from hub.apps.webhooks.encryption import decrypt_secret

        plain = decrypt_secret(self.event_payload_encrypted)
        return json.loads(plain)

    @event_payload.setter
    def event_payload(self, value: dict) -> None:
        import json

        from hub.apps.webhooks.encryption import encrypt_secret

        self.event_payload_encrypted = encrypt_secret(json.dumps(value, sort_keys=True))


class OpenLineageInboundEvent(models.Model):
    """Phase 228 F4 (REQ-LIN-F4-002 / DoD self-audit GAP-D4) —
    idempotency cache for inbound RunEvents.

    The spec requires that a re-POST of the same ``run.runId`` returns
    the original ``202`` payload unchanged + creates zero additional
    LineageEdge rows. This model is the relational anchor for the
    idempotency check: ``UNIQUE(tenant, event_id)`` is enforced via
    a Postgres unique constraint so concurrent duplicate POSTs cannot
    produce two distinct ``edges_created`` results.

    Storage is intentionally minimal — we persist the response payload
    (``edges_created`` count + accept timestamp) so a duplicate POST
    can return a byte-identical response without re-running the
    translator. Access logs / audit-events carry the full event body.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="openlineage_inbound_events",
        db_index=True,
    )
    event_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="OpenLineage ``run.runId`` — the idempotency key.",
    )
    edges_created = models.IntegerField(
        default=0,
        help_text=(
            "Number of LineageEdge rows the first-accept created. "
            "Returned in the duplicate-POST 202 response so the "
            "original-vs-duplicate semantics are byte-identical."
        ),
    )
    accepted_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "openlineage_inbound_event"
        verbose_name = "OpenLineage Inbound Event"
        verbose_name_plural = "OpenLineage Inbound Events"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "event_id"],
                name="ol_inbound_tenant_eventid_uq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "accepted_at"],
                name="ol_inbound_tenant_time_idx",
            ),
        ]
        ordering = ["-accepted_at"]


__all__ = [
    "OpenLineageDeadLetter",
    "OpenLineageInboundEvent",
    "OpenLineageIngestApiKey",
    "generate_ingest_key_plaintext",
    "hash_ingest_key",
    "verify_ingest_key",
]
