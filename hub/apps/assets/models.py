"""
Assets Models

Asset model for managing data products (contract + dataset).
"""
import logging
import uuid
import warnings

from django.db import models
from django.db.utils import DatabaseError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex


_logger = logging.getLogger(__name__)


class AssetStatus(models.TextChoices):
    """Asset lifecycle status enumeration"""
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    PUBLIC = "PUBLIC", "Public"
    RETIRED = "RETIRED", "Retired"


class AssetVisibility(models.TextChoices):
    """Asset visibility enumeration"""
    INTERNAL = "INTERNAL", "Internal"
    PUBLIC = "PUBLIC", "Public"


class DQStatus(models.TextChoices):
    """Data Quality status enumeration"""
    UNKNOWN = "UNKNOWN", "Unknown"
    PASS = "PASS", "Pass"
    WARN = "WARN", "Warning"
    FAIL = "FAIL", "Fail"


class ComplianceStatus(models.TextChoices):
    """Compliance status enumeration"""
    UNKNOWN = "UNKNOWN", "Unknown"
    PASS = "PASS", "Pass"
    WARN = "WARN", "Warning"
    FAIL = "FAIL", "Fail"


class SemanticStatus(models.TextChoices):
    """Phase 250.7.A.1 — semantic-mapping + search-indexing status.

    Tracks whether the asset is fully discoverable in the semantic
    layer + search index, OR landed in a degraded state because one
    of the post-activation best-effort steps (semantic mapping via
    Fuseki RPC, search indexing via OpenSearch) failed. Per D250.6
    the asset still ACTIVATES on degradation; this field is the
    durable signal so the SPA can render a "active but not yet
    discoverable" banner inline.

    Values mirror the DQ / Compliance enum shape so the FE can use
    the same status-badge component across all three surfaces.
    """
    UNKNOWN = "UNKNOWN", "Unknown"
    PASS = "PASS", "Pass"
    WARN = "WARN", "Warning"
    FAIL = "FAIL", "Fail"


class AssetSourceType(models.TextChoices):
    """Asset source type enumeration"""
    HUB_NATIVE = "HUB_NATIVE", "Hub Native"
    FEDERATED = "FEDERATED", "Federated"


class DataStrategy(models.TextChoices):
    """Data strategy enumeration for federated assets"""
    METADATA_ONLY = "METADATA_ONLY", "Metadata Only"
    DOWNLOAD_SELECTIVE = "DOWNLOAD_SELECTIVE", "Selective Download"
    DOWNLOAD_ALL = "DOWNLOAD_ALL", "Download All"
    # Phase 275.A.3 — live warehouse query (no full table copy).
    LIVE_QUERY = "LIVE_QUERY", "Live Query"


class Asset(models.Model):
    """
    Asset model representing a logical data product (contract + dataset).

    Assets are the primary entities in the catalog, linking contracts and datasets.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="assets",
        help_text="Tenant this asset belongs to"
    )
    key = models.CharField(
        max_length=255,
        help_text="Human-friendly identifier, unique per tenant"
    )
    name = models.CharField(
        max_length=255,
        help_text="Asset name"
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Asset description"
    )
    domain = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Domain (e.g., marketing, finance)"
    )
    status = models.CharField(
        max_length=20,
        choices=AssetStatus.choices,
        default=AssetStatus.DRAFT,
        help_text="Asset lifecycle status: DRAFT, ACTIVE, PUBLIC, RETIRED"
    )
    # Phase 250.3.B.1 — ``visibility`` is no longer a stored column,
    # exposed as a @property deriving from ``status`` per D250.4.
    # The DB column is retained for forensic/rollback safety (phase-2
    # drop after 3 release cycles).  The model field is declared here
    # with null=True, blank=True so Django's ORM is aware of the column
    # during INSERT (the migration removed it from Django state via
    # SeparateDatabaseAndState, but we restored it to avoid
    # NotNullViolation on test INSERT paths).
    visibility = models.CharField(
        max_length=20, null=True, blank=True,
        help_text="[DEPRECATED] Derived from status via @property"
    )
    dq_status = models.CharField(
        max_length=20,
        choices=DQStatus.choices,
        default=DQStatus.UNKNOWN,
        help_text="Data Quality status: UNKNOWN, PASS, WARN, FAIL"
    )
    compliance_status = models.CharField(
        max_length=20,
        choices=ComplianceStatus.choices,
        default=ComplianceStatus.UNKNOWN,
        help_text="Compliance status: UNKNOWN, PASS, WARN, FAIL"
    )
    # Phase 250.7.A.1 — semantic-mapping + search-indexing status.
    # Per D250.6, semantic / search failures during activation are
    # observability events, not gates: the asset still ACTIVATES on
    # degradation and this field carries the marker so the SPA can
    # render a "active but not yet discoverable" banner inline.
    # Default UNKNOWN so pre-existing assets are NOT silently flagged
    # as PASS or FAIL by the migration backfill — UNKNOWN is the
    # honest "we haven't checked yet" state.
    semantic_status = models.CharField(
        max_length=20,
        choices=SemanticStatus.choices,
        default=SemanticStatus.UNKNOWN,
        help_text=(
            "Phase 250.7.A — semantic-mapping + search-indexing "
            "status: UNKNOWN (default; not yet checked), PASS "
            "(both succeeded), WARN (partial degradation reserved "
            "for future granular failures), FAIL (one or both "
            "failed; asset is ACTIVE but not discoverable in "
            "semantic search)."
        ),
    )
    version = models.IntegerField(
        default=1,
        help_text="Optimistic locking version counter"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_assets",
        null=True,
        blank=True,
        help_text="User who created the asset"
    )
    # Popularity and health metrics
    health_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Overall health score (0-100) combining DQ, compliance, freshness, usage"
    )
    popularity_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Popularity score (0-100) based on views, downloads, usage frequency"
    )
    view_count = models.IntegerField(
        default=0,
        help_text="Number of times asset has been viewed"
    )
    download_count = models.IntegerField(
        default=0,
        help_text="Number of times asset has been downloaded"
    )
    source_type = models.CharField(
        max_length=20,
        choices=AssetSourceType.choices,
        default=AssetSourceType.HUB_NATIVE,
        help_text="Asset source: HUB_NATIVE (created in Hub) or FEDERATED (imported from marketplace)"
    )
    source_metadata = models.JSONField(
        null=True,
        blank=True,
        help_text="Source metadata for federated assets: marketplace_type, marketplace_id, listing_id, listing_url, synced_at, sync_job_id"
    )
    metadata_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Hub-managed metadata (e.g. contract_warnings from invalidation cascade)",
    )
    # Phase 232.4 — RoPA Article 30-style metadata scaffold (processing inventory).
    processing_purposes = models.ManyToManyField(
        "consent.ConsentPurpose",
        related_name="ropa_assets",
        blank=True,
        help_text="Consent / processing purposes applicable to this asset for RoPA exports.",
    )
    categories_of_subjects = models.JSONField(
        default=list,
        blank=True,
        help_text="Categories of data subjects (structured labels for supervisory registers).",
    )
    recipient_categories = models.JSONField(
        default=list,
        blank=True,
        help_text="Categories of recipients of personal data.",
    )
    # Phase 232.6 — processors tied to RoPA / Article 28-style inventory.
    processors = models.ManyToManyField(
        "processor_agreements.Processor",
        through="processor_agreements.AssetProcessorMembership",
        related_name="assets",
        blank=True,
        help_text="Processors (data processing agreements) linked to this asset.",
    )
    data_strategy = models.CharField(
        max_length=30,
        choices=DataStrategy.choices,
        default=DataStrategy.METADATA_ONLY,
        help_text="Data strategy: METADATA_ONLY, DOWNLOAD_SELECTIVE, DOWNLOAD_ALL, LIVE_QUERY (Phase 275)"
    )
    # Phase 275.A.3 — nullable FK to warehouse connection for LIVE_QUERY assets.
    warehouse_connection = models.ForeignKey(
        "warehouses.WarehouseConnection",
        on_delete=models.SET_NULL,
        related_name="assets",
        null=True,
        blank=True,
        help_text="Warehouse connection for LIVE_QUERY assets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Full-text search vector (Phase 18.2).
    # Populated asynchronously via post_save → RQ task.
    # Covers name (A), description (B), domain (C).
    search_vector = SearchVectorField(
        null=True,
        blank=True,
        help_text="PostgreSQL tsvector for full-text search (auto-maintained)",
    )
    # Phase 230.8.9 (REQ-SEM-FED-002) — per-resource federation
    # opt-out.  When True, this asset's triples are excluded from
    # incoming federated SERVICE responses.  Defaults to False so the
    # opt-out is explicit, not implicit.
    semantic_federate_optout = models.BooleanField(
        default=False,
        help_text=(
            "When True, this resource's triples are NOT exposed to "
            "external federated SERVICE queries (REQ-SEM-FED-002)."
        ),
    )

    class Meta:
        db_table = "assets"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "key"]),
            # Phase 250.3.B.2 — ``(tenant, visibility)`` index removed
            # alongside the visibility model-field declaration. Queries
            # that previously filtered by visibility are translated to
            # ``status`` filters at the view layer (see
            # ``AssetViewSet.get_queryset`` visibility-filter branch),
            # so the existing ``(tenant, status)`` index covers them.
            models.Index(fields=["tenant", "dq_status"]),
            models.Index(fields=["tenant", "compliance_status"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "source_type"]),
            GinIndex(fields=["search_vector"], name="asset_search_vector_gin_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "key"],
                name="unique_asset_key_per_tenant"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["DRAFT", "ACTIVE", "PUBLIC", "RETIRED"]
                ),
                name="asset_status_valid",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.key})"

    # ------------------------------------------------------------------
    # Phase 250.3.B — visibility-as-property (deprecation phase 1)
    # ------------------------------------------------------------------
    #
    # Per D250.4, ``visibility`` is no longer a stored column — it
    # derives from ``status``: PUBLIC iff ``status == AssetStatus.PUBLIC``,
    # else INTERNAL. Phase-1 deprecation:
    #
    # * Reads route through the ``visibility`` property (returns derived).
    # * Writes are silently absorbed: a ``DeprecationWarning`` fires AND
    #   an ``ASSET_VISIBILITY_WRITE_DEPRECATED`` audit row is emitted
    #   (best-effort; audit-DB outages don't block the no-op).
    # * Construction with ``Asset(visibility=X, ...)`` is supported for
    #   backwards compat — the kwarg is popped in ``__init__`` and
    #   routed through the deprecation setter so the legacy call site
    #   doesn't crash with ``TypeError: 'visibility' is an invalid
    #   keyword argument``.

    def __init__(self, *args, **kwargs):
        legacy_visibility_write = kwargs.pop("visibility", None)
        super().__init__(*args, **kwargs)
        if legacy_visibility_write is not None:
            # Route through the setter so the deprecation signals fire
            # uniformly regardless of whether the call site used
            # ``Asset(visibility=X)`` or ``asset.visibility = X``.
            self.visibility = legacy_visibility_write

    @property
    def visibility(self) -> str:
        """Derived asset visibility per D250.4.

        Returns ``AssetVisibility.PUBLIC`` iff ``self.status ==
        AssetStatus.PUBLIC``, otherwise ``AssetVisibility.INTERNAL``.
        Reads NEVER touch the legacy DB column (which is being nulled
        by migration ``0013_visibility_to_property`` and dropped in
        phase-2).
        """
        if self.status == AssetStatus.PUBLIC:
            return AssetVisibility.PUBLIC
        return AssetVisibility.INTERNAL

    @visibility.setter
    def visibility(self, value):
        """Phase-1 deprecation no-op.

        The write is silently absorbed (status — and therefore the
        derived visibility — is not mutated) but BOTH:

        1. A ``DeprecationWarning`` is issued so ``-W
           error::DeprecationWarning`` in CI catches stragglers.
        2. An ``ASSET_VISIBILITY_WRITE_DEPRECATED`` audit row is
           emitted (best-effort) so dashboards can track caller-side
           adoption and gate the phase-2 column-drop on zero events
           per D250.4.
        """
        warnings.warn(
            (
                "Asset.visibility is a derived @property as of Phase "
                "250.3.B (D250.4); writes are silently ignored. To "
                "make an asset publicly visible, set ``status="
                "AssetStatus.PUBLIC``. The visibility column is "
                "scheduled for removal in phase-2 — three release "
                "cycles after zero deprecation events."
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        # Best-effort audit emission. Using local imports so the model
        # module doesn't pull in audit at import time (avoids circular
        # imports — ``audit.utils`` imports from a few other apps and
        # the assets app is high in the dependency graph).
        try:
            from hub.apps.audit import event_types as _audit_event_types
            from hub.apps.audit.utils import create_audit_event

            create_audit_event(
                resource_type=_audit_event_types.ASSET_RESOURCE_TYPE,
                action=_audit_event_types.ASSET_VISIBILITY_WRITE_DEPRECATED,
                actor_user=getattr(self, "created_by", None),
                tenant=getattr(self, "tenant", None),
                resource_id=str(self.pk) if self.pk else None,
                result="WARNING",
                details={
                    "tenant_id": (
                        str(self.tenant_id)
                        if getattr(self, "tenant_id", None)
                        else None
                    ),
                    "asset_id": str(self.pk) if self.pk else None,
                    "attempted_value": str(value) if value is not None else None,
                    "call_site": "model.setter",
                    "current_status": str(self.status),
                    "derived_visibility": (
                        AssetVisibility.PUBLIC
                        if self.status == AssetStatus.PUBLIC
                        else AssetVisibility.INTERNAL
                    ),
                },
            )
        except (OSError, ConnectionError, TimeoutError) as audit_exc:
            # Transient infrastructure failure — audit emission is
            # best-effort. The deprecation warning above is the
            # load-bearing signal.
            _logger.warning(
                "asset_visibility_deprecation_audit_emit_failed",
                extra={
                    "asset_id": str(self.pk) if self.pk else None,
                    "error": str(audit_exc),
                },
            )
        except DatabaseError as audit_exc:
            # Database error during audit emission — still best-effort
            # (don't crash the setter), but log at ERROR so it surfaces
            # in Sentry/DataDog for engineering investigation.
            _logger.error(
                "asset_visibility_deprecation_audit_emit_failed",
                extra={
                    "asset_id": str(self.pk) if self.pk else None,
                    "error": str(audit_exc),
                },
            )

    # Valid status transitions (state machine)
    VALID_TRANSITIONS = {
        AssetStatus.DRAFT: [AssetStatus.ACTIVE],
        AssetStatus.ACTIVE: [AssetStatus.PUBLIC, AssetStatus.RETIRED],
        AssetStatus.PUBLIC: [AssetStatus.RETIRED],
        AssetStatus.RETIRED: [],  # Terminal state
    }

    def clean(self):
        """Validate asset status transitions and activation requirements."""
        super().clean()

        # Enforce state machine transitions
        if self.pk:
            try:
                previous = Asset.objects.only("status").get(pk=self.pk)
                if (
                    previous.status != self.status
                    and self.status not in self.VALID_TRANSITIONS.get(
                        previous.status, []
                    )
                ):
                    raise ValidationError(
                        f"Invalid status transition: "
                        f"{previous.status} → {self.status}. "
                        f"Allowed transitions from {previous.status}: "
                        f"{self.VALID_TRANSITIONS.get(previous.status, [])}"
                    )
            except Asset.DoesNotExist:
                pass  # New object, no transition to validate

        # Enforce ACTIVE status requirements
        if self.status == AssetStatus.ACTIVE:
            # Check contract requirements
            active_contract = self.contracts.filter(status="ACTIVE").first()
            if not active_contract:
                raise ValidationError(
                    "Asset cannot be ACTIVE without an ACTIVE contract"
                )

            if active_contract.validation_status not in ["VALID", "WARNING_ONLY"]:
                raise ValidationError(
                    f"Asset cannot be ACTIVE with contract validation_status={active_contract.validation_status}. "
                    f"Required: VALID or WARNING_ONLY"
                )

            if active_contract.normalization_status not in [
                "NORMALIZED_OK",
                "NORMALIZED_WITH_WARNINGS"
            ]:
                raise ValidationError(
                    f"Asset cannot be ACTIVE with contract normalization_status={active_contract.normalization_status}. "
                    f"Required: NORMALIZED_OK or NORMALIZED_WITH_WARNINGS"
                )

            # Phase 227 Wave 1 (227.L4.1) — structural-floor check at the
            # ORM level. ALWAYS-ON per the 2026-04-30 ungate directive.
            # Only the currently-active contract drives the gate;
            # historic contract versions of the same asset are NOT
            # retroactively validated. ``Asset.clean()`` is invoked on
            # ``full_clean()`` (e.g. admin PATCH), making this the
            # last-line defense for direct ORM saves bypassing the
            # service layer.
            #
            # When hub_contract_json has no structural payload (None,
            # empty dict, missing models/fields, or a stub like
            # {"hub_contract_version": 1}), the floor check is
            # skipped — the contract can activate before the async
            # normalisation pipeline populates real structure.
            from hub.apps.contracts.structureless import is_payload_structureless
            if not is_payload_structureless(active_contract.hub_contract_json):
                from hub.apps.contracts.structural_floor import (
                    enforce_structural_floor,
                )
                from hub.apps.core.services.base import (
                    ValidationError as _ServiceValidationError,
                )
                try:
                    enforce_structural_floor(
                        active_contract.hub_contract_json,
                        spec_type=active_contract.original_spec_type,
                        spec_version=active_contract.original_spec_version,
                        contract_id=str(active_contract.id),
                        warnings=active_contract.normalization_warnings or [],
                    )
                except _ServiceValidationError as exc:
                    # Translate the typed ValidationError into Django's so
                    # the standard form-validation pipeline carries the
                    # message; preserve the subcode in the message body so
                    # ops can grep audit logs.
                    subcode = (exc.details or {}).get("subcode", "STRUCTURELESS")
                    raise ValidationError(
                        f"Asset cannot be ACTIVE: contract has no resolvable "
                        f"models or schema fields ({subcode}). "
                        f"Open the Schema editor to add structure before "
                        f"activating."
                    )

            # Check dataset requirements (if dataset exists)
            dataset = self.datasets.first()
            if dataset:
                if self.dq_status not in [DQStatus.PASS, DQStatus.WARN]:
                    raise ValidationError(
                        f"Asset cannot be ACTIVE with dq_status={self.dq_status}. "
                        f"Required: PASS or WARN"
                    )

                if self.compliance_status not in [ComplianceStatus.PASS, ComplianceStatus.WARN]:
                    raise ValidationError(
                        f"Asset cannot be ACTIVE with compliance_status={self.compliance_status}. "
                        f"Required: PASS or WARN"
                    )

    def compliance_intake_scan_gate_satisfied(self) -> bool:
        """True when the latest compliance run clears the Phase 231.1 intake gate."""
        from hub.apps.compliance.intake_scan import (
            compliance_intake_gate_satisfied_for_asset,
        )

        return compliance_intake_gate_satisfied_for_asset(self)

    def can_activate(self) -> tuple[bool, list[str]]:
        """
        Check if asset can be activated.

        Returns:
            Tuple of (can_activate: bool, blockers: list[str])
        """
        blockers = []

        # Check contract requirements
        active_contract = self.contracts.filter(status="ACTIVE").first()
        if not active_contract:
            blockers.append("Asset must have an ACTIVE contract")
        else:
            # Check contract validation status
            if active_contract.validation_status not in ["VALID", "WARNING_ONLY"]:
                blockers.append(
                    f"Contract validation_status must be VALID or WARNING_ONLY "
                    f"(current: {active_contract.validation_status})"
                )

            # Check contract normalization status
            if active_contract.normalization_status not in [
                "NORMALIZED_OK",
                "NORMALIZED_WITH_WARNINGS"
            ]:
                blockers.append(
                    f"Contract normalization_status must be NORMALIZED_OK or NORMALIZED_WITH_WARNINGS "
                    f"(current: {active_contract.normalization_status})"
                )

            # Phase 227 Wave 1 (227.L4.1) — structural-floor check.
            # ALWAYS-ON per the 2026-04-30 ungate directive. Multi-version
            # semantics: only the currently-active contract is checked
            # (we already filtered on ``status="ACTIVE"`` above); historic
            # contract versions of the same asset SHALL NOT be
            # retroactively validated.
            #
            # When hub_contract_json has no structural payload (None,
            # empty dict, missing models/fields, or a stub like
            # {"hub_contract_version": 1}), the floor check is
            # skipped — the contract can activate before the async
            # normalisation pipeline populates real structure.
            from hub.apps.contracts.structureless import is_payload_structureless
            if not is_payload_structureless(active_contract.hub_contract_json):
                from hub.apps.contracts.structural_floor import (
                    collect_structural_floor_errors,
                )
                floor_errors = collect_structural_floor_errors(
                    active_contract.hub_contract_json,
                    spec_type=active_contract.original_spec_type,
                    spec_version=active_contract.original_spec_version,
                    contract_id=str(active_contract.id),
                    warnings=active_contract.normalization_warnings or [],
                )
                for err in floor_errors:
                    subcode = err.get("subcode", "STRUCTURELESS")
                    hint = err.get("hint", "")
                    remediation = err.get("remediation_url", "")
                    blockers.append(
                        f"Contract has no resolvable models or schema fields "
                        f"({subcode}). {hint} See: {remediation}"
                    )

        # Check dataset requirements (if dataset exists)
        # Contract-only assets (no dataset) are allowed
        dataset = self.datasets.first()
        if dataset:
            # Check DQ status
            if self.dq_status not in [DQStatus.PASS, DQStatus.WARN]:
                blockers.append(
                    f"dq_status must be PASS or WARN (current: {self.dq_status})"
                )

            # Check compliance status
            if self.compliance_status not in [ComplianceStatus.PASS, ComplianceStatus.WARN]:
                blockers.append(
                    f"compliance_status must be PASS or WARN (current: {self.compliance_status})"
                )

        from hub.apps.compliance.intake_scan import COMPLIANCE_INTAKE_ACTIVATION_BLOCKER
        from hub.apps.tenants.models import Tenant

        tenant_row = None
        if self.tenant_id:
            try:
                tenant_row = Tenant.objects.only("compliance_intake_gate_enabled").get(
                    pk=self.tenant_id
                )
            except Tenant.DoesNotExist:
                tenant_row = None
        if tenant_row and tenant_row.compliance_intake_gate_enabled:
            if not self.compliance_intake_scan_gate_satisfied():
                blockers.append(COMPLIANCE_INTAKE_ACTIVATION_BLOCKER)

            # Phase 274.2.2 — delegate compliance threshold check to
            # AssetActivationRule.  Only applies to data assets (assets with
            # at least one dataset) because the compliance gate operates on
            # the dataset's data content.  Contract-only assets bypass.
            if self.datasets.exists():
                from hub.apps.assets.business_rules import AssetActivationRule

                rule_result = AssetActivationRule.validate_activation(self)
                if not rule_result["can_activate"]:
                    blockers.append(
                        f"{rule_result['blocker_code']}: "
                        f"{rule_result['details'].get('message', '')}"
                    )

        return len(blockers) == 0, blockers

    def increment_version(self):
        """Increment version for optimistic locking"""
        self.version += 1
        self.save(update_fields=['version', 'updated_at'])

    def is_metadata_only(self):
        """
        Check if asset is metadata-only (no downloaded resources).

        Returns:
            bool: True if asset uses METADATA_ONLY strategy, False otherwise
        """
        return self.data_strategy == DataStrategy.METADATA_ONLY

    def can_download_resource(self, resource_id: str):
        """
        Check if a specific external resource can be downloaded based on data strategy.

        Args:
            resource_id: External resource identifier

        Returns:
            bool: True if resource can be downloaded, False otherwise
        """
        # If metadata-only, cannot download
        if self.data_strategy == DataStrategy.METADATA_ONLY:
            return False

        # If DOWNLOAD_ALL, can download any resource
        if self.data_strategy == DataStrategy.DOWNLOAD_ALL:
            return True

        # If DOWNLOAD_SELECTIVE, check if resource is in download list
        # This would be stored in source_metadata or ExternalResourceReference
        if self.data_strategy == DataStrategy.DOWNLOAD_SELECTIVE:
            # Check if resource exists in external resources
            if self.has_external_resources():
                return self.external_resource_references.filter(
                    resource_id=resource_id
                ).exists()
            return False

        return False

    def get_external_resources(self):
        """
        Get queryset of external resource references for this asset.

        Returns:
            QuerySet of ExternalResourceReference objects
        """
        return self.external_resource_references.all()

    def has_external_resources(self):
        """
        Check if asset has external resource references.

        Returns:
            bool: True if asset has external resources, False otherwise
        """
        return self.external_resource_references.exists()

    def download_external_resource(self, resource_id: str):
        """
        Download a specific external resource on-demand.

        Args:
            resource_id: External resource identifier

        Returns:
            Tuple of (file_path: str, file_content: bytes) or None if not found

        Raises:
            ValidationError: If resource not found or download fails
        """
        try:
            external_resource = self.external_resource_references.get(
                resource_id=resource_id
            )
        except ExternalResourceReference.DoesNotExist:
            raise ValidationError(
                f"External resource '{resource_id}' not found for asset '{self.id}'"
            )

        # Get the marketplace connection
        from hub.apps.integrations.models import MarketplaceConnection
        try:
            connection = MarketplaceConnection.objects.get(
                id=external_resource.connection_id
            )
        except MarketplaceConnection.DoesNotExist:
            raise ValidationError(
                f"Marketplace connection '{external_resource.connection_id}' not found"
            )

        # Use marketplace connector to download the resource
        from hub.apps.integrations.factory import MarketplaceConnectorFactory
        from hub.apps.integrations.base import MarketplaceType

        factory = MarketplaceConnectorFactory()
        marketplace_type_enum = MarketplaceType(connection.marketplace_type)
        connector = factory.create_connector(
            marketplace_type_enum, config=connection.get_config()
        )

        # Download resource
        import tempfile
        import os
        temp_dir = tempfile.gettempdir()
        destination_path = os.path.join(
            temp_dir, f"resource_{resource_id}_{uuid.uuid4().hex[:8]}"
        )

        try:
            downloaded_path = connector.download_resource(
                resource_id=resource_id, destination_path=destination_path
            )

            # Read file content
            with open(downloaded_path, "rb") as f:
                file_content = f.read()

            return downloaded_path, file_content
        except Exception as e:
            raise ValidationError(
                f"Failed to download external resource '{resource_id}': {str(e)}"
            )


class ExternalResourceReference(models.Model):
    """
    External Resource Reference model for storing references to external resources
    from federated assets (marketplaces).

    This model stores metadata about external resources that are referenced but
    not necessarily downloaded. Resources can be downloaded on-demand using the
    download_external_resource() method on the Asset model.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="external_resource_references",
        help_text="Asset this external resource belongs to"
    )
    resource_id = models.CharField(
        max_length=255,
        help_text="External resource identifier from marketplace"
    )
    name = models.CharField(
        max_length=255,
        help_text="Resource name"
    )
    url = models.URLField(
        max_length=2048,
        help_text="External resource URL"
    )
    format = models.CharField(
        max_length=50,
        help_text="Resource format (CSV, JSON, PARQUET, etc.)"
    )
    size_bytes = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Resource size in bytes"
    )
    marketplace_type = models.CharField(
        max_length=50,
        help_text="Marketplace type (e.g., CKAN_INSTANCE, DADOS_GOV_BR)"
    )
    connection_id = models.UUIDField(
        help_text="Reference to MarketplaceConnection used to access this resource"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata about the external resource"
    )
    # Phase 250.5.A.5 (D250.16) — when the federated source is another
    # Hub tenant, ``source_tenant_id`` carries the producer-side
    # ``Tenant.id``. NULL when the source isn't a Hub tenant (e.g.
    # public CKAN catalogs) — the tombstone cascade only fires for
    # rows where this column is populated, so external (non-Hub)
    # federations are unaffected by Hub tenant deletions. The field
    # is a UUID rather than a real FK to avoid blocking source-tenant
    # row deletes during the 90-day grace window.
    source_tenant_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Phase 250.5.A.5 (D250.16) — Hub Tenant.id of the federated "
            "source (NULL when source is non-Hub, e.g. public CKAN). "
            "Drives the source-tenant deletion tombstone cascade."
        ),
    )
    # Phase 250.5.A.5 (D250.16) — populated by the Tenant soft-delete
    # signal (`hub.apps.tenants.signals.tombstone_federated_resources_on_tenant_delete`)
    # when the source tenant is soft-deleted. The consumer-side row
    # remains queryable for 90 days after this timestamp (the grace
    # window per D250.16) so the consumer can export; after the grace
    # expires, a scheduled cleanup task may hard-delete the row.
    source_tenant_deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Phase 250.5.A.5 (D250.16) — set by the Tenant soft-delete "
            "signal when ``source_tenant_id`` matches the deleted "
            "tenant. The consumer-side row stays queryable until "
            "this + 90 days; after that, scheduled cleanup may "
            "hard-delete."
        ),
    )
    # Phase 250.5.F.2 (closes G2-4) — consumer-side soft-deletion
    # timestamp INDEPENDENT of ``source_tenant_deleted_at``. Marks
    # user-initiated deletion of the consumer's federated COPY
    # without affecting the source-tenant row. Distinct semantics:
    #   * source_tenant_deleted_at: source-side cascade signal;
    #     90-day grace window before hard-delete.
    #   * deleted_at: consumer-side delete; row hidden from listing
    #     queries but kept for audit history (no automatic
    #     hard-delete).
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Phase 250.5.F.2 — consumer-side soft-delete timestamp. "
            "Independent of ``source_tenant_deleted_at``. When set, "
            "the federated copy is hidden from consumer-side list "
            "views but kept for audit history."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "external_resource_references"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["asset", "resource_id"]),
            models.Index(fields=["connection_id"]),
            # Phase 250.5.A.5 — supports the cleanup task that scans
            # for rows whose grace window has expired.
            models.Index(
                fields=["source_tenant_deleted_at"],
                name="err_src_deleted_at_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "resource_id"],
                name="unique_external_resource_per_asset"
            )
        ]

    #: Phase 250.5.A.5 (D250.16) — number of days the consumer-side
    #: row remains queryable after ``source_tenant_deleted_at`` is
    #: set. After this window, the row is eligible for cleanup. The
    #: window is intentionally hard-coded (not a setting) because the
    #: spec calls for a uniform 90-day grace across all tenants —
    #: per-tenant overrides would create operator confusion + audit
    #: complexity.
    TOMBSTONE_GRACE_DAYS: int = 90

    def __str__(self):
        return f"{self.name} ({self.resource_id}) - {self.asset.name}"

    @property
    def is_within_tombstone_grace(self) -> bool:
        """True iff the source-tenant tombstone is unset OR was set
        within the last ``TOMBSTONE_GRACE_DAYS`` days. False once the
        grace window has expired (so the cleanup task can hard-delete).
        """
        if self.source_tenant_deleted_at is None:
            return True
        from datetime import timedelta
        from django.utils import timezone

        grace_end = self.source_tenant_deleted_at + timedelta(
            days=self.TOMBSTONE_GRACE_DAYS,
        )
        return timezone.now() < grace_end

    def clean(self):
        """Validate external resource reference"""
        super().clean()

        # Phase 250.5.B.2 (closes Gap 14) — SSRF guard on the
        # external URL BEFORE the row is persisted. The URL is
        # tenant-supplied and may point at loopback / RFC1918 /
        # link-local (169.254.169.254 AWS IMDS) / disallowed
        # schemes (file://, gopher://, ftp://). Rejecting at
        # ``clean()`` time ensures the row never reaches the DB,
        # so a worker that fetches the URL later cannot be
        # tricked into hitting an attacker-controlled internal
        # endpoint. Re-resolution at fetch time
        # (``SSRFGuard.revalidate_resolved_ip``) catches the
        # DNS-rebinding case where the registered hostname's A
        # record gets flipped post-save.
        if self.url:
            from hub.apps.security.url_validators import (
                SSRFGuard,
                SSRFViolationError,
            )
            try:
                SSRFGuard.validate(self.url)
            except SSRFViolationError as exc:
                raise ValidationError(
                    f"External resource URL failed SSRF "
                    f"validation: {exc}"
                )

        # Validate format is one of known formats
        valid_formats = ["CSV", "JSON", "PARQUET", "XML", "XLSX", "PDF", "OTHER"]
        if self.format and self.format.upper() not in valid_formats:
            raise ValidationError(
                f"Invalid format '{self.format}'. "
                f"Valid formats: {', '.join(valid_formats)}"
            )

        # Validate size_bytes is positive if provided
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValidationError("size_bytes must be non-negative")

