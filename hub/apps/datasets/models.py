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
        on_delete=models.CASCADE,
        related_name="datasets",
        help_text="File this dataset is based on"
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
    format = models.CharField(
        max_length=20,
        help_text="File format: CSV, JSON, PARQUET"
    )
    version = models.IntegerField(
        default=1,
        help_text="Dataset version (per-asset version counter)"
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
    
    class Meta:
        db_table = "datasets"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "asset"]),
            models.Index(fields=["tenant", "file"]),
            models.Index(fields=["tenant", "format"]),
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
        return f"{asset_name} - {self.file.name} (v{self.version}, {self.format})"

