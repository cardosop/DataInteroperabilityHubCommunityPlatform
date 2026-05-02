"""
Assets Models

Asset model for managing data products (contract + dataset).
"""
import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex


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


class AssetSourceType(models.TextChoices):
    """Asset source type enumeration"""
    HUB_NATIVE = "HUB_NATIVE", "Hub Native"
    FEDERATED = "FEDERATED", "Federated"


class DataStrategy(models.TextChoices):
    """Data strategy enumeration for federated assets"""
    METADATA_ONLY = "METADATA_ONLY", "Metadata Only"
    DOWNLOAD_SELECTIVE = "DOWNLOAD_SELECTIVE", "Selective Download"
    DOWNLOAD_ALL = "DOWNLOAD_ALL", "Download All"


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
    visibility = models.CharField(
        max_length=20,
        choices=AssetVisibility.choices,
        default=AssetVisibility.INTERNAL,
        help_text="Asset visibility: INTERNAL, PUBLIC"
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
    data_strategy = models.CharField(
        max_length=20,
        choices=DataStrategy.choices,
        default=DataStrategy.METADATA_ONLY,
        help_text="Data strategy for federated assets: METADATA_ONLY (store references only), DOWNLOAD_SELECTIVE (download specific resources), DOWNLOAD_ALL (download all resources)"
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
            models.Index(fields=["tenant", "visibility"]),
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
            from hub.apps.contracts.structural_floor import (
                collect_structural_floor_errors,
            )
            floor_errors = collect_structural_floor_errors(
                active_contract.hub_contract_json,
                spec_type=active_contract.original_spec_type,
                spec_version=active_contract.original_spec_version,
                contract_id=str(active_contract.id),
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "external_resource_references"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["asset", "resource_id"]),
            models.Index(fields=["connection_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "resource_id"],
                name="unique_external_resource_per_asset"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.resource_id}) - {self.asset.name}"

    def clean(self):
        """Validate external resource reference"""
        super().clean()

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

