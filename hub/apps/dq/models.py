"""
DQ Models

Data Quality Run model for tracking DQ executions, anomalies, and trends.
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError


class DQRunStatus(models.TextChoices):
    """DQ Run status enumeration"""
    PENDING = "PENDING", "Pending"
    RUNNING = "RUNNING", "Running"
    SUCCEEDED = "SUCCEEDED", "Succeeded"
    FAILED = "FAILED", "Failed"


class DQEngine(models.TextChoices):
    """DQ Engine enumeration"""
    GREAT_EXPECTATIONS = "GREAT_EXPECTATIONS", "Great Expectations"
    SODA = "SODA", "Soda"


class DQAnomalySeverity(models.TextChoices):
    """DQ Anomaly severity enumeration"""
    CRITICAL = "CRITICAL", "Critical"
    HIGH = "HIGH", "High"
    MEDIUM = "MEDIUM", "Medium"
    LOW = "LOW", "Low"


class DQTrendDirection(models.TextChoices):
    """DQ Trend direction enumeration"""
    IMPROVING = "IMPROVING", "Improving"
    DEGRADING = "DEGRADING", "Degrading"
    STABLE = "STABLE", "Stable"


class DQRun(models.Model):
    """
    DQ Run model representing a data quality check execution.
    
    Tracks DQ runs for assets, datasets, or files.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="dq_runs",
        help_text="Tenant this DQ run belongs to"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="dq_runs",
        null=True,
        blank=True,
        help_text="Asset this DQ run is for (nullable)"
    )
    dataset = models.ForeignKey(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="dq_runs",
        null=True,
        blank=True,
        help_text="Dataset this DQ run is for (nullable)"
    )
    file = models.ForeignKey(
        "files.File",
        on_delete=models.CASCADE,
        related_name="dq_runs",
        null=True,
        blank=True,
        help_text="File this DQ run is for (scan-only, nullable)"
    )
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.CASCADE,
        related_name="dq_runs",
        help_text="Job that orchestrates this DQ run"
    )
    profile_key = models.CharField(
        max_length=100,
        help_text="DQ profile key (e.g., intake_basic_gx, intake_basic_soda)"
    )
    engine = models.CharField(
        max_length=50,
        choices=DQEngine.choices,
        help_text="DQ engine used: GREAT_EXPECTATIONS or SODA"
    )
    status = models.CharField(
        max_length=20,
        choices=DQRunStatus.choices,
        default=DQRunStatus.PENDING,
        help_text="DQ run status: PENDING, RUNNING, SUCCEEDED, FAILED"
    )
    overall_status = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Overall DQ status: PASS, FAIL, WARN, UNKNOWN (from result)"
    )
    quality_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Quality score (0-100)"
    )
    checks_json = models.JSONField(
        null=True,
        blank=True,
        help_text="List of DQ checks with results"
    )
    details_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Detailed DQ results and metadata"
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When DQ run started"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When DQ run completed"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "dq_runs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "asset"]),
            models.Index(fields=["tenant", "dataset"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "file"]),
            models.Index(fields=["job"]),
        ]
    
    def __str__(self):
        return f"DQ Run {self.id} ({self.profile_key})"
    
    def clean(self):
        """Validate that at least one of asset_id, dataset_id, or file_id is set"""
        super().clean()
        
        if not self.asset and not self.dataset and not self.file:
            raise ValidationError(
                "At least one of asset, dataset, or file must be set"
            )
    
    def save(self, *args, **kwargs):
        """Override save to validate before saving"""
        self.full_clean()
        super().save(*args, **kwargs)


class DQAnomaly(models.Model):
    """
    DQ Anomaly model for tracking detected anomalies in data quality metrics.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="dq_anomalies",
        help_text="Tenant this anomaly belongs to"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="dq_anomalies",
        null=True,
        blank=True,
        help_text="Asset this anomaly is for (nullable)"
    )
    dataset = models.ForeignKey(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="dq_anomalies",
        null=True,
        blank=True,
        help_text="Dataset this anomaly is for (nullable)"
    )
    dq_run = models.ForeignKey(
        DQRun,
        on_delete=models.CASCADE,
        related_name="anomalies",
        null=True,
        blank=True,
        help_text="DQ run that detected this anomaly (nullable)"
    )
    metric_type = models.CharField(
        max_length=100,
        help_text="Type of metric (e.g., quality_score, completeness, accuracy)"
    )
    expected_value = models.FloatField(
        null=True,
        blank=True,
        help_text="Expected value for this metric"
    )
    actual_value = models.FloatField(
        help_text="Actual value that triggered the anomaly"
    )
    deviation = models.FloatField(
        help_text="Deviation from expected value"
    )
    severity = models.CharField(
        max_length=20,
        choices=DQAnomalySeverity.choices,
        default=DQAnomalySeverity.MEDIUM,
        help_text="Anomaly severity: CRITICAL, HIGH, MEDIUM, LOW"
    )
    anomaly_type = models.CharField(
        max_length=50,
        help_text="Type of anomaly (e.g., z_score_outlier, iqr_outlier, sudden_drop)"
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Description of the anomaly"
    )
    metadata = models.JSONField(
        default=dict,
        null=True,
        blank=True,
        help_text="Additional metadata about the anomaly"
    )
    detected_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the anomaly was detected"
    )
    acknowledged = models.BooleanField(
        default=False,
        help_text="Whether the anomaly has been acknowledged"
    )
    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the anomaly was acknowledged"
    )
    acknowledged_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="acknowledged_dq_anomalies",
        null=True,
        blank=True,
        help_text="User who acknowledged the anomaly"
    )
    
    class Meta:
        db_table = "dq_anomalies"
        ordering = ["-detected_at"]
        indexes = [
            models.Index(fields=["tenant", "asset"]),
            models.Index(fields=["tenant", "dataset"]),
            models.Index(fields=["tenant", "severity"]),
            models.Index(fields=["tenant", "metric_type"]),
            models.Index(fields=["tenant", "acknowledged"]),
            models.Index(fields=["detected_at"]),
        ]
    
    def __str__(self):
        return f"DQ Anomaly {self.id} ({self.metric_type}, {self.severity})"


class DQTrend(models.Model):
    """
    DQ Trend model for tracking quality trends over time.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="dq_trends",
        help_text="Tenant this trend belongs to"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="dq_trends",
        null=True,
        blank=True,
        help_text="Asset this trend is for (nullable)"
    )
    dataset = models.ForeignKey(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="dq_trends",
        null=True,
        blank=True,
        help_text="Dataset this trend is for (nullable)"
    )
    metric_type = models.CharField(
        max_length=100,
        help_text="Type of metric (e.g., quality_score, completeness, accuracy)"
    )
    period_start = models.DateTimeField(
        help_text="Start of the trend period"
    )
    period_end = models.DateTimeField(
        help_text="End of the trend period"
    )
    period_type = models.CharField(
        max_length=20,
        help_text="Period type: HOURLY, DAILY, WEEKLY, MONTHLY"
    )
    current_value = models.FloatField(
        help_text="Current value for this metric"
    )
    previous_value = models.FloatField(
        null=True,
        blank=True,
        help_text="Previous value for comparison"
    )
    change_amount = models.FloatField(
        null=True,
        blank=True,
        help_text="Change amount (current - previous)"
    )
    change_percent = models.FloatField(
        null=True,
        blank=True,
        help_text="Percentage change"
    )
    direction = models.CharField(
        max_length=20,
        choices=DQTrendDirection.choices,
        help_text="Trend direction: IMPROVING, DEGRADING, STABLE"
    )
    trend_strength = models.FloatField(
        null=True,
        blank=True,
        help_text="Trend strength (0-1, higher = stronger trend)"
    )
    forecast_value = models.FloatField(
        null=True,
        blank=True,
        help_text="Forecasted value for next period"
    )
    metadata = models.JSONField(
        default=dict,
        null=True,
        blank=True,
        help_text="Additional metadata about the trend"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "dq_trends"
        ordering = ["-period_start"]
        indexes = [
            models.Index(fields=["tenant", "asset"]),
            models.Index(fields=["tenant", "dataset"]),
            models.Index(fields=["tenant", "metric_type"]),
            models.Index(fields=["tenant", "period_type"]),
            models.Index(fields=["period_start", "period_end"]),
            models.Index(fields=["direction"]),
        ]
    
    def __str__(self):
        return f"DQ Trend {self.id} ({self.metric_type}, {self.direction})"


class DQAlertChannel(models.TextChoices):
    """DQ Alert channel enumeration"""
    EMAIL = "EMAIL", "Email"
    SLACK = "SLACK", "Slack"
    WEBHOOK = "WEBHOOK", "Webhook"
    PAGERDUTY = "PAGERDUTY", "PagerDuty"


class DQAlertingRule(models.Model):
    """
    DQ Alerting Rule model for configurable alerting rules.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="dq_alerting_rules",
        help_text="Tenant this rule belongs to"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="dq_alerting_rules",
        null=True,
        blank=True,
        help_text="Asset this rule applies to (nullable for global rules)"
    )
    name = models.CharField(
        max_length=255,
        help_text="Rule name"
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Rule description"
    )
    metric_type = models.CharField(
        max_length=100,
        help_text="Type of metric (e.g., quality_score, completeness, accuracy)"
    )
    threshold = models.FloatField(
        help_text="Threshold value (e.g., quality_score < 0.9)"
    )
    comparison_operator = models.CharField(
        max_length=10,
        choices=[
            ("<", "Less than"),
            ("<=", "Less than or equal"),
            (">", "Greater than"),
            (">=", "Greater than or equal"),
            ("==", "Equal to"),
            ("!=", "Not equal to")
        ],
        default="<",
        help_text="Comparison operator"
    )
    severity = models.CharField(
        max_length=20,
        choices=DQAnomalySeverity.choices,
        default=DQAnomalySeverity.MEDIUM,
        help_text="Alert severity: CRITICAL, HIGH, MEDIUM, LOW"
    )
    alert_channels = models.JSONField(
        default=list,
        help_text="List of alert channels (EMAIL, SLACK, WEBHOOK, PAGERDUTY)"
    )
    channel_config = models.JSONField(
        default=dict,
        null=True,
        blank=True,
        help_text="Channel-specific configuration (e.g., email addresses, webhook URLs)"
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Whether the rule is enabled"
    )
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="created_dq_alerting_rules",
        null=True,
        blank=True,
        help_text="User who created the rule"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "dq_alerting_rules"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "asset"]),
            models.Index(fields=["tenant", "enabled"]),
            models.Index(fields=["tenant", "metric_type"]),
            models.Index(fields=["tenant", "severity"]),
        ]
    
    def __str__(self):
        return f"DQ Alerting Rule {self.name} ({self.metric_type})"
    
    def clean(self):
        """Validate rule configuration"""
        super().clean()
        
        if not self.alert_channels:
            raise ValidationError("At least one alert channel must be specified")
        
        # Validate channel config
        if self.channel_config:
            for channel in self.alert_channels:
                if channel == "EMAIL" and "emails" not in self.channel_config:
                    raise ValidationError("EMAIL channel requires 'emails' in channel_config")
                elif channel == "WEBHOOK" and "url" not in self.channel_config:
                    raise ValidationError("WEBHOOK channel requires 'url' in channel_config")
    
    def save(self, *args, **kwargs):
        """Override save to validate before saving"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def evaluate(self, metric_value: float) -> bool:
        """
        Evaluate if the rule condition is met.
        
        Args:
            metric_value: Current metric value
        
        Returns:
            True if condition is met (alert should fire), False otherwise
        """
        if not self.enabled:
            return False
        
        if self.comparison_operator == "<":
            return metric_value < self.threshold
        elif self.comparison_operator == "<=":
            return metric_value <= self.threshold
        elif self.comparison_operator == ">":
            return metric_value > self.threshold
        elif self.comparison_operator == ">=":
            return metric_value >= self.threshold
        elif self.comparison_operator == "==":
            return abs(metric_value - self.threshold) < 0.0001  # Float comparison
        elif self.comparison_operator == "!=":
            return abs(metric_value - self.threshold) >= 0.0001
        else:
            return False
