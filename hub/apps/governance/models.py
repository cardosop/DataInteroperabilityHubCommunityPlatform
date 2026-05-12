"""
Governance Models

Models for data classification, retention policies, access request workflows,
compliance reporting, and ABAC policies.
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError


class ClassificationCategory(models.TextChoices):
    """Data classification categories"""
    PUBLIC = "PUBLIC", "Public"
    INTERNAL = "INTERNAL", "Internal"
    CONFIDENTIAL = "CONFIDENTIAL", "Confidential"
    RESTRICTED = "RESTRICTED", "Restricted"
    PII = "PII", "Personally Identifiable Information"
    PHI = "PHI", "Protected Health Information"
    PCI = "PCI", "Payment Card Information"
    FINANCIAL = "FINANCIAL", "Financial Information"
    LEGAL = "LEGAL", "Legal Information"


class ClassificationStatus(models.TextChoices):
    """Classification status"""
    PENDING = "PENDING", "Pending"
    AUTO_CLASSIFIED = "AUTO_CLASSIFIED", "Auto-Classified"
    MANUAL_REVIEW = "MANUAL_REVIEW", "Manual Review"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


class DataClassification(models.Model):
    """
    Data classification for fields, datasets, and assets.
    
    Tracks automatic and manual classifications with confidence scores.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="data_classifications",
        help_text="Tenant this classification belongs to"
    )
    # Polymorphic resource reference
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="classifications",
        null=True,
        blank=True,
        help_text="Asset this classification is for (nullable)"
    )
    dataset = models.ForeignKey(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="classifications",
        null=True,
        blank=True,
        help_text="Dataset this classification is for (nullable)"
    )
    field_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Field name for field-level classification (nullable)"
    )
    category = models.CharField(
        max_length=50,
        choices=ClassificationCategory.choices,
        help_text="Classification category"
    )
    status = models.CharField(
        max_length=20,
        choices=ClassificationStatus.choices,
        default=ClassificationStatus.AUTO_CLASSIFIED,
        help_text="Classification status"
    )
    confidence_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Confidence score (0.0-1.0) for automatic classification"
    )
    classification_rules = models.JSONField(
        default=list,
        null=True,
        blank=True,
        help_text="Rules that matched for this classification"
    )
    detected_patterns = models.JSONField(
        default=list,
        null=True,
        blank=True,
        help_text="Detected patterns (PII types, keywords, etc.)"
    )
    manual_review_notes = models.TextField(
        null=True,
        blank=True,
        help_text="Notes from manual review"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_classifications",
        null=True,
        blank=True,
        help_text="User who reviewed this classification"
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When classification was reviewed"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_classifications",
        null=True,
        blank=True,
        help_text="User who created this classification"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "data_classifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "asset"]),
            models.Index(fields=["tenant", "dataset"]),
            models.Index(fields=["tenant", "category"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "asset", "field_name"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "asset", "field_name"],
                condition=models.Q(asset__isnull=False, field_name__isnull=False),
                name="unique_field_classification"
            ),
            models.UniqueConstraint(
                fields=["tenant", "dataset", "field_name"],
                condition=models.Q(dataset__isnull=False, field_name__isnull=False),
                name="unique_dataset_field_classification"
            ),
        ]
    
    def __str__(self):
        resource = self.asset or self.dataset
        field_part = f" - {self.field_name}" if self.field_name else ""
        return f"{resource}{field_part} - {self.category}"
    
    def clean(self):
        """Validate that at least one of asset or dataset is set"""
        super().clean()
        
        if not self.asset and not self.dataset:
            raise ValidationError(
                "At least one of asset or dataset must be set"
            )
    
    def save(self, *args, **kwargs):
        """Override save to validate before saving"""
        self.full_clean()
        super().save(*args, **kwargs)


class RetentionPolicyType(models.TextChoices):
    """Retention policy types"""
    TIME_BASED = "TIME_BASED", "Time-Based"
    EVENT_BASED = "EVENT_BASED", "Event-Based"


class RetentionAction(models.TextChoices):
    """Retention actions"""
    SOFT_DELETE = "SOFT_DELETE", "Soft Delete"
    HARD_DELETE = "HARD_DELETE", "Hard Delete"
    ARCHIVE = "ARCHIVE", "Archive"


class RetentionPolicy(models.Model):
    """
    Retention policy for assets, datasets, or files.
    
    Supports time-based and event-based retention with legal hold support.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="retention_policies",
        help_text="Tenant this retention policy belongs to"
    )
    name = models.CharField(
        max_length=255,
        help_text="Policy name"
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Policy description"
    )
    # Polymorphic resource reference
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="retention_policies",
        null=True,
        blank=True,
        help_text="Asset this policy applies to (nullable)"
    )
    dataset = models.ForeignKey(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="retention_policies",
        null=True,
        blank=True,
        help_text="Dataset this policy applies to (nullable)"
    )
    file = models.ForeignKey(
        "files.File",
        on_delete=models.CASCADE,
        related_name="retention_policies",
        null=True,
        blank=True,
        help_text="File this policy applies to (nullable)"
    )
    policy_type = models.CharField(
        max_length=20,
        choices=RetentionPolicyType.choices,
        help_text="Policy type: TIME_BASED or EVENT_BASED"
    )
    # Time-based retention
    retention_period_days = models.IntegerField(
        null=True,
        blank=True,
        help_text="Retention period in days (for time-based policies)"
    )
    # Event-based retention
    event_trigger = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Event trigger (e.g., 'contract_expired', 'project_completed')"
    )
    action = models.CharField(
        max_length=20,
        choices=RetentionAction.choices,
        default=RetentionAction.SOFT_DELETE,
        help_text="Action to take when retention period expires"
    )
    grace_period_days = models.IntegerField(
        default=30,
        help_text="Grace period in days before hard delete (for soft delete)"
    )
    legal_hold = models.BooleanField(
        default=False,
        help_text="Whether data is under legal hold (prevents deletion)"
    )
    legal_hold_reason = models.TextField(
        null=True,
        blank=True,
        help_text="Reason for legal hold"
    )
    legal_hold_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When legal hold expires (nullable for indefinite hold)"
    )
    regulation_keys = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Regime keys (uppercase strings) attached to TIME_BASED policies; "
            "when non-empty they drive retention_period_days automatically."
        ),
    )
    tombstoned_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="UTC timestamp when the Phase 232.7 auto-sweep first soft-deleted the resource.",
    )
    hard_delete_scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="UTC deadline after tombstone grace (90 calendar days by default auto-sweep).",
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Whether policy is enabled"
    )
    last_enforced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When policy was last enforced"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_retention_policies",
        null=True,
        blank=True,
        help_text="User who created this policy"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "retention_policies"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "asset"]),
            models.Index(fields=["tenant", "dataset"]),
            models.Index(fields=["tenant", "file"]),
            models.Index(fields=["tenant", "enabled"]),
            models.Index(fields=["tenant", "legal_hold"]),
            models.Index(fields=["legal_hold_expires_at"]),
            models.Index(fields=["tenant", "tombstoned_at"]),
        ]
    
    def __str__(self):
        resource = self.asset or self.dataset or self.file
        return f"{self.name} - {resource}"
    
    def clean(self):
        """Validate policy configuration"""
        super().clean()
        
        if not self.asset and not self.dataset and not self.file:
            raise ValidationError(
                "At least one of asset, dataset, or file must be set"
            )
        
        if self.policy_type == RetentionPolicyType.TIME_BASED.value:
            rk = list(self.regulation_keys or [])
            if rk:
                from hub.apps.regulation_policies.registry import data_retention_period_days_for_regime_keys

                derived_days = data_retention_period_days_for_regime_keys(rk)
                if derived_days > 0:
                    self.retention_period_days = derived_days
            if not self.retention_period_days:
                raise ValidationError(
                    "retention_period_days is required for time-based policies (or supply regulation_keys)"
                )
        elif self.policy_type == RetentionPolicyType.EVENT_BASED.value:
            if not self.event_trigger:
                raise ValidationError(
                    "event_trigger is required for event-based policies"
                )
    
    def save(self, *args, **kwargs):
        """Override save to validate before saving"""
        self.full_clean()
        super().save(*args, **kwargs)


class AccessRequestStatus(models.TextChoices):
    """Access request status"""
    PENDING = "PENDING", "Pending"
    PENDING_NEXT_APPROVER = "PENDING_NEXT_APPROVER", "Pending Next Approver"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    EXPIRED = "EXPIRED", "Expired"
    REVOKED = "REVOKED", "Revoked"


class AccessRequest(models.Model):
    """
    Access request for assets, datasets, or files.
    
    Supports single-step and multi-step approval workflows.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="access_requests",
        help_text="Tenant this access request belongs to"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="requested_access",
        help_text="User requesting access"
    )
    # Polymorphic resource reference
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="access_requests",
        null=True,
        blank=True,
        help_text="Asset access is requested for (nullable)"
    )
    dataset = models.ForeignKey(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="access_requests",
        null=True,
        blank=True,
        help_text="Dataset access is requested for (nullable)"
    )
    file = models.ForeignKey(
        "files.File",
        on_delete=models.CASCADE,
        related_name="access_requests",
        null=True,
        blank=True,
        help_text="File access is requested for (nullable)"
    )
    reason = models.TextField(
        help_text="Reason for access request"
    )
    requested_access_type = models.CharField(
        max_length=50,
        help_text="Type of access requested (e.g., 'READ', 'WRITE', 'DOWNLOAD')"
    )
    status = models.CharField(
        max_length=30,
        choices=AccessRequestStatus.choices,
        default=AccessRequestStatus.PENDING,
        help_text="Access request status"
    )
    # Approval workflow
    requires_approval = models.BooleanField(
        default=True,
        help_text="Whether request requires approval"
    )
    approval_workflow = models.JSONField(
        default=list,
        null=True,
        blank=True,
        help_text="Approval workflow steps (for multi-step approval)"
    )
    current_approval_step = models.IntegerField(
        default=0,
        help_text="Current approval step index"
    )
    approvers = models.JSONField(
        default=list,
        null=True,
        blank=True,
        help_text="List of approver user IDs"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approved_access_requests",
        null=True,
        blank=True,
        help_text="User who approved this request"
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When request was approved"
    )
    rejection_reason = models.TextField(
        null=True,
        blank=True,
        help_text="Reason for rejection"
    )
    revocation_reason = models.TextField(
        null=True,
        blank=True,
        help_text="Reason for revocation (required at API)",
    )
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="rejected_access_requests",
        null=True,
        blank=True,
        help_text="User who rejected this request"
    )
    rejected_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When request was rejected"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When access expires (nullable for permanent access)"
    )
    access_granted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When access was granted"
    )
    order = models.ForeignKey(
        "marketplace.Order",
        on_delete=models.SET_NULL,
        related_name="governance_access_requests",
        null=True,
        blank=True,
        help_text="Marketplace order that triggered this access request",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "access_requests"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "requested_by"]),
            models.Index(fields=["tenant", "asset"]),
            models.Index(fields=["tenant", "dataset"]),
            models.Index(fields=["tenant", "file"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["order"]),
        ]
    
    def __str__(self):
        resource = self.asset or self.dataset or self.file
        return f"Access Request {self.id} - {resource} ({self.status})"
    
    def clean(self):
        """Validate that at least one resource is set"""
        super().clean()
        
        if not self.asset and not self.dataset and not self.file:
            raise ValidationError(
                "At least one of asset, dataset, or file must be set"
            )
    
    def save(self, *args, **kwargs):
        """Override save to validate before saving"""
        self.full_clean()
        super().save(*args, **kwargs)


class AccessRequestComment(models.Model):
    """
    Phase 272.1 — threaded comment on an access request.

    Comments can be created standalone (via the dedicated endpoint) or
    embedded in an approve/reject payload. They are always tied to an
    access request and an author (nullable on user deletion).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="access_request_comments",
        help_text="Tenant this comment belongs to",
    )
    access_request = models.ForeignKey(
        AccessRequest,
        on_delete=models.CASCADE,
        related_name="comments",
        help_text="Access request this comment is attached to",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="access_request_comments",
        null=True,
        blank=True,
        help_text="User who wrote this comment",
    )
    body = models.TextField(help_text="Comment body text")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "access_request_comments"
        ordering = ["created_at"]


class ApprovalDelegation(models.Model):
    """
    Phase 272.6 — temporary delegation of approval authority.

    A user (delegator) can delegate their approval authority to another
    user (delegate) for a bounded time window. During the active window,
    the delegate is treated as a valid approver.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="approval_delegations",
    )
    delegator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="delegations_given",
        help_text="User delegating their approval authority",
    )
    delegate = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="delegations_received",
        help_text="User receiving delegated approval authority",
    )
    start_at = models.DateTimeField(help_text="Delegation window start")
    end_at = models.DateTimeField(help_text="Delegation window end")
    reason = models.TextField(
        null=True,
        blank=True,
        help_text="Reason for delegation",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "approval_delegations"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["delegate", "start_at", "end_at"],
                name="delegation_active_window_idx",
            ),
        ]

    def is_active(self, at=None):
        at = at or timezone.now()
        return self.start_at <= at <= self.end_at
        indexes = [
            models.Index(
                fields=["access_request", "created_at"],
                name="ar_comment_thread_idx",
            ),
        ]

    def __str__(self):
        return f"Comment {self.id} on AR {self.access_request_id}"


class ComplianceReport(models.Model):
    """
    Compliance report for regulations (GDPR, HIPAA, SOX, LGPD, CCPA).
    
    Stores generated reports with scheduling and delivery options.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="compliance_reports",
        help_text="Tenant this report belongs to"
    )
    regulation = models.CharField(
        max_length=20,
        help_text="Regulation: GDPR, HIPAA, SOX, LGPD, CCPA"
    )
    report_type = models.CharField(
        max_length=50,
        default="STANDARD",
        help_text="Report type: STANDARD, SUMMARY, DETAILED"
    )
    report_data = models.JSONField(
        help_text="Report data (JSON structure)"
    )
    start_date = models.DateTimeField(
        help_text="Start date for report period"
    )
    end_date = models.DateTimeField(
        help_text="End date for report period"
    )
    # Scheduling
    scheduled = models.BooleanField(
        default=False,
        help_text="Whether report is scheduled"
    )
    schedule_frequency = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Schedule frequency: DAILY, WEEKLY, MONTHLY, QUARTERLY"
    )
    # Email delivery
    email_recipients = models.JSONField(
        default=list,
        null=True,
        blank=True,
        help_text="List of email addresses to send report to"
    )
    email_sent = models.BooleanField(
        default=False,
        help_text="Whether report was sent via email"
    )
    email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When report was sent via email"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_compliance_reports",
        null=True,
        blank=True,
        help_text="User who created this report"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "compliance_reports"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "regulation"]),
            models.Index(fields=["tenant", "scheduled"]),
            models.Index(fields=["start_date", "end_date"]),
        ]
    
    def __str__(self):
        return f"{self.regulation} Report - {self.tenant.name} ({self.start_date.date()} to {self.end_date.date()})"


class AccessPolicy(models.Model):
    """
    Attribute-Based Access Control (ABAC) policy.
    
    Defines access policies based on attributes (user, resource, environment).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="access_policies",
        help_text="Tenant this policy belongs to"
    )
    name = models.CharField(
        max_length=255,
        help_text="Policy name"
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Policy description"
    )
    # Policy conditions (JSON structure)
    conditions = models.JSONField(
        help_text="Policy conditions (user attributes, resource attributes, environment)"
    )
    # Policy effect
    effect = models.CharField(
        max_length=10,
        choices=[("ALLOW", "Allow"), ("DENY", "Deny")],
        default="ALLOW",
        help_text="Policy effect: ALLOW or DENY"
    )
    # Resource scope
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="access_policies",
        null=True,
        blank=True,
        help_text="Asset this policy applies to (nullable for tenant-wide)"
    )
    dataset = models.ForeignKey(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="access_policies",
        null=True,
        blank=True,
        help_text="Dataset this policy applies to (nullable)"
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Whether policy is enabled"
    )
    priority = models.IntegerField(
        default=100,
        help_text="Policy priority (lower number = higher priority)"
    )
    # Phase 272.4 — ordered list of approval steps.
    required_approval_chain = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Ordered list of approval steps for multi-step workflows. "
            "Each step: {step: int, role: str, label: str}. "
            "Default [] means single-step approval."
        ),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_access_policies",
        null=True,
        blank=True,
        help_text="User who created this policy"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "access_policies"
        ordering = ["priority", "-created_at"]
        indexes = [
            models.Index(fields=["tenant", "enabled"]),
            models.Index(fields=["tenant", "asset"]),
            models.Index(fields=["tenant", "dataset"]),
            models.Index(fields=["tenant", "priority"]),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.effect})"


class FieldAccessPolicy(models.Model):
    """
    Field-level access policy for ABAC.
    
    Defines access policies for specific fields within datasets.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="field_access_policies",
        help_text="Tenant this policy belongs to"
    )
    access_policy = models.ForeignKey(
        AccessPolicy,
        on_delete=models.CASCADE,
        related_name="field_policies",
        help_text="Parent access policy"
    )
    dataset = models.ForeignKey(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="field_access_policies",
        help_text="Dataset this field policy applies to"
    )
    field_name = models.CharField(
        max_length=255,
        help_text="Field name this policy applies to"
    )
    # Access control
    access_type = models.CharField(
        max_length=20,
        choices=[("READ", "Read"), ("WRITE", "Write"), ("NONE", "None")],
        default="READ",
        help_text="Access type allowed for this field"
    )
    # Masking strategy
    masking_strategy = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Masking strategy: REDACT, HASH, PARTIAL, FORMAT_PRESERVING, NONE"
    )
    masking_config = models.JSONField(
        null=True,
        blank=True,
        help_text="Masking configuration (e.g., partial mask characters, hash algorithm)"
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Whether field policy is enabled"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "field_access_policies"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "dataset", "field_name"]),
            models.Index(fields=["tenant", "access_policy"]),
            models.Index(fields=["tenant", "enabled"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "dataset", "field_name", "access_policy"],
                name="unique_field_access_policy"
            ),
        ]
    
    def __str__(self):
        return f"{self.access_policy.name} - {self.dataset} - {self.field_name}"


# Note: AccessLog and AccessCertification models are defined in:
# - hub.apps.governance.access_analytics (AccessLog)
# - hub.apps.governance.access_certification (AccessCertification)
# They are registered with Django via app config and migrations
