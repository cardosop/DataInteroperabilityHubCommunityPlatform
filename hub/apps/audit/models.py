"""
Audit Logging Models

Immutable audit event logging for compliance and security.
"""

import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models.expressions import RawSQL
from django.utils import timezone

# Phase 234.6 — GENERATED-column expression for ``details_json_tsvector``.
# Pinned here as a module-level constant so the model field and the
# migration share ONE source of truth — a future tweak to the lexeme
# weights or the underscore-translate shim updates both call sites
# atomically. Postgres treats ``_`` as a word character; the
# ``translate(.., '_', ' ')`` shim splits ``ASSET_CREATED`` into the
# ``asset`` + ``created`` lexemes operators expect to type in the
# search box.
_DETAILS_TSVECTOR_EXPRESSION_SQL: str = (
    "setweight("
    "to_tsvector('english', translate(coalesce(action, ''), '_', ' '))"
    ", 'A') "
    "|| setweight("
    "to_tsvector('english', translate(coalesce(resource_type, ''), '_', ' '))"
    ", 'B') "
    "|| setweight("
    "jsonb_to_tsvector('english', coalesce(details_json, '{}'::jsonb), '\"all\"')"
    ", 'C')"
)

User = get_user_model()


class ActiveAuditEventManager(models.Manager):
    """Default manager that excludes archived events from queries."""

    def get_queryset(self):
        return super().get_queryset().filter(is_archived=False)


class AuditEvent(models.Model):
    """
    Audit Event model for immutable audit logging.

    All critical actions are logged as audit events for compliance and security.
    Events are append-only and cannot be modified or deleted.

    # Decision: Immutability is enforced at the MODEL layer (not via
    # BusinessRules) because every audit-write path — DRF views, signal
    # handlers, management commands, async workers — must be covered
    # by a single chokepoint. A BusinessRule would require every call
    # site to opt in; model-layer enforcement ensures immutability
    # without per-caller ceremony. (BR6 / D274.11)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        related_name="audit_events",
        null=True,
        blank=True,
        help_text="Tenant this event belongs to (null for platform-level events)",
    )
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="audited_actions",
        null=True,
        blank=True,
        help_text="User who performed the action (null for system events)",
    )
    resource_type = models.CharField(
        max_length=50, help_text="Type of resource (e.g., TENANT, USER, CONTRACT, ASSET, AUTH)"
    )
    resource_id = models.UUIDField(
        null=True, blank=True, help_text="ID of the resource (null for resource-less events)"
    )
    action = models.CharField(
        max_length=100,
        help_text="Action performed (e.g., CREATED, UPDATED, DELETED, LOGIN, LOGOUT)",
    )
    result = models.CharField(
        max_length=20,
        choices=[
            ("SUCCESS", "Success"),
            ("FAILURE", "Failure"),
            ("WARNING", "Warning"),
        ],
        default="SUCCESS",
        help_text="Result of the action",
    )
    details_json = models.JSONField(
        default=dict, help_text="Additional details as JSON (no PII allowed)"
    )
    full_details_json = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Restricted original details. Access ONLY via get_full_details(actor) "
            "with TENANT_ADMIN guard."
        ),
    )
    timestamp = models.DateTimeField(
        db_index=True,
        default=timezone.now,
        help_text=(
            "When the event occurred (UTC). Phase 234.1: ``auto_now_add`` was "
            "replaced with ``default=timezone.now`` so the value is settable "
            "BEFORE ``save()`` runs (the chain hash MUST cover the exact "
            "timestamp that gets persisted). ``default=`` keeps "
            "``bulk_create``/``Manager.create`` behaviour identical to the "
            "previous ``auto_now_add`` contract — every legitimate write "
            "still gets a non-null UTC timestamp without the caller having "
            "to remember to set it."
        ),
    )
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this event has been archived by the retention policy",
    )
    archived_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this event was archived (UTC)",
    )

    # ------------------------------------------------------------------
    # Phase 234.1 — Tamper-evidence: hash chain.
    # ------------------------------------------------------------------
    # All three columns are nullable so the schema migration can land
    # without rewriting historical rows in a single transaction. The
    # ``backfill_audit_chain`` management command (234.1.9) fills the
    # values in batches; the chain is then computed forward by every
    # new ``save()`` call.
    chain_sequence = models.BigIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Phase 234.1 — per-tenant monotonic sequence (1-indexed). "
            "NULL only on pre-backfill rows; ``save()`` will never write "
            "a row with NULL ``chain_sequence``."
        ),
    )
    prev_chain_hash = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text=(
            "Phase 234.1 — SHA-256 hex of the immediately-preceding event in "
            "this tenant's chain. NULL on the genesis (first-per-tenant) row."
        ),
    )
    chain_hash = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text=(
            "Phase 234.1 — SHA-256 hex of "
            "``canonical_form(self) || prev_chain_hash || timestamp_iso``. "
            "NULL only on pre-backfill rows."
        ),
    )

    # ------------------------------------------------------------------
    # Phase 234.6 — Postgres FTS index column.
    # ------------------------------------------------------------------
    # ``details_json_tsvector`` is a STORED ``GENERATED ALWAYS AS (...)``
    # column. Django 5.0+ ``GeneratedField`` is the load-bearing piece:
    # its ``generated=True`` class attribute is what makes Django's
    # ORM EXCLUDE the column from INSERT/UPDATE SQL (see
    # ``django/db/models/base.py:_save_table`` — every field-list
    # comprehension filters on ``not f.generated``). A plain
    # ``SearchVectorField`` here would have failed every INSERT because
    # Postgres rejects user-supplied values for GENERATED columns with
    # ``ERROR: cannot insert a non-DEFAULT value into column``.
    #
    # The expression weighs ``action`` highest ('A'), ``resource_type``
    # next ('B'), and the full ``details_json`` payload last ('C') so
    # ``ts_rank`` ordering pushes action-matches to the top of the
    # result set. The ``translate(.., '_', ' ')`` shim splits
    # ``ASSET_CREATED`` into the two lexemes ``asset`` + ``created`` so
    # ``websearch_to_tsquery`` quoted phrases work for the
    # uppercase-underscore audit-action convention.
    #
    # ``output_field=SearchVectorField(null=True)`` carries the
    # ``tsvector`` column type AND drives the lookup machinery — a
    # ``filter(details_json_tsvector=SearchQuery(...))`` resolves
    # against ``SearchVectorField``'s ``exact`` lookup (the ``@@``
    # operator) via :meth:`GeneratedField.contribute_to_class`.
    details_json_tsvector = models.GeneratedField(
        expression=RawSQL(
            _DETAILS_TSVECTOR_EXPRESSION_SQL,
            params=[],
            output_field=SearchVectorField(),
        ),
        output_field=SearchVectorField(null=True),
        db_persist=True,
    )

    # Phase 277.B.111 — OTel trace_id for cross-system correlation.
    # Extracted from the active span context at audit-write time.
    # Nullable: events created outside a trace span (management commands,
    # tests, background workers without OTel) store None.
    trace_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        default=None,
        help_text="OTel trace_id for cross-system audit/trace/log correlation.",
    )

    # Default manager excludes archived events; use all_objects for admin ops.
    objects = ActiveAuditEventManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "audit_events"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["tenant", "timestamp"]),
            models.Index(fields=["actor_user", "timestamp"]),
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["action", "timestamp"]),
            models.Index(fields=["timestamp"]),  # For retention queries
            models.Index(fields=["is_archived", "timestamp"]),  # For archival queries
            # Phase 234.1.2 — chain-sequence range scan per tenant. The index
            # is created CONCURRENTLY in a separate non-atomic migration so
            # the rollout doesn't lock the audit_events table on large fleets.
            # The state-only declaration here keeps Django's model
            # introspection in sync with the database; the SQL counterpart
            # is in ``0007_chain_index_concurrent`` (RunSQL with
            # ``atomic = False``).
            models.Index(
                fields=["tenant", "chain_sequence"],
                name="ae_tenant_chain_seq_idx",
            ),
            # Phase 234.6.2 — GIN index over the FTS tsvector column.
            # Created CONCURRENTLY in migration 0011 so the rollout
            # doesn't take an ACCESS EXCLUSIVE lock on the hot
            # ``audit_events`` table. The state-only declaration here
            # keeps Django's introspection aligned with the database.
            GinIndex(
                fields=["details_json_tsvector"],
                name="audit_events_details_tsv_gin",
            ),
        ]
        # Prevent updates and deletes
        default_permissions = ()  # No default permissions (read-only)

    def __str__(self):
        return f"{self.action} on {self.resource_type} by {self.actor_user.email if self.actor_user else 'SYSTEM'}"

    def save(self, *args, **kwargs):
        """Override save to prevent updates (append-only) AND populate chain fields.

        Phase 234.1.3 — on INSERT, this method:

        1.  Holds a SHARE ROW EXCLUSIVE lock on the tenant's current chain
            head via ``select_for_update`` so concurrent writers can't both
            claim the same ``chain_sequence``. The lock is per-tenant
            (filtering on ``tenant_id``) so different tenants don't
            contend with each other.
        2.  Computes ``timestamp`` (if unset), then the canonical form,
            then the SHA-256 chain hash binding the canonical content to
            the predecessor hash and the timestamp.
        3.  Persists ``chain_sequence``, ``prev_chain_hash``, ``chain_hash``
            atomically with the row insert.

        Pre-existing call sites that pre-set chain fields (the backfill
        command does this) are honoured: the chain-population step is
        skipped when ``chain_hash`` is already populated. This is the
        idempotent-resume primitive the backfill command relies on.
        """
        # Append-only guard (unchanged from pre-234.1 behaviour).
        if self.pk and AuditEvent.all_objects.filter(pk=self.pk).exists():
            raise ValueError("Audit events are immutable and cannot be updated")

        is_new = self._state.adding or not self.pk
        chain_already_set = bool(self.chain_hash)

        if is_new and not chain_already_set:
            # Local import — chain.py imports nothing from models, but we
            # keep the dependency one-directional at module top.
            from hub.apps.audit.chain import canonical_form, compute_chain_hash

            # Route the predecessor lookup + lock to the SAME DB alias the
            # caller is inserting through. ``create_audit_event`` for the
            # tenant=None path uses the ``admin`` BYPASSRLS connection
            # (separate MVCC snapshot from ``default``) — if we queried
            # ``default`` here we'd miss the row the previous write just
            # inserted on ``admin`` and would re-issue chain_sequence=1.
            using = kwargs.get("using") or self._state.db or "default"

            with transaction.atomic(using=using):
                # Lock the predecessor row to serialize sequence allocation
                # for THIS tenant. ``select_for_update`` blocks (not
                # skip_locked) so concurrent INSERTs into the same tenant
                # are strictly ordered. ``tenant`` may be NULL for
                # platform events — the filter handles both branches.
                # Ignore pre-backfill rows: in PostgreSQL ``ORDER BY DESC``
                # places NULLs FIRST, so a naive ``.first()`` on a tenant
                # with un-chained historical rows would pick a NULL-sequence
                # row and our guard would re-issue chain_sequence=1 over and
                # over. Filtering ``chain_sequence__isnull=False`` ensures
                # the writer always sees the highest *already-chained* row
                # as the head. The backfill command later fills the gap and
                # the sequences join up cleanly.
                prev_qs = (
                    AuditEvent.all_objects.using(using)
                    .select_for_update()
                    .filter(tenant_id=self.tenant_id, chain_sequence__isnull=False)
                    .order_by("-chain_sequence")
                )
                prev = prev_qs.first()
                self.chain_sequence = (
                    (prev.chain_sequence + 1) if (prev and prev.chain_sequence) else 1
                )
                self.prev_chain_hash = prev.chain_hash if prev else None

                # Stamp the timestamp explicitly — ``auto_now_add`` was
                # removed from the field so the value hashed below is
                # the value persisted.
                if not self.timestamp:
                    self.timestamp = timezone.now()
                canonical = canonical_form(self)
                self.chain_hash = compute_chain_hash(
                    canonical,
                    self.prev_chain_hash,
                    self.timestamp.isoformat(),
                )
                super().save(*args, **kwargs)
            return

        # Path 2: chain fields already set (backfill / explicit-set path)
        # OR not a new row (which the guard above already rejected for
        # already-persisted rows). In both legitimate cases, plain save.
        if not self.timestamp:
            self.timestamp = timezone.now()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Override delete to prevent deletion"""
        raise ValueError("Audit events are immutable and cannot be deleted")

    def get_full_details(self, actor_user) -> dict:
        """Return full details for authorized actors only."""
        if actor_user is None:
            raise PermissionDenied("TENANT_ADMIN role is required")
        event_tenant = getattr(self, "tenant", None)
        if event_tenant is None:
            raise PermissionDenied("TENANT_ADMIN role is required")

        actor_tenant = getattr(actor_user, "tenant", None)
        actor_tenant_id = getattr(actor_tenant, "id", None)
        if actor_tenant_id != event_tenant.id:
            raise PermissionDenied("TENANT_ADMIN role is required")

        has_tenant_admin = bool(
            actor_user.user_roles.filter(
                role__tenant=event_tenant,
                role__name="TENANT_ADMIN",
            ).exists()
        )
        if not has_tenant_admin:
            raise PermissionDenied("TENANT_ADMIN role is required")
        return self.full_details_json if self.full_details_json is not None else self.details_json


class AuditMerkleSnapshot(models.Model):
    """Phase 234.1.5–234.1.7 — durable proof-of-tampering-resistance row.

    One row per (tenant, period_start, period_end) describing the Merkle
    root computed over that window's ``AuditEvent.chain_hash`` leaves,
    signed with the tenant's current ``AUDIT_CHAIN_SIGNING_KEYS_JSON``
    key, and uploaded to ``meshant-{env}-audit-merkle-roots`` under S3
    Object Lock with retention = ``AUDIT_RETENTION_YEARS`` * 365 + 365.
    The job that produces these rows is scheduled hourly per tenant
    (see :class:`hub.apps.jobs.models.JobType.AUDIT_MERKLE_SNAPSHOT`).

    Uniqueness on (tenant, period_start, period_end) makes the snapshot
    job idempotent: a re-run for the same window returns the existing
    row instead of writing a duplicate, so a Celery retry can never
    fork the proof trail.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        related_name="audit_merkle_snapshots",
        null=True,
        blank=True,
        help_text=(
            "Tenant whose chain this snapshot covers. ``NULL`` for the "
            "platform-level (no-tenant) audit chain — same dual-track shape "
            "as ``AuditEvent.tenant``."
        ),
    )
    period_start = models.DateTimeField(
        help_text="Inclusive start of the window covered by this snapshot (UTC)."
    )
    period_end = models.DateTimeField(
        help_text="Exclusive end of the window covered by this snapshot (UTC)."
    )
    event_count = models.PositiveIntegerField(
        help_text="Number of AuditEvent rows folded into ``root_hex``."
    )
    first_chain_sequence = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="``chain_sequence`` of the earliest event in the window (NULL when empty).",
    )
    last_chain_sequence = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="``chain_sequence`` of the latest event in the window (NULL when empty).",
    )
    root_hex = models.CharField(
        max_length=64,
        help_text="SHA-256 Merkle root over chain_hash leaves (64 hex chars).",
    )
    signature_hex = models.CharField(
        max_length=128,
        help_text=(
            "HMAC-SHA256 of ``root_hex`` keyed on the tenant's current "
            "``AUDIT_CHAIN_SIGNING_KEYS_JSON`` entry (index 0). 64 hex "
            "chars in practice; column sized at 128 to leave room for a "
            "future migration to a longer primitive."
        ),
    )
    signing_key_index = models.PositiveSmallIntegerField(
        default=0,
        help_text=(
            "Index of the key in the rolling 3-key ring that produced "
            "``signature_hex``. ``verify_root_signature`` walks the whole "
            "ring on lookup so a post-rotation verifier still works."
        ),
    )
    s3_bucket = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="S3 bucket the proof was uploaded to (empty when S3 disabled).",
    )
    s3_key = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="S3 object key for the uploaded proof JSON.",
    )
    s3_version_id = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="S3 VersionId returned by the Object-Lock PUT (empty on fallback).",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the snapshot row was persisted (UTC).",
    )

    class Meta:
        db_table = "audit_merkle_snapshots"
        ordering = ["-period_end", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "period_start", "period_end"],
                name="audit_merkle_unique_window",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "period_end"]),
        ]

    def __str__(self) -> str:
        return (
            f"Merkle[{self.tenant_id}:{self.period_start.isoformat()}→"
            f"{self.period_end.isoformat()}] "
            f"root={self.root_hex[:8]}... ({self.event_count} events)"
        )


# Phase 228 (REQ-LIN-007, 228.0.19) — canonical lineage audit-action codes.
#
# The ``action`` field on ``AuditEvent`` is a free-form CharField, so the
# operational invariant we ship here is a NAMED CONSTANT registry: every
# call site references these constants instead of inlining the string,
# so a typo can't produce two divergent histories of "the same action".
# Pinned by ``test_lineage_audit_codes.py`` which asserts the four
# Phase 228 codes exist and are the only ``LINEAGE_*`` values defined.

LINEAGE_VIEWED = "LINEAGE_VIEWED"
LINEAGE_VIEWED_CROSS_TENANT = "LINEAGE_VIEWED_CROSS_TENANT"
LINEAGE_EDGE_CREATED = "LINEAGE_EDGE_CREATED"
LINEAGE_EDGE_DELETED = "LINEAGE_EDGE_DELETED"
# Phase 228 F5 (REQ-LIN-F5-001 / DoD-G7) — emitted on every successful
# point-in-time lineage query (`?as_of=` or `?version=`).
LINEAGE_SNAPSHOT_QUERIED = "LINEAGE_SNAPSHOT_QUERIED"
# Phase 228 X (REQ-LIN-X-004 / 228.X.4.3) — emitted when a cross-
# region lineage view is gated by the data-residency check + the
# request carried explicit consent. Lets a compliance auditor
# answer "did somebody view EU lineage from a US viewer with
# consent — and when?".
LINEAGE_VIEWED_CROSS_REGION_CONSENTED = "LINEAGE_VIEWED_CROSS_REGION_CONSENTED"

# Phase 228 F4 (REQ-LIN-F4-003) — OpenLineage ingest-key admin
# audit-action codes. Same registry pattern as the lineage codes
# above so a typo in the call-site fails the
# ``test_lineage_audit_codes.py`` constants test.
OPENLINEAGE_KEY_CREATED = "OPENLINEAGE_KEY_CREATED"
OPENLINEAGE_KEY_REVOKED = "OPENLINEAGE_KEY_REVOKED"
OPENLINEAGE_KEY_ROTATED = "OPENLINEAGE_KEY_ROTATED"
# Phase 228 F4 (REQ-LIN-F4-003 spec scenario "Quarterly rotation grace") —
# fired the FIRST time a graced (post-rotation, pre-expiry) key is used
# to authenticate. Once-per-key emission so a busy producer doesn't
# generate one audit row per request; the field
# ``OpenLineageIngestApiKey.grace_audit_emitted_at`` is the latch.
OPENLINEAGE_KEY_GRACE_USED = "OPENLINEAGE_KEY_GRACE_USED"

# Phase 230.8 (REQ-SEM-FED-001) — SPARQL federation audit codes.
# - SEMANTIC_FEDERATED_QUERY: emitted on every federated SERVICE call
#   (including timeouts + DENIED).  Carries target_url + SHA-256 query
#   hash + response_time_ms in details_json so an auditor can answer
#   "did tenant T query partner P with what shape, when, and was it
#   slow".
# - SEMANTIC_FEDERATION_ALLOWLIST_ADD / _REMOVE: emitted on
#   TenantSparqlEndpoint mutations.  Allowlist changes are a security
#   event — auditor must reconstruct the allowlist state at any past
#   point in time from the audit log alone (defence-in-depth against
#   silent allowlist drift).
SEMANTIC_FEDERATED_QUERY = "SEMANTIC_FEDERATED_QUERY"
SEMANTIC_FEDERATION_ALLOWLIST_ADD = "SEMANTIC_FEDERATION_ALLOWLIST_ADD"
SEMANTIC_FEDERATION_ALLOWLIST_REMOVE = "SEMANTIC_FEDERATION_ALLOWLIST_REMOVE"

# Phase 230.2 (REQ-SEM-EXPORT-001) — bulk RDF export audit code.
# Emitted on every successful export with byte-count, format, and
# tenant in details_json. Rejected exports (400/413/429) do NOT
# emit (matches the LDN inbound pattern — failed attempts surface
# in structured logs, not as audit rows).
SEMANTIC_EXPORT = "SEMANTIC_EXPORT"

# Phase 230.3 (REQ-SEM-TOMBSTONE-001) — tombstone lifecycle audit
# code. Emitted on Asset retire / Contract delete / Dataset archive
# AND on the GDPR-purge path. ``details_json`` carries the
# tombstoned IRI + reason (asset_retired / contract_deleted /
# dataset_archived / gdpr_purge).
SEMANTIC_TOMBSTONE = "SEMANTIC_TOMBSTONE"

# Phase 230.10 (REQ-SEM-ONTO-001) — custom ontology lifecycle audit
# codes. UPLOAD covers BOTH successful and validation-failed
# attempts (per audit-fix GAP-A — INVALID rows are persisted with
# validation_errors populated; the audit row distinguishes via
# ``details_json.validation_status``). ACTIVATE / DEACTIVATE fire
# on PATCH is_active transitions.
SEMANTIC_ONTOLOGY_UPLOAD = "SEMANTIC_ONTOLOGY_UPLOAD"
SEMANTIC_ONTOLOGY_ACTIVATE = "SEMANTIC_ONTOLOGY_ACTIVATE"
SEMANTIC_ONTOLOGY_DEACTIVATE = "SEMANTIC_ONTOLOGY_DEACTIVATE"

# Phase 230.12 (REQ-SEM-LDN-001/003) — W3C LDN audit codes.
# INBOUND fires on accepted notifications only (rejected requests
# — 401/413/429 — do NOT emit per spec).
# OUTBOUND fires per delivery attempt (successful + failed retries).
# SUBSCRIPTION_CREATED fires on LdnSubscription.objects.create.
SEMANTIC_LDN_INBOUND = "SEMANTIC_LDN_INBOUND"
SEMANTIC_LDN_OUTBOUND = "SEMANTIC_LDN_OUTBOUND"
SEMANTIC_LDN_SUBSCRIPTION_CREATED = "SEMANTIC_LDN_SUBSCRIPTION_CREATED"

# Phase 230.13 (REQ-SEM-GQL-001) — GraphQL-LD endpoint audit code.
# Emitted on every authenticated GraphQL query (success + failure).
# Carries SHA-256 of the query text in details_json.query_sha256
# (the body is NOT stored — GraphQL queries can carry user-supplied
# input that may contain PII).  Resolver-level outcome
# (SUCCESS/DEPTH_EXCEEDED/COMPLEXITY_EXCEEDED/TIMEOUT/THROTTLED) is
# captured in details_json.outcome.
SEMANTIC_GRAPHQL_QUERY = "SEMANTIC_GRAPHQL_QUERY"

LINEAGE_AUDIT_ACTIONS: tuple[str, ...] = (
    LINEAGE_VIEWED,
    LINEAGE_VIEWED_CROSS_TENANT,
    LINEAGE_VIEWED_CROSS_REGION_CONSENTED,
    LINEAGE_EDGE_CREATED,
    LINEAGE_EDGE_DELETED,
    LINEAGE_SNAPSHOT_QUERIED,
    OPENLINEAGE_KEY_CREATED,
    OPENLINEAGE_KEY_REVOKED,
    OPENLINEAGE_KEY_ROTATED,
    OPENLINEAGE_KEY_GRACE_USED,
    SEMANTIC_FEDERATED_QUERY,
    SEMANTIC_FEDERATION_ALLOWLIST_ADD,
    SEMANTIC_FEDERATION_ALLOWLIST_REMOVE,
    SEMANTIC_GRAPHQL_QUERY,
)

# Phase 230.14.12 — canonical registry of all SEMANTIC_* audit
# action codes added across Phase 230 sub-phases. Pinned by a
# constants test (mirror of LINEAGE_AUDIT_ACTIONS) so a future
# rename or accidental delete fails CI rather than silently
# drifting the audit-trail vocabulary.
SEMANTIC_AUDIT_ACTIONS: tuple[str, ...] = (
    SEMANTIC_EXPORT,
    SEMANTIC_TOMBSTONE,
    SEMANTIC_FEDERATED_QUERY,
    SEMANTIC_FEDERATION_ALLOWLIST_ADD,
    SEMANTIC_FEDERATION_ALLOWLIST_REMOVE,
    SEMANTIC_ONTOLOGY_UPLOAD,
    SEMANTIC_ONTOLOGY_ACTIVATE,
    SEMANTIC_ONTOLOGY_DEACTIVATE,
    SEMANTIC_LDN_INBOUND,
    SEMANTIC_LDN_OUTBOUND,
    SEMANTIC_LDN_SUBSCRIPTION_CREATED,
    SEMANTIC_GRAPHQL_QUERY,
)


class AuditEventRetentionPolicy(models.Model):
    """Phase 234.5 — per-event-type audit retention override.

    The Phase 234.3 ``archive_old_audit_events`` command applies a SINGLE
    global retention window (``settings.AUDIT_RETENTION_YEARS``, default
    3y) to every audit row. That blunt rule fails two real-world needs:

    1.  **Regulator-driven overrides.** GDPR/UK_GDPR auditors expect 7y
        on auth + breach + DSAR-handling events; CCPA accepts 2y on
        marketing-consent events. A single global window is either too
        loose (everything kept 7y → unnecessary storage + PII exposure
        surface) or too strict (everything purged at 3y → compliance
        gap on regulated event classes).
    2.  **Tenant-driven extensions.** Some tenants must keep specific
        event types longer than the platform default for sectoral
        reasons (e.g. finance: 10y on contract-execution events).

    A row in this table overrides the global window for ONE
    ``(tenant, event_type)`` pair. The override can be specified two
    ways — the model normalises both into a single ``retention_days``
    integer in :meth:`clean`:

    * Explicit: pass ``retention_days=N``.
    * Regulation-driven: pass ``regulation_keys=["GDPR", "UK_GDPR", ...]``
      and let the :func:`hub.apps.regulation_policies.registry.data_retention_period_days_for_regime_keys`
      lookup produce the strictest (max) horizon. This is the same
      derivation Phase 232.7 ``RetentionPolicy`` uses on tenant
      business resources — sharing the registry keeps audit retention
      aligned with data-resource retention under the same regimes.

    Validation contract (enforced by :meth:`clean`):

    * At least one of ``retention_days`` or ``regulation_keys`` MUST be
      set (otherwise the row would be a no-op and confuse operators).
    * ``regulation_keys`` (when non-empty) auto-populates
      ``retention_days`` with the registry-derived value. If both are
      provided, the registry-derived value WINS — the regulator's
      contract is the load-bearing constraint, not what the operator
      typed in.
    * ``(tenant, event_type)`` is unique — one override per pair.

    Read path: :func:`resolve_retention_days_for_event_type` is the
    canonical lookup used by ``archive_old_audit_events`` and any
    future surface that needs to know "how long does THIS tenant keep
    THIS event type".
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="audit_event_retention_policies",
        help_text="Tenant this override applies to (per-tenant scoping).",
    )
    event_type = models.CharField(
        max_length=100,
        help_text=(
            "AuditEvent.action value this row overrides "
            "(e.g. ``DSAR_SUBMITTED``, ``BREACH_INCIDENT_OPENED``). "
            "Matched verbatim against the persisted ``action`` column."
        ),
    )
    retention_days = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text=(
            "Days an event of this type is kept before archival. "
            "Auto-populated from ``regulation_keys`` when those are "
            "provided; otherwise must be set explicitly."
        ),
    )
    regulation_keys = ArrayField(
        models.CharField(max_length=64),
        default=list,
        blank=True,
        help_text=(
            'Uppercase regime tokens (e.g. ``["GDPR", "UK_GDPR"]``). '
            "When non-empty, ``retention_days`` is derived from "
            "``data_retention_period_days_for_regime_keys`` — the same "
            "registry Phase 232.7 ``RetentionPolicy`` consults — so "
            "audit retention stays aligned with data-resource retention."
        ),
    )
    enabled = models.BooleanField(
        default=True,
        help_text=(
            "When False, this row is ignored by the resolver — useful "
            "for staging a regime change without deleting history."
        ),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_audit_event_retention_policies",
        null=True,
        blank=True,
        help_text="User who created this override (nullable for system seeds).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "audit_event_retention_policies"
        ordering = ["tenant_id", "event_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "event_type"],
                name="audit_evt_ret_tenant_evt_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "enabled"],
                name="audit_evt_ret_tenant_en_ix",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.event_type} -> {self.retention_days}d"

    # ------------------------------------------------------------------
    # Validation / normalisation
    # ------------------------------------------------------------------

    def clean(self):
        """Normalise ``regulation_keys`` into ``retention_days``.

        Mirrors the Phase 232.7 ``RetentionPolicy.clean`` shape: when
        ``regulation_keys`` is non-empty, the resolver wins; otherwise
        ``retention_days`` must be set explicitly. We also
        case-normalise the regulation key list so ``["gdpr"]`` and
        ``["GDPR"]`` produce the same row (avoids creating two policies
        that collide on the unique constraint via a typo).
        """
        super().clean()

        # Phase 234.5 audit-fix Gap 1 — strip ``event_type`` of leading /
        # trailing whitespace BEFORE the blank check so an operator who
        # types ``"  DSAR_SUBMITTED  "`` doesn't create a row that
        # silently never matches the persisted ``AuditEvent.action``
        # column (byte-for-byte comparison in the archive command).
        # We normalise the stored value in place rather than raising —
        # operator intent is clearly the un-padded string.
        self.event_type = (self.event_type or "").strip()
        if not self.event_type:
            raise ValidationError("event_type must be a non-empty string.")

        # Case-normalise + dedupe regulation_keys (mirrors registry input
        # contract) BEFORE the registry lookup. Stored value is the
        # canonical uppercase + sorted form for stable diffs/audits.
        keys = sorted(
            {str(k).upper().strip() for k in (self.regulation_keys or []) if str(k).strip()}
        )
        self.regulation_keys = list(keys)

        if keys:
            from hub.apps.regulation_policies.registry import (
                data_retention_period_days_for_regime_keys,
            )

            derived = data_retention_period_days_for_regime_keys(keys)
            if derived > 0:
                # Registry win — regulator contract is load-bearing.
                self.retention_days = derived

        if not self.retention_days or self.retention_days < 1:
            raise ValidationError(
                "Either retention_days (>=1) or regulation_keys "
                "resolvable to a positive day count must be provided."
            )

    def save(self, *args, **kwargs):
        """Run ``full_clean`` so the registry-derived retention is computed.

        Matches the Phase 232.7 ``RetentionPolicy.save`` pattern — we
        WANT operators who bulk-create rows via ``.objects.create(...)``
        to get the regulation-key derivation, not a silent NULL
        ``retention_days``.
        """
        self.full_clean()
        super().save(*args, **kwargs)


def resolve_retention_days_for_event_type(
    *,
    tenant_id,
    event_type: str,
    default_days: int,
) -> int:
    """Phase 234.5 — return the effective retention window for one (tenant, event_type).

    Lookup order:

    1.  Active ``AuditEventRetentionPolicy`` row for ``(tenant_id, event_type)``
        with ``enabled=True`` — if found, returns its ``retention_days``.
    2.  Fallback to ``default_days`` (typically the
        ``settings.AUDIT_RETENTION_YEARS`` × 365 day count).

    The function is INTENTIONALLY thin so it can be called inside hot
    archive-sweep loops without dragging in heavy logic. Callers that
    need the row itself (UI, audit emission) should query the model
    directly.
    """
    if not event_type:
        return int(default_days)

    row = (
        AuditEventRetentionPolicy.objects.using("admin")
        .filter(tenant_id=tenant_id, event_type=event_type, enabled=True)
        .values("retention_days")
        .first()
    )
    if row and row["retention_days"]:
        return int(row["retention_days"])
    return int(default_days)
