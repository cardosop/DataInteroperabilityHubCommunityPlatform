"""
Dataset Models

Dataset model for managing data files with inferred schema and sample data.
"""
import uuid
from django.db import models
from django.conf import settings


class DatasetKind(models.TextChoices):
    """Dataset kind enumeration"""
    FILE = "FILE", "File-based dataset"
    EXTERNAL_REF = "EXTERNAL_REF", "External reference dataset"


class DatasetStatus(models.TextChoices):
    """Dataset lifecycle status"""
    ACTIVE = "ACTIVE", "Active"
    RETIRED = "RETIRED", "Retired"
    DRAFT = "DRAFT", "Draft"
    PROCESSING = "PROCESSING", "Processing"


class DatasetFileHandlePurpose(models.TextChoices):
    """Purpose discriminator for (tenant, file) unique-when-primary constraint."""
    PRIMARY = "PRIMARY", "Primary"
    SAMPLE = "SAMPLE", "Sample"
    SCHEMA_ONLY = "SCHEMA_ONLY", "Schema Only"


class Dataset(models.Model):
    """
    Dataset model representing a data file with inferred schema.
    
    A dataset is linked to an asset and a file, and contains:
    - Inferred schema (field names, types, nullable flags)
    - Sample data (first 100 rows)
    - Row count
    - Format information
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="datasets",
        help_text="Tenant this dataset belongs to"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="datasets",
        null=True,
        blank=True,
        help_text="Asset this dataset belongs to (nullable for MVP)"
    )
    file = models.ForeignKey(
        "files.File",
        on_delete=models.SET_NULL,
        related_name="datasets",
        null=True,
        blank=True,
        help_text="File this dataset is based on (nullable; SET_NULL preserves dataset on file deletion)"
    )
    schema_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Inferred schema as JSON (fields, types, nullable flags, etc.)"
    )
    sample_data_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Sample data (first 100 rows) as JSON array"
    )
    row_count = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Total number of rows in the dataset"
    )
    status = models.CharField(
        max_length=20,
        choices=DatasetStatus.choices,
        default=DatasetStatus.ACTIVE,
        help_text="Dataset lifecycle status"
    )
    kind = models.CharField(
        max_length=20,
        choices=DatasetKind.choices,
        default=DatasetKind.FILE,
        db_index=True,
        help_text="Dataset kind: FILE or EXTERNAL_REF"
    )
    file_handle_purpose = models.CharField(
        max_length=50,
        choices=DatasetFileHandlePurpose.choices,
        default=DatasetFileHandlePurpose.PRIMARY,
        help_text="Purpose for which the file handle was stored (e.g. original, processed, sample)"
    )
    retired_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the dataset was retired"
    )
    format = models.CharField(
        max_length=20,
        help_text="File format: CSV, JSON, PARQUET"
    )
    version = models.IntegerField(
        default=1,
        help_text="Dataset version (per-asset version counter)"
    )
    # Version history fields
    parent_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='child_versions',
        null=True,
        blank=True,
        help_text="Parent version in version tree"
    )
    version_hash = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="SHA-256 hash of schema and file content for version identification"
    )
    snapshot_metadata = models.JSONField(
        default=dict,
        null=True,
        blank=True,
        help_text="Additional metadata for version snapshot"
    )
    is_current = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this is the current version for the asset"
    )
    archived_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp when version was archived"
    )
    semantic_version = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True,
        help_text="Semantic version string (e.g., '1.0.0')"
    )
    version_tags = models.JSONField(
        default=list,
        null=True,
        blank=True,
        help_text="Version tags (e.g., ['production', 'staging'])"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_datasets",
        null=True,
        blank=True,
        help_text="User who created the dataset"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Phase 230.8.9 (REQ-SEM-FED-002) — per-resource federation
    # opt-out.  When True, this dataset's triples are excluded from
    # incoming federated SERVICE responses.
    semantic_federate_optout = models.BooleanField(
        default=False,
        help_text=(
            "When True, this resource's triples are NOT exposed to "
            "external federated SERVICE queries (REQ-SEM-FED-002)."
        ),
    )

    class Meta:
        db_table = "datasets"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "asset"]),
            models.Index(fields=["tenant", "file"]),
            models.Index(fields=["tenant", "format"]),
            # Version history indexes
            models.Index(fields=["tenant", "asset", "is_current"]),
            models.Index(fields=["tenant", "asset", "semantic_version"]),
            models.Index(fields=["tenant", "asset", "parent_version"]),
            models.Index(fields=["tenant", "asset", "archived_at"]),
            models.Index(fields=["version_hash"]),
        ]
        # Unique constraint on (tenant, asset, version) if asset is provided
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "asset", "version"],
                condition=models.Q(asset__isnull=False),
                name="unique_dataset_version_per_asset"
            )
        ]
    
    def __str__(self):
        asset_name = self.asset.name if self.asset else "No Asset"
        file_name = self.file.name if self.file else "No file"
        return f"{asset_name} - {file_name} (v{self.version}, {self.format})"


class SchemaVersion(models.Model):
    """
    Tracks schema evolution for dataset versions.
    
    Stores schema snapshots and change logs for each dataset version.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.OneToOneField(
        Dataset,
        on_delete=models.CASCADE,
        related_name='schema_version',
        help_text="Dataset version this schema belongs to"
    )
    parent_schema_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='child_schema_versions',
        null=True,
        blank=True,
        help_text="Parent schema version in evolution chain"
    )
    schema_json = models.JSONField(
        help_text="Complete schema JSON snapshot"
    )
    status = models.CharField(
        max_length=20, default="ACTIVE",
        help_text="Schema version status"
    )
    compatibility_level = models.CharField(
        max_length=20,
        help_text="Compatibility level: FULLY_COMPATIBLE, BACKWARD_COMPATIBLE, FORWARD_COMPATIBLE, INCOMPATIBLE"
    )
    change_summary = models.JSONField(
        default=dict,
        help_text="Summary of changes (counts by change type)"
    )
    change_log = models.JSONField(
        default=dict,
        help_text="Complete change log with all changes"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "schema_versions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["dataset"]),
            models.Index(fields=["parent_schema_version"]),
            models.Index(fields=["compatibility_level"]),
        ]
    
    def __str__(self):
        return f"SchemaVersion for {self.dataset} ({self.compatibility_level})"


class SnapshotType(models.TextChoices):
    """Snapshot type enumeration for time-travel queries."""
    FULL = "FULL", "Full"
    SCHEMA_ONLY = "SCHEMA_ONLY", "Schema Only"
    METADATA_ONLY = "METADATA_ONLY", "Metadata Only"
    INCREMENTAL = "INCREMENTAL", "Incremental (post-MVP placeholder)"


class DatasetSnapshot(models.Model):
    """
    Optional snapshot storage for time-travel queries.
    
    Stores complete dataset snapshots for point-in-time recovery.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(
        Dataset,
        on_delete=models.CASCADE,
        related_name='snapshots',
        help_text="Dataset version this snapshot belongs to"
    )
    snapshot_data = models.JSONField(
        help_text="Complete dataset snapshot (schema, sample data, metadata)"
    )
    snapshot_type = models.CharField(
        max_length=20,
        choices=SnapshotType.choices,
        default=SnapshotType.FULL,
        help_text="Snapshot type: FULL, SCHEMA_ONLY, METADATA_ONLY"
    )
    status = models.CharField(
        max_length=20, default="ACTIVE",
        help_text="Snapshot status: ACTIVE, ARCHIVED, EXPIRED"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "dataset_snapshots"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["dataset", "created_at"]),
            models.Index(fields=["snapshot_type"]),
        ]
    
    def __str__(self):
        return f"Snapshot for {self.dataset} ({self.snapshot_type})"
