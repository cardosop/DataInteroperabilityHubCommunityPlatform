"""
Contract Models

Contract model for managing data contracts with HubContract normalization.
"""
import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex

from .typed_models import validate_hub_contract_dict
from .versioning import get_default_version


class ContractStatus(models.TextChoices):
    """Contract lifecycle status enumeration"""
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    RETIRED = "RETIRED", "Retired"


class ValidationStatus(models.TextChoices):
    """Contract validation status enumeration (from DataContract CLI)"""
    VALID = "VALID", "Valid"
    INVALID = "INVALID", "Invalid"
    WARNING_ONLY = "WARNING_ONLY", "Warning Only"
    ERROR = "ERROR", "Error"
    SKIPPED = "SKIPPED", "Skipped"


class NormalizationStatus(models.TextChoices):
    """Contract normalization status enumeration"""
    NOT_NORMALIZED = "NOT_NORMALIZED", "Not Normalized"
    NORMALIZED_OK = "NORMALIZED_OK", "Normalized OK"
    NORMALIZED_WITH_WARNINGS = "NORMALIZED_WITH_WARNINGS", "Normalized With Warnings"
    NORMALIZATION_FAILED = "NORMALIZATION_FAILED", "Normalization Failed"


class OriginalSpecType(models.TextChoices):
    """Original specification type enumeration

    Supported types:
    - ODCS: Open Data Contract Standard (technical specification)
    - ODPS: Open Data Product Standard (marketplace specification)
    """
    ODCS = "ODCS", "ODCS"
    ODPS = "ODPS", "ODPS"


class OriginalFormat(models.TextChoices):
    """Original contract format enumeration"""
    JSON = "JSON", "JSON"
    YAML = "YAML", "YAML"


class Contract(models.Model):
    """
    Contract model representing a data contract with HubContract normalization.

    Stores original contract (ODCS) and normalized HubContract.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="contracts",
        help_text="Tenant this contract belongs to"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="contracts",
        null=True,
        blank=True,
        help_text="Asset this contract belongs to (nullable for contract-only assets)"
    )
    version = models.IntegerField(
        default=1,
        help_text="Per-asset contract version counter"
    )
    status = models.CharField(
        max_length=20,
        choices=ContractStatus.choices,
        default=ContractStatus.DRAFT,
        help_text="Contract lifecycle status: DRAFT, ACTIVE, RETIRED"
    )

    # Original specification metadata
    original_spec_type = models.CharField(
        max_length=50,
        choices=OriginalSpecType.choices,
        help_text="Original spec type: ODCS (Open Data Contract Standard) or ODPS (Open Data Product Standard)"
    )
    original_spec_version = models.CharField(
        max_length=20,
        help_text="Original spec version (e.g., 3.0.2, 2.2.2)"
    )
    original_format = models.CharField(
        max_length=10,
        choices=OriginalFormat.choices,
        help_text="Original format: JSON or YAML"
    )
    original_raw = models.TextField(
        help_text="Original contract file content (verbatim)"
    )
    original_raw_resolved = models.TextField(
        null=True,
        blank=True,
        help_text="Original contract content with all $ref references resolved (cached for performance)"
    )

    # HubContract normalization
    hub_contract_version = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="HubContract version (e.g., 1.0.0)"
    )
    hub_contract_json = models.JSONField(
        db_index=False,  # No full-column index: large JSON (>8KB) exceeds PostgreSQL index key limit.
        null=True,
        blank=True,
        help_text="Normalized HubContract JSON"
    )
    normalization_status = models.CharField(
        max_length=30,
        choices=NormalizationStatus.choices,
        null=True,
        blank=True,
        default=NormalizationStatus.NOT_NORMALIZED,
        help_text="Normalization status"
    )
    normalization_errors = models.JSONField(
        null=True,
        blank=True,
        default=list,
        help_text="Normalization errors (JSON array)"
    )
    normalization_warnings = models.JSONField(
        null=True,
        blank=True,
        default=list,
        help_text="Normalization warnings (JSON array)"
    )

    # CLI validation result
    validation_status = models.CharField(
        max_length=20,
        choices=ValidationStatus.choices,
        null=True,
        blank=True,
        help_text="CLI validation status: VALID, INVALID, WARNING_ONLY, ERROR"
    )
    validation_errors = models.JSONField(
        null=True,
        blank=True,
        default=list,
        help_text="Validation errors (JSON array)"
    )
    validation_warnings = models.JSONField(
        null=True,
        blank=True,
        default=list,
        help_text="Validation warnings (JSON array)"
    )
    cli_version = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="DataContract CLI version used"
    )
    last_validated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last validation timestamp"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_contracts",
        null=True,
        blank=True,
        help_text="User who created the contract"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Full-text search vector (Phase 18.2).
    # Covers original_spec_type (A), hub_contract_version (B).
    search_vector = SearchVectorField(
        null=True,
        blank=True,
        help_text=(
            "PostgreSQL tsvector for full-text search "
            "(auto-maintained via post_save signal)"
        ),
    )

    class Meta:
        db_table = "contracts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "asset"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "validation_status"]),
            GinIndex(
                fields=["search_vector"],
                name="contract_search_vector_gin_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "asset", "version"],
                condition=models.Q(asset__isnull=False),
                name="unique_contract_version_per_asset"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["DRAFT", "ACTIVE", "RETIRED"]),
                name="contract_status_valid",
            ),
        ]

    def __str__(self):
        asset_name = self.asset.name if self.asset else "No Asset"
        return f"{asset_name} - {self.original_spec_type} v{self.original_spec_version} ({self.status})"

    # Fields that cannot be changed once contract is ACTIVE
    _IMMUTABLE_WHEN_ACTIVE = frozenset({
        "hub_contract_json",
        "original_raw",
        "original_spec_type",
        "original_format",
        "validation_status",
        "normalization_status",
    })

    def clean(self):
        """Validate contract status rules and immutability."""
        super().clean()

        # Reject changes to critical fields on ACTIVE contracts
        if self.pk:
            try:
                prev = type(self).objects.only(
                    "status", *self._IMMUTABLE_WHEN_ACTIVE
                ).get(pk=self.pk)
                if prev.status == ContractStatus.ACTIVE:
                    changed = [
                        f
                        for f in self._IMMUTABLE_WHEN_ACTIVE
                        if getattr(self, f) != getattr(prev, f)
                    ]
                    if changed:
                        raise ValidationError(
                            f"Cannot modify {', '.join(changed)} "
                            f"on an ACTIVE contract. Retire and "
                            f"create a new version instead."
                        )
            except type(self).DoesNotExist:
                pass

        if self.hub_contract_json:
            validated_contract, validation_errors = validate_hub_contract_dict(self.hub_contract_json)
            if validation_errors:
                raise ValidationError({"hub_contract_json": validation_errors})
            expected_version = get_default_version()
            if validated_contract and str(validated_contract.hub_contract_version) != expected_version:
                raise ValidationError({"hub_contract_json": [f"hub_contract_version must be {expected_version}"]})

        # Enforce ACTIVE status requirements
        if self.status == ContractStatus.ACTIVE:
            # Must have valid validation status
            if self.validation_status not in [ValidationStatus.VALID, ValidationStatus.WARNING_ONLY]:
                raise ValidationError(
                    f"Contract cannot be ACTIVE with validation_status={self.validation_status}. "
                    f"Required: VALID or WARNING_ONLY"
                )

            # Must have successful normalization
            if self.normalization_status not in [
                NormalizationStatus.NORMALIZED_OK,
                NormalizationStatus.NORMALIZED_WITH_WARNINGS
            ]:
                raise ValidationError(
                    f"Contract cannot be ACTIVE with normalization_status={self.normalization_status}. "
                    f"Required: NORMALIZED_OK or NORMALIZED_WITH_WARNINGS"
                )

    def can_activate(self) -> tuple[bool, str]:
        """
        Check if contract can be activated.

        Returns:
            Tuple of (can_activate: bool, reason: str)
        """
        if self.validation_status not in [ValidationStatus.VALID, ValidationStatus.WARNING_ONLY]:
            return False, f"validation_status must be VALID or WARNING_ONLY (current: {self.validation_status})"

        if self.normalization_status not in [
            NormalizationStatus.NORMALIZED_OK,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS
        ]:
            return False, f"normalization_status must be NORMALIZED_OK or NORMALIZED_WITH_WARNINGS (current: {self.normalization_status})"

        return True, ""


class MigrationCheckpoint(models.Model):
    """
    Phase 227 Wave 1 (227.L6.2) — checkpoint persistence for resumable
    bulk operations.

    Records `(migration_name, contract_id, status, error, completed_at)`
    so a long-running data migration can be killed mid-batch and resumed
    without double-processing already-completed contracts. The unique
    constraint on `(migration_name, contract_id)` enforces idempotence:
    a re-run hits the unique-violation path on rows that succeeded
    previously and skips them via `exclude(id__in=...)`.

    Status taxonomy
    ---------------
    * ``done`` — contract was successfully processed by the migration.
    * ``failed`` — contract raised during processing; ``error`` carries
      the truncated exception message for ops triage.
    * ``in_progress`` — reserved for future use (currently we write
      ``done``/``failed`` directly because each batch is wrapped in
      ``transaction.atomic`` and only commits on success).

    Why a dedicated model rather than a Django migration entry
    -----------------------------------------------------------
    Django's ``django_migrations`` table tracks migrations as a whole;
    this model tracks per-contract progress *within* a single migration.
    A bulk re-normalization affects 50,000 rows — the unit of resumption
    must be the row, not the migration.
    """

    STATUS_DONE = "done"
    STATUS_FAILED = "failed"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_CHOICES = [
        (STATUS_DONE, "Done"),
        (STATUS_FAILED, "Failed"),
        (STATUS_IN_PROGRESS, "In Progress"),
    ]

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    migration_name = models.CharField(
        max_length=255,
        db_index=True,
        help_text=(
            "Logical migration name (operator-supplied via the "
            "``--checkpoint-table`` flag). Becomes the partition key "
            "for resumability — different migrations with the same "
            "contract_id do not collide."
        ),
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.CASCADE,
        related_name="migration_checkpoints",
        help_text="Contract being processed",
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_DONE,
        db_index=True,
        help_text=(
            "Per-contract outcome. ``done`` = success (skip on resume); "
            "``failed`` = error captured (skip on resume; ops can rerun "
            "by deleting the row); ``in_progress`` = reserved."
        ),
    )
    error = models.TextField(
        null=True,
        blank=True,
        help_text=(
            "Truncated exception message when ``status='failed'``. "
            "``None`` for ``done`` rows."
        ),
    )
    completed_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When this row was inserted (UTC).",
    )

    class Meta:
        db_table = "migration_checkpoints"
        ordering = ["-completed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["migration_name", "contract"],
                name="unique_checkpoint_per_migration_per_contract",
            )
        ]
        indexes = [
            models.Index(
                fields=["migration_name", "status"],
                name="checkpoint_mig_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.migration_name}/{self.contract_id} → {self.status}"
        )


class SecurityAuditLog(models.Model):
    """
    Security audit log for ODPS $ref resolution security events.

    Stores security events including:
    - External $ref fetches (URL, tenant_id, user_id, timestamp)
    - Rate limit violations (level, tenant_id, user_id, timestamp)
    - Security violations (URL validation failures, path traversal attempts)
    - Cache operations (hits, misses, evictions)

    Events are append-only and cannot be modified or deleted for compliance.
    """
    # Event identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Type of security event (e.g., EXTERNAL_REF_FETCH, RATE_LIMIT_EXCEEDED, CACHE_HIT, CACHE_MISS, CACHE_EVICTION, SECURITY_VIOLATION)"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the event occurred (UTC)"
    )

    # Context
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        related_name="security_audit_logs",
        null=True,
        blank=True,
        help_text="Tenant this event belongs to (null for platform-level events)"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="security_audit_logs",
        null=True,
        blank=True,
        help_text="User who triggered the event (null for system events)"
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.SET_NULL,
        related_name="security_audit_logs",
        null=True,
        blank=True,
        help_text="Contract associated with the event (if applicable)"
    )

    # Event details
    severity = models.CharField(
        max_length=20,
        choices=[
            ("LOW", "Low"),
            ("MEDIUM", "Medium"),
            ("HIGH", "High"),
            ("CRITICAL", "Critical"),
        ],
        null=True,
        blank=True,
        help_text="Severity level (for security violations)"
    )
    ref_type = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Reference type (internal, local, external)"
    )
    ref_path = models.CharField(
        max_length=2048,
        null=True,
        blank=True,
        help_text="The $ref path/URL"
    )
    resolved_path = models.CharField(
        max_length=2048,
        null=True,
        blank=True,
        help_text="Resolved path/URL"
    )

    # Rate limit details
    rate_limit_level = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Rate limit level (global, tenant, user)"
    )

    # Cache operation details
    cache_operation = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Cache operation type (hit, miss, eviction)"
    )
    cache_key = models.CharField(
        max_length=512,
        null=True,
        blank=True,
        help_text="Cache key (for cache operations)"
    )
    eviction_reason = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Eviction reason (for cache evictions)"
    )

    # Security violation details
    violation_type = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Human-readable violation type"
    )
    attempted_path = models.CharField(
        max_length=2048,
        null=True,
        blank=True,
        help_text="Attempted path (for path traversal)"
    )
    attempted_url = models.CharField(
        max_length=2048,
        null=True,
        blank=True,
        help_text="Attempted URL (for URL violations)"
    )

    # Additional metadata
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Detailed description of the event"
    )
    metadata_json = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text="Additional metadata as JSON"
    )

    # Request context
    request_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Request ID for tracing"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the request"
    )
    user_agent = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="User agent string"
    )

    class Meta:
        db_table = "security_audit_logs"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["event_type", "timestamp"]),
            models.Index(fields=["tenant", "timestamp"]),
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["tenant", "event_type", "timestamp"]),
            models.Index(fields=["tenant", "user", "timestamp"]),
            models.Index(fields=["ref_type", "timestamp"]),
            models.Index(fields=["cache_operation", "timestamp"]),
            models.Index(fields=["timestamp"]),  # For retention queries
        ]
        # Prevent updates and deletes
        default_permissions = ()  # No default permissions (read-only)

    def __str__(self):
        return f"{self.event_type} - {self.tenant.name if self.tenant else 'SYSTEM'} - {self.timestamp}"

    def save(self, *args, **kwargs):
        """Override save to prevent updates (append-only)"""
        if self.pk and SecurityAuditLog.objects.filter(pk=self.pk).exists():
            raise ValueError("Security audit logs are immutable and cannot be updated")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Override delete to prevent deletion"""
        raise ValueError("Security audit logs are immutable and cannot be deleted")


class SecurityIncident(models.Model):
    """
    Security incident model for tracking and managing security incidents.

    Tracks security incidents detected from security violations and suspicious patterns.
    Incidents can be OPEN, INVESTIGATING, or RESOLVED.
    """
    # Incident identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(
        max_length=255,
        help_text="Incident title"
    )
    description = models.TextField(
        help_text="Incident description"
    )

    # Severity and status
    severity = models.CharField(
        max_length=20,
        choices=[
            ("LOW", "Low"),
            ("MEDIUM", "Medium"),
            ("HIGH", "High"),
            ("CRITICAL", "Critical"),
        ],
        db_index=True,
        help_text="Incident severity level"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("OPEN", "Open"),
            ("INVESTIGATING", "Investigating"),
            ("RESOLVED", "Resolved"),
        ],
        default="OPEN",
        db_index=True,
        help_text="Incident status"
    )

    # Context
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        related_name="security_incidents",
        null=True,
        blank=True,
        help_text="Tenant this incident belongs to (null for platform-level incidents)"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="security_incidents",
        null=True,
        blank=True,
        help_text="User associated with the incident (if applicable)"
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.SET_NULL,
        related_name="security_incidents",
        null=True,
        blank=True,
        help_text="Contract associated with the incident (if applicable)"
    )

    # Incident details
    event_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Type of security event that triggered the incident"
    )
    violation_count = models.IntegerField(
        default=1,
        help_text="Number of violations that contributed to this incident"
    )
    first_detected_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the incident was first detected"
    )
    last_updated_at = models.DateTimeField(
        auto_now=True,
        db_index=True,
        help_text="When the incident was last updated"
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When the incident was resolved"
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="resolved_security_incidents",
        null=True,
        blank=True,
        help_text="User who resolved the incident"
    )
    resolution_notes = models.TextField(
        null=True,
        blank=True,
        help_text="Notes about how the incident was resolved"
    )

    # Related security audit logs
    related_audit_logs = models.ManyToManyField(
        "contracts.SecurityAuditLog",
        related_name="security_incidents",
        blank=True,
        help_text="Security audit logs related to this incident"
    )

    # Additional metadata
    metadata_json = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text="Additional metadata as JSON"
    )

    class Meta:
        db_table = "security_incidents"
        ordering = ["-first_detected_at"]
        indexes = [
            models.Index(fields=["severity", "status", "first_detected_at"]),
            models.Index(fields=["tenant", "status", "first_detected_at"]),
            models.Index(fields=["event_type", "status", "first_detected_at"]),
            models.Index(fields=["status", "first_detected_at"]),
            models.Index(fields=["first_detected_at"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.severity} - {self.status}"

    def resolve(self, resolved_by_user=None, resolution_notes=None):
        """Mark incident as resolved."""
        from django.utils import timezone
        self.status = "RESOLVED"
        self.resolved_at = timezone.now()
        if resolved_by_user:
            self.resolved_by = resolved_by_user
        if resolution_notes:
            self.resolution_notes = resolution_notes
        self.save()


class LineageEdgeType(models.TextChoices):
    """Phase 228 (REQ-LIN-001) — edge-type taxonomy.

    The five values map to the lineage operations Meshant tracks:

    * ``upload`` — raw data upload landed an asset.
    * ``transformation`` — a transformation job (DBT, Spark, custom)
      produced a target field from one or more source fields.
    * ``derivation`` — a contract-time derivation rule (a SQL expression
      stored on the contract) maps source → target.
    * ``export`` — a target consumer (data product, marketplace listing,
      external system) reads from the source.
    * ``reference`` — a contract declares an upstream reference without a
      transformation rule (the default for contract-to-contract lineage).
    """

    UPLOAD = "upload", "Upload"
    TRANSFORMATION = "transformation", "Transformation"
    DERIVATION = "derivation", "Derivation"
    EXPORT = "export", "Export"
    REFERENCE = "reference", "Reference"


class LineageEdge(models.Model):
    """Phase 228 (REQ-LIN-001) — derived lineage-edge index.

    Canonical write source is ``Contract.hub_contract_json.lineage``;
    this table is maintained by the ``post_save`` signal handler in
    :mod:`hub.apps.contracts.lineage_sync` (REQ-LIN-002). Application
    writers SHOULD NOT update this table directly outside the sync
    handler or the ``backfill_lineage_edges`` management command —
    direct writes risk drift from the JSONB source of truth.

    The model implements SCD Type 2 versioning (ADR-LIN-002) via the
    ``valid_from`` / ``valid_to`` columns. An edge is "current" when
    ``valid_to IS NULL``. Updates close the prior open row and insert
    a new one, preserving the audit trail.

    Time-travel queries SHALL use:

    .. code-block:: sql

        WHERE valid_from <= :as_of
          AND (valid_to IS NULL OR valid_to > :as_of)

    See REQ-LIN-004 + the ``LineageService.<method>(as_of=...)``
    parameter for the production read-path.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="lineage_edges",
        db_index=True,
        help_text="Tenant owning the edge (cascade deletes the row).",
    )
    source_contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.SET_NULL,
        related_name="outgoing_lineage_edges",
        null=True,
        blank=True,
        db_index=True,
        help_text="Upstream contract; NULL for cross-tenant or external sources.",
    )
    target_contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.SET_NULL,
        related_name="incoming_lineage_edges",
        null=True,
        blank=True,
        db_index=True,
        help_text="Downstream contract; NULL for cross-tenant or external targets.",
    )
    source_model = models.CharField(
        max_length=255, blank=True, default="",
        help_text="Source model name (HubContract.models[*].name).",
    )
    source_field = models.CharField(
        max_length=255, blank=True, default="",
        help_text="Source field name (HubContract.models[*].fields[*].name).",
    )
    target_model = models.CharField(
        max_length=255, blank=True, default="",
        help_text="Target model name.",
    )
    target_field = models.CharField(
        max_length=255, blank=True, default="",
        help_text="Target field name.",
    )
    edge_type = models.CharField(
        max_length=32,
        choices=LineageEdgeType.choices,
        default=LineageEdgeType.REFERENCE,
        help_text="Edge classification (upload / transformation / derivation / export / reference).",
    )
    transformation_ref = models.CharField(
        max_length=512, blank=True, default="",
        help_text="Reference to the transformation that produced the edge (e.g. dbt model id, SQL expression).",
    )
    job_ref = models.CharField(
        max_length=512, blank=True, default="",
        help_text="Reference to the job/pipeline that ran the transformation (e.g. Airflow run id).",
    )
    valid_from = models.DateTimeField(
        # ``Func('NOW')`` enforces DB-side timestamps so app clock-skew
        # cannot violate the SCD Type 2 monotonicity invariant
        # (REQ-LIN-F5-006). Pinned by ``test_lineage_clock_skew.py``.
        db_default=models.functions.Now(),
        db_index=True,
        help_text="When this edge became current (DB NOW()).",
    )
    valid_to = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When this edge stopped being current; NULL means still current.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Row insert timestamp (audit-only; NOT the validity start — see ``valid_from``).",
    )
    created_by_run = models.CharField(
        max_length=255, blank=True, default="",
        help_text=(
            "Identifier for the run that created this edge — typically the "
            "lineage-sync handler's run-id, or the backfill command's "
            "checkpoint key."
        ),
    )

    class Meta:
        db_table = "contracts_lineage_edge"
        verbose_name = "Lineage Edge"
        verbose_name_plural = "Lineage Edges"
        indexes = [
            # Composite indexes for the SCD Type 2 read path (REQ-LIN-001).
            # Each index supports "edges current at :as_of for contract X".
            models.Index(
                fields=["source_contract", "valid_from", "valid_to"],
                name="lin_edge_src_validity_idx",
            ),
            models.Index(
                fields=["target_contract", "valid_from", "valid_to"],
                name="lin_edge_tgt_validity_idx",
            ),
            # Tenant + edge_type for "all transformation edges in tenant T".
            models.Index(
                fields=["tenant", "edge_type"],
                name="lin_edge_tenant_type_idx",
            ),
        ]
        constraints = [
            # Unique constraint on the open-edge tuple — at most one
            # current row per scope. Enforced only when ``valid_to IS NULL``
            # so closed historical rows can repeat the same scope tuple
            # (an edge can be reopened with the same shape after a close).
            models.UniqueConstraint(
                fields=[
                    "tenant",
                    "source_contract",
                    "target_contract",
                    "source_model",
                    "source_field",
                    "target_model",
                    "target_field",
                    "edge_type",
                ],
                condition=models.Q(valid_to__isnull=True),
                name="lin_edge_open_unique",
            ),
        ]

    def __str__(self) -> str:
        src = (
            str(self.source_contract_id)[:8]
            if self.source_contract_id
            else "(ext)"
        )
        tgt = (
            str(self.target_contract_id)[:8]
            if self.target_contract_id
            else "(ext)"
        )
        return f"LineageEdge[{self.edge_type}] {src} → {tgt}"


class LineageEdgeArchive(models.Model):
    """Phase 228 F5 (REQ-LIN-F5-003 / 228.F5.5) — cold-tier archive for
    closed lineage edges older than the 12-month hot retention window.

    Lifecycle (per OP-3 sign-off, see [docs/architecture/lineage-archive-op3.md](
    ../../docs/architecture/lineage-archive-op3.md)):

    ``LineageEdge`` (hot, 12 mo) → ``LineageEdgeArchive`` (warm, 24 mo)
    → S3 standard (36 mo) → S3 Glacier (84 mo) → S3 Deep Archive.

    The ``archive_lineage_edges`` management command (228.F5.6) moves
    closed-and-old rows from ``LineageEdge`` to this table; the same
    command with ``--target=s3`` exports a parquet/jsonl bundle to
    the configured S3 bucket and then deletes the archive rows it
    successfully exported.

    Schema duplicates ``LineageEdge`` field-for-field — the archive is
    a literal cold copy. The model intentionally has NO unique
    constraint on the scope tuple: archived rows are append-only +
    historical, so two archive rows representing different validity
    windows for the same scope tuple co-exist by design.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Original LineageEdge id — preserved so a restore-to-hot operation
    # (rare but useful in incident recovery) can use the canonical id.
    original_edge_id = models.UUIDField(
        db_index=True,
        help_text="``LineageEdge.id`` from the row this entry was archived from.",
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="archived_lineage_edges",
        db_index=True,
    )
    # Source / target contracts may have been deleted by the time
    # archival runs — store as nullable FK with SET_NULL so a deleted
    # contract doesn't cascade-delete the archive entry.
    source_contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True, blank=True, db_index=True,
    )
    target_contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True, blank=True, db_index=True,
    )
    source_model = models.CharField(max_length=255, blank=True, default="")
    source_field = models.CharField(max_length=255, blank=True, default="")
    target_model = models.CharField(max_length=255, blank=True, default="")
    target_field = models.CharField(max_length=255, blank=True, default="")
    edge_type = models.CharField(
        max_length=32,
        choices=LineageEdgeType.choices,
        default=LineageEdgeType.REFERENCE,
    )
    transformation_ref = models.CharField(max_length=512, blank=True, default="")
    job_ref = models.CharField(max_length=512, blank=True, default="")
    valid_from = models.DateTimeField(db_index=True)
    valid_to = models.DateTimeField(null=True, blank=True, db_index=True)
    # When this row was moved out of the hot table.
    archived_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # When (if) the row was exported to S3 — set by ``archive_lineage_edges
    # --target=s3``. ``s3_uri`` carries the resulting object key.
    exported_to_s3_at = models.DateTimeField(null=True, blank=True, db_index=True)
    s3_uri = models.CharField(max_length=2048, blank=True, default="")

    class Meta:
        db_table = "contracts_lineage_edge_archive"
        verbose_name = "Archived Lineage Edge"
        verbose_name_plural = "Archived Lineage Edges"
        indexes = [
            models.Index(
                fields=["tenant", "valid_to"],
                name="lin_arch_tenant_validto_idx",
            ),
            models.Index(
                fields=["archived_at"],
                name="lin_arch_archived_at_idx",
            ),
            models.Index(
                fields=["exported_to_s3_at"],
                name="lin_arch_s3_exported_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"LineageEdgeArchive[{self.edge_type}] orig={self.original_edge_id}"


class LineageSubscriptionSeverity(models.TextChoices):
    """Severity tier choices for ``LineageSubscription.severity_threshold``.

    Mirrors :class:`hub.apps.contracts.lineage_severity.Severity` so the
    DB column and the classifier share a single canonical vocabulary.
    """
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    CRITICAL = "CRITICAL", "Critical"


class LineageSubscription(models.Model):
    """Phase 228.F3.3 (REQ-LIN-F3-002) — user opt-in for lineage-impact
    notifications.

    A subscription points at exactly ONE source — either a contract or
    an asset — and the dispatcher walks the downstream lineage graph
    from that source on each ``contract.updated`` event to decide who
    to page.

    Constraints (DB-level, not just app-level):

    * **Exactly one of** ``source_contract`` / ``source_asset`` is set.
      Enforced by a ``CheckConstraint`` so the dispatcher's "subscription
      keyed on (contract OR asset)" walk has no ambiguous rows.
    * **Unique** ``(user, source_contract, source_asset)`` — a user
      cannot subscribe twice to the same source.

    The per-user 100-subscription cap (REQ-LIN-F3-002) is enforced at
    the API layer (the DB UNIQUE doesn't bound count, just duplicates).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lineage_subscriptions",
        db_index=True,
    )
    source_contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.CASCADE,
        related_name="lineage_subscriptions",
        null=True, blank=True, db_index=True,
    )
    source_asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="lineage_subscriptions",
        null=True, blank=True, db_index=True,
    )
    severity_threshold = models.CharField(
        max_length=16,
        choices=LineageSubscriptionSeverity.choices,
        default=LineageSubscriptionSeverity.HIGH,
    )
    in_app = models.BooleanField(default=True)
    email = models.BooleanField(default=False)
    # F3 v1 channel-decision (REQ-LIN-F3-008): Slack is a v2 follow-on.
    # Field exists so v2 doesn't need a migration; UI hides the toggle
    # in v1 and the dispatcher ignores the flag.
    slack = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    last_dispatched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "contracts_lineage_subscription"
        verbose_name = "Lineage Subscription"
        verbose_name_plural = "Lineage Subscriptions"
        constraints = [
            # Exactly one of (source_contract, source_asset) must be
            # set — XOR enforced at the DB level so cross-tenant
            # consistency holds even on direct DB writes.
            models.CheckConstraint(
                name="lineage_sub_xor_source",
                condition=(
                    models.Q(source_contract__isnull=False, source_asset__isnull=True)
                    | models.Q(source_contract__isnull=True, source_asset__isnull=False)
                ),
            ),
            # A user cannot have two subscriptions pointing at the
            # same source.  ``UniqueConstraint`` with the nullable
            # FK columns relies on Postgres treating NULLs as
            # distinct in unique indexes — so the constraint reduces
            # to "unique per non-null source", which is exactly the
            # spec semantics.
            models.UniqueConstraint(
                fields=["user", "source_contract", "source_asset"],
                name="lineage_sub_unique_user_source",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "created_at"],
                name="lin_sub_user_created_idx",
            ),
            models.Index(
                fields=["source_contract", "severity_threshold"],
                name="lin_sub_contract_sev_idx",
            ),
        ]

    def __str__(self) -> str:
        target = self.source_contract_id or self.source_asset_id
        return f"LineageSubscription[user={self.user_id} source={target}]"
