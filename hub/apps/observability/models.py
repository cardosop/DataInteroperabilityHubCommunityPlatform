"""
Observability Models

Models for data freshness monitoring, volume monitoring, and schema drift detection.
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class FreshnessSLA(models.TextChoices):
    """Freshness SLA levels"""
    REAL_TIME = "REAL_TIME", "Real-time (< 1 minute)"
    NEAR_REAL_TIME = "NEAR_REAL_TIME", "Near Real-time (< 5 minutes)"
    HOURLY = "HOURLY", "Hourly (< 1 hour)"
    DAILY = "DAILY", "Daily (< 24 hours)"
    WEEKLY = "WEEKLY", "Weekly (< 7 days)"
    MONTHLY = "MONTHLY", "Monthly (< 30 days)"
    ON_DEMAND = "ON_DEMAND", "On-demand (no SLA)"


class DataObservabilityMetric(models.Model):
    """
    Data observability metrics for datasets and assets.
    
    Tracks freshness, volume, and schema information over time.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="observability_metrics",
        help_text="Tenant this metric belongs to"
    )
    # Resource reference
    dataset = models.ForeignKey(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="observability_metrics",
        null=True,
        blank=True,
        help_text="Dataset this metric is for"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="observability_metrics",
        null=True,
        blank=True,
        help_text="Asset this metric is for"
    )
    # Freshness metrics
    last_update_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time the data was updated"
    )
    freshness_age_seconds = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Age of data in seconds (time since last update)"
    )
    freshness_sla = models.CharField(
        max_length=50,
        choices=FreshnessSLA.choices,
        null=True,
        blank=True,
        help_text="Freshness SLA requirement"
    )
    freshness_sla_seconds = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Freshness SLA in seconds"
    )
    is_stale = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether data is stale (exceeds SLA)"
    )
    # Volume metrics
    row_count = models.BigIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Number of rows in the dataset"
    )
    size_bytes = models.BigIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Size of dataset in bytes"
    )
    # Schema information
    schema_hash = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="SHA-256 hash of schema for drift detection"
    )
    schema_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Schema JSON snapshot for comparison"
    )
    # Metadata
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When this metric was recorded"
    )
    
    class Meta:
        db_table = "data_observability_metrics"
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["tenant", "dataset", "recorded_at"]),
            models.Index(fields=["tenant", "asset", "recorded_at"]),
            models.Index(fields=["tenant", "is_stale", "recorded_at"]),
            models.Index(fields=["recorded_at"]),
        ]
    
    def __str__(self):
        resource = f"Dataset {self.dataset_id}" if self.dataset else f"Asset {self.asset_id}"
        return f"{resource} - {self.recorded_at}"


class VolumeTrend(models.Model):
    """
    Aggregated volume trends for hourly and daily analysis.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="volume_trends",
        help_text="Tenant this trend belongs to"
    )
    dataset = models.ForeignKey(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="volume_trends",
        null=True,
        blank=True,
        help_text="Dataset this trend is for"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="volume_trends",
        null=True,
        blank=True,
        help_text="Asset this trend is for"
    )
    # Aggregation period
    period_start = models.DateTimeField(
        db_index=True,
        help_text="Start of aggregation period"
    )
    period_end = models.DateTimeField(
        db_index=True,
        help_text="End of aggregation period"
    )
    period_type = models.CharField(
        max_length=20,
        choices=[
            ("HOURLY", "Hourly"),
            ("DAILY", "Daily"),
        ],
        help_text="Type of aggregation period"
    )
    # Aggregated metrics
    avg_row_count = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Average row count during period"
    )
    min_row_count = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Minimum row count during period"
    )
    max_row_count = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Maximum row count during period"
    )
    avg_size_bytes = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Average size in bytes during period"
    )
    min_size_bytes = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Minimum size in bytes during period"
    )
    max_size_bytes = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Maximum size in bytes during period"
    )
    sample_count = models.IntegerField(
        default=0,
        help_text="Number of samples in this period"
    )
    # Anomaly detection
    is_anomaly = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this period contains anomalies"
    )
    anomaly_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Type of anomaly detected (SPIKE, DROP, UNUSUAL_PATTERN)"
    )
    anomaly_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Anomaly score (0.0 to 1.0)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "volume_trends"
        ordering = ["-period_start"]
        indexes = [
            models.Index(fields=["tenant", "dataset", "period_type", "period_start"]),
            models.Index(fields=["tenant", "asset", "period_type", "period_start"]),
            models.Index(fields=["tenant", "is_anomaly", "period_start"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "dataset", "period_type", "period_start"],
                condition=models.Q(dataset__isnull=False),
                name="unique_volume_trend_dataset"
            ),
            models.UniqueConstraint(
                fields=["tenant", "asset", "period_type", "period_start"],
                condition=models.Q(asset__isnull=False),
                name="unique_volume_trend_asset"
            ),
        ]
    
    def __str__(self):
        resource = f"Dataset {self.dataset_id}" if self.dataset else f"Asset {self.asset_id}"
        return f"{resource} - {self.period_type} - {self.period_start}"


class SchemaDrift(models.Model):
    """
    Schema drift detection records.
    
    Tracks schema changes over time including new fields, removed fields, and type changes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="schema_drifts",
        help_text="Tenant this drift record belongs to"
    )
    dataset = models.ForeignKey(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="schema_drifts",
        null=True,
        blank=True,
        help_text="Dataset this drift is for"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="schema_drifts",
        null=True,
        blank=True,
        help_text="Asset this drift is for"
    )
    # Schema comparison
    previous_schema_hash = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Hash of previous schema"
    )
    current_schema_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Hash of current schema"
    )
    previous_schema_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Previous schema JSON"
    )
    current_schema_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Current schema JSON"
    )
    # Drift details
    new_fields = models.JSONField(
        default=list,
        null=True,
        blank=True,
        help_text="List of new fields added"
    )
    removed_fields = models.JSONField(
        default=list,
        null=True,
        blank=True,
        help_text="List of fields removed"
    )
    type_changes = models.JSONField(
        default=list,
        null=True,
        blank=True,
        help_text="List of type changes (field_name, old_type, new_type)"
    )
    nullable_changes = models.JSONField(
        default=list,
        null=True,
        blank=True,
        help_text="List of nullable changes (field_name, old_nullable, new_nullable)"
    )
    # Drift severity
    drift_severity = models.CharField(
        max_length=20,
        choices=[
            ("BREAKING", "Breaking Change"),
            ("NON_BREAKING", "Non-Breaking Change"),
            ("MINOR", "Minor Change"),
        ],
        default="MINOR",
        help_text="Severity of schema drift"
    )
    # Tolerance configuration
    tolerance_config = models.JSONField(
        default=dict,
        null=True,
        blank=True,
        help_text="Tolerance configuration used for drift detection"
    )
    is_within_tolerance = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether drift is within configured tolerance"
    )
    # Metadata
    detected_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When this drift was detected"
    )
    
    class Meta:
        db_table = "schema_drifts"
        ordering = ["-detected_at"]
        indexes = [
            models.Index(fields=["tenant", "dataset", "detected_at"]),
            models.Index(fields=["tenant", "asset", "detected_at"]),
            models.Index(fields=["tenant", "drift_severity", "detected_at"]),
            models.Index(fields=["tenant", "is_within_tolerance", "detected_at"]),
        ]
    
    def __str__(self):
        resource = f"Dataset {self.dataset_id}" if self.dataset else f"Asset {self.asset_id}"
        return f"{resource} - {self.drift_severity} - {self.detected_at}"


class PipelineExecution(models.Model):
    """
    Pipeline execution tracking for ingestion and transformation pipelines.
    
    Tracks execution times, success rates, error rates, latency, and throughput.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="pipeline_executions",
        help_text="Tenant this execution belongs to"
    )
    # Pipeline identification
    pipeline_type = models.CharField(
        max_length=50,
        choices=[
            ("SCHEDULED_INGESTION", "Scheduled Ingestion"),
            ("DQ_RUN", "Data Quality Run"),
            ("COMPLIANCE_RUN", "Compliance Run"),
            ("CONTRACT_VALIDATION", "Contract Validation"),
            ("SEMANTIC_MAPPING", "Semantic Mapping"),
            ("TRANSFORMATION", "Transformation"),
        ],
        db_index=True,
        help_text="Type of pipeline"
    )
    pipeline_id = models.UUIDField(
        db_index=True,
        help_text="ID of the pipeline (scheduled_ingestion_id, job_id, etc.)"
    )
    pipeline_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Name of the pipeline"
    )
    # Execution tracking
    status = models.CharField(
        max_length=20,
        choices=[
            ("PENDING", "Pending"),
            ("RUNNING", "Running"),
            ("COMPLETED", "Completed"),
            ("FAILED", "Failed"),
            ("CANCELLED", "Cancelled"),
        ],
        db_index=True,
        help_text="Execution status"
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When execution started"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When execution completed"
    )
    execution_time_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text="Execution time in seconds"
    )
    # Performance metrics
    latency_ms = models.FloatField(
        null=True,
        blank=True,
        help_text="Latency in milliseconds"
    )
    throughput_items_per_second = models.FloatField(
        null=True,
        blank=True,
        help_text="Throughput (items processed per second)"
    )
    items_processed = models.IntegerField(
        default=0,
        help_text="Number of items processed"
    )
    items_failed = models.IntegerField(
        default=0,
        help_text="Number of items that failed"
    )
    # Error tracking
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if execution failed"
    )
    error_code = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text="Error code for categorization"
    )
    # Resource reference
    resource_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Resource type: DATASET, ASSET, CONTRACT, etc."
    )
    resource_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of the resource"
    )
    # Metadata
    result_json = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text="Execution result data"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "pipeline_executions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "pipeline_type", "status"]),
            models.Index(fields=["tenant", "pipeline_type", "created_at"]),
            models.Index(fields=["pipeline_id", "status"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["resource_type", "resource_id"]),
        ]
    
    def __str__(self):
        return f"{self.pipeline_type} - {self.status} - {self.created_at}"


class DataSLA(models.Model):
    """
    Data SLA definitions for availability, freshness, and quality.
    
    Defines SLAs per asset/dataset and tracks compliance.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="data_slas",
        help_text="Tenant this SLA belongs to"
    )
    # Resource reference
    dataset = models.ForeignKey(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="data_slas",
        null=True,
        blank=True,
        help_text="Dataset this SLA is for"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="data_slas",
        null=True,
        blank=True,
        help_text="Asset this SLA is for"
    )
    # SLA definition
    name = models.CharField(
        max_length=255,
        help_text="SLA name"
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="SLA description"
    )
    sla_type = models.CharField(
        max_length=50,
        choices=[
            ("AVAILABILITY", "Availability"),
            ("FRESHNESS", "Freshness"),
            ("QUALITY", "Quality"),
        ],
        db_index=True,
        help_text="Type of SLA"
    )
    # Availability SLA
    availability_target_percent = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Availability target percentage (e.g., 99.9)"
    )
    # Freshness SLA
    freshness_sla_seconds = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Freshness SLA in seconds (maximum age of data)"
    )
    # Quality SLA
    quality_target_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Quality target score (0.0 to 1.0)"
    )
    # Compliance tracking
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether SLA is active"
    )
    current_compliance_percent = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Current compliance percentage"
    )
    last_compliance_check = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time compliance was checked"
    )
    is_violated = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether SLA is currently violated"
    )
    violation_count = models.IntegerField(
        default=0,
        help_text="Number of times SLA has been violated"
    )
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_slas",
        null=True,
        blank=True,
        help_text="User who created the SLA"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "data_slas"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "sla_type", "is_active"]),
            models.Index(fields=["tenant", "dataset", "sla_type"]),
            models.Index(fields=["tenant", "asset", "sla_type"]),
            models.Index(fields=["tenant", "is_violated", "is_active"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    models.Q(sla_type="AVAILABILITY", availability_target_percent__isnull=False) |
                    models.Q(sla_type="FRESHNESS", freshness_sla_seconds__isnull=False) |
                    models.Q(sla_type="QUALITY", quality_target_score__isnull=False)
                ),
                name="sla_has_appropriate_target"
            ),
        ]
    
    def __str__(self):
        resource = f"Dataset {self.dataset_id}" if self.dataset else f"Asset {self.asset_id}"
        return f"{resource} - {self.sla_type} - {self.name}"


class DataIncident(models.Model):
    """
    Data incident management for tracking and resolving data issues.
    
    Tracks incidents through lifecycle: DETECTED → TRIAGED → IN_PROGRESS → RESOLVED
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="data_incidents",
        help_text="Tenant this incident belongs to"
    )
    # Incident identification
    title = models.CharField(
        max_length=255,
        help_text="Incident title"
    )
    description = models.TextField(
        help_text="Incident description"
    )
    incident_type = models.CharField(
        max_length=50,
        choices=[
            ("FRESHNESS_VIOLATION", "Freshness Violation"),
            ("QUALITY_VIOLATION", "Quality Violation"),
            ("AVAILABILITY_VIOLATION", "Availability Violation"),
            ("SCHEMA_DRIFT", "Schema Drift"),
            ("PIPELINE_FAILURE", "Pipeline Failure"),
            ("DATA_LOSS", "Data Loss"),
            ("COMPLIANCE_VIOLATION", "Compliance Violation"),
            ("OTHER", "Other"),
        ],
        db_index=True,
        help_text="Type of incident"
    )
    severity = models.CharField(
        max_length=20,
        choices=[
            ("CRITICAL", "Critical"),
            ("HIGH", "High"),
            ("MEDIUM", "Medium"),
            ("LOW", "Low"),
        ],
        default="MEDIUM",
        db_index=True,
        help_text="Incident severity"
    )
    # Lifecycle tracking
    status = models.CharField(
        max_length=20,
        choices=[
            ("DETECTED", "Detected"),
            ("TRIAGED", "Triaged"),
            ("IN_PROGRESS", "In Progress"),
            ("RESOLVED", "Resolved"),
        ],
        default="DETECTED",
        db_index=True,
        help_text="Incident status"
    )
    detected_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When incident was detected"
    )
    triaged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When incident was triaged"
    )
    in_progress_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When incident was marked as in progress"
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When incident was resolved"
    )
    resolution_time_seconds = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Time to resolve in seconds"
    )
    # Assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_incidents",
        null=True,
        blank=True,
        help_text="User assigned to resolve the incident"
    )
    detected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="detected_incidents",
        null=True,
        blank=True,
        help_text="User or system that detected the incident"
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="resolved_incidents",
        null=True,
        blank=True,
        help_text="User who resolved the incident"
    )
    # Resource reference
    resource_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Resource type: DATASET, ASSET, CONTRACT, PIPELINE, etc."
    )
    resource_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of the resource"
    )
    # Incident details
    root_cause = models.TextField(
        null=True,
        blank=True,
        help_text="Root cause analysis"
    )
    resolution_notes = models.TextField(
        null=True,
        blank=True,
        help_text="Resolution notes"
    )
    metadata_json = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text="Additional incident metadata"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "data_incidents"
        ordering = ["-detected_at"]
        indexes = [
            models.Index(fields=["tenant", "status", "severity"]),
            models.Index(fields=["tenant", "incident_type", "status"]),
            models.Index(fields=["tenant", "assigned_to", "status"]),
            models.Index(fields=["status", "detected_at"]),
            models.Index(fields=["resource_type", "resource_id"]),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.status} - {self.detected_at}"

