"""
Email Delivery Tracking Models

Tracks email delivery status for auditing and debugging.
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class EmailDeliveryStatus(models.TextChoices):
    """Email delivery status enumeration"""
    PENDING = "PENDING", "Pending"
    SENT = "SENT", "Sent"
    DELIVERED = "DELIVERED", "Delivered"
    BOUNCED = "BOUNCED", "Bounced"
    FAILED = "FAILED", "Failed"
    DEFERRED = "DEFERRED", "Deferred"


class EmailType(models.TextChoices):
    """Email type enumeration"""
    USER_INVITATION = "USER_INVITATION", "User Invitation"
    PASSWORD_RESET = "PASSWORD_RESET", "Password Reset"
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION", "Email Verification"
    JOB_COMPLETION = "JOB_COMPLETION", "Job Completion"
    JOB_FAILURE = "JOB_FAILURE", "Job Failure"
    API_DEPRECATION = "API_DEPRECATION", "API Deprecation"
    ODPS_CREATION_COMPLETION = "ODPS_CREATION_COMPLETION", "ODPS Creation Completion"
    ODPS_NORMALIZATION_FAILURE = "ODPS_NORMALIZATION_FAILURE", "ODPS Normalization Failure"
    ODPS_LINKING_STATUS = "ODPS_LINKING_STATUS", "ODPS Linking Status"
    MARKETPLACE_SYNC_COMPLETION = "MARKETPLACE_SYNC_COMPLETION", "Marketplace Sync Completion"
    MARKETPLACE_SYNC_FAILURE = "MARKETPLACE_SYNC_FAILURE", "Marketplace Sync Failure"
    MARKETPLACE_CONNECTION_TEST_FAILURE = "MARKETPLACE_CONNECTION_TEST_FAILURE", "Marketplace Connection Test Failure"
    API_KEY_CREATED = "API_KEY_CREATED", "API Key Created"
    API_KEY_REVOKED = "API_KEY_REVOKED", "API Key Revoked"

    # Customer billing (Phase 116A.8)
    CUSTOMER_BILLING_REPORT = "CUSTOMER_BILLING_REPORT", "Customer Billing Report"

    # ML events (Phase 114C.7)
    ML_TRAINING_COMPLETION = "ML_TRAINING_COMPLETION", "ML Training Completion"
    ML_TRAINING_FAILURE = "ML_TRAINING_FAILURE", "ML Training Failure"
    ML_INFERENCE_FAILURE = "ML_INFERENCE_FAILURE", "ML Inference Failure"
    ML_MODEL_DEPLOYED = "ML_MODEL_DEPLOYED", "ML Model Deployed"

    # Transformation events (Phase 115C.3)
    TRANSFORMATION_COMPLETION = "TRANSFORMATION_COMPLETION", "Transformation Completion"
    TRANSFORMATION_FAILURE = "TRANSFORMATION_FAILURE", "Transformation Failure"

    # Phase 227 Wave 0 — T-14 heads-up to TENANT_ADMINs whose contracts
    # are structureless and pending Wave-5 deadline.
    ASSET_CONTRACT_STRUCTURELESS_PENDING = (
        "ASSET_CONTRACT_STRUCTURELESS_PENDING",
        "Asset Contract Structureless — Pending Remediation",
    )


class EmailDelivery(models.Model):
    """
    Tracks email delivery status and metadata.

    Used for auditing, debugging, and retry logic.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email_type = models.CharField(
        max_length=50,
        choices=EmailType.choices,
        help_text="Type of email sent"
    )
    to_email = models.EmailField(
        help_text="Recipient email address"
    )
    subject = models.CharField(
        max_length=255,
        help_text="Email subject"
    )
    status = models.CharField(
        max_length=20,
        choices=EmailDeliveryStatus.choices,
        default=EmailDeliveryStatus.PENDING,
        help_text="Delivery status"
    )
    message_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Message ID from email service (SendGrid, SES, etc.)"
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if delivery failed"
    )
    retry_count = models.IntegerField(
        default=0,
        help_text="Number of retry attempts"
    )
    max_retries = models.IntegerField(
        default=3,
        help_text="Maximum number of retry attempts"
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When email was sent"
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When email was delivered (from webhook)"
    )
    failed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When email delivery failed"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When email delivery record was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When email delivery record was last updated"
    )
    metadata_json = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text="Additional metadata (template context, etc.)"
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        related_name="email_deliveries",
        null=True,
        blank=True,
        help_text="Tenant this email is related to"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="email_deliveries",
        null=True,
        blank=True,
        help_text="User this email is related to"
    )

    class Meta:
        db_table = 'email_deliveries'
        indexes = [
            models.Index(fields=['to_email', 'status']),
            models.Index(fields=['email_type', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['tenant', 'status']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email_type} to {self.to_email} ({self.status})"

    def mark_sent(self, message_id: str = None):
        """Mark email as sent"""
        self.status = EmailDeliveryStatus.SENT
        self.sent_at = timezone.now()
        if message_id:
            self.message_id = message_id
        self.save(update_fields=['status', 'sent_at', 'message_id', 'updated_at'])

    def mark_delivered(self):
        """Mark email as delivered"""
        self.status = EmailDeliveryStatus.DELIVERED
        self.delivered_at = timezone.now()
        self.save(update_fields=['status', 'delivered_at', 'updated_at'])

    def mark_failed(self, error_message: str):
        """Mark email as failed"""
        self.status = EmailDeliveryStatus.FAILED
        self.failed_at = timezone.now()
        self.error_message = error_message
        self.save(update_fields=['status', 'failed_at', 'error_message', 'updated_at'])

    def mark_bounced(self, error_message: str = None):
        """Mark email as bounced"""
        self.status = EmailDeliveryStatus.BOUNCED
        self.failed_at = timezone.now()
        if error_message:
            self.error_message = error_message
        self.save(update_fields=['status', 'failed_at', 'error_message', 'updated_at'])

    def can_retry(self) -> bool:
        """Check if email can be retried"""
        return (
            self.status in [EmailDeliveryStatus.FAILED, EmailDeliveryStatus.DEFERRED] and
            self.retry_count < self.max_retries
        )

    def increment_retry(self):
        """Increment retry count"""
        self.retry_count += 1
        self.save(update_fields=['retry_count', 'updated_at'])



class NotificationType(models.TextChoices):
    """Severity/variant for in-app notifications."""
    INFO = "INFO", "Info"
    SUCCESS = "SUCCESS", "Success"
    WARNING = "WARNING", "Warning"
    ERROR = "ERROR", "Error"


class NotificationCategory(models.TextChoices):
    """Top-level functional grouping for in-app notifications."""
    GOVERNANCE = "GOVERNANCE", "Governance"
    MARKETPLACE = "MARKETPLACE", "Marketplace"
    JOBS = "JOBS", "Jobs"
    CONTRACTS = "CONTRACTS", "Contracts"
    SYSTEM = "SYSTEM", "System"


class UserNotification(models.Model):
    """
    Thin, user-scoped in-app notification.

    Designed as a pointer: for rich context consumers should follow
    ``resource_type`` + ``resource_id`` or the optional ``audit_event``
    link. Storing a short title + message denormalised on the row keeps
    list rendering cheap and survives deletion of the underlying resource.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="user_notifications",
        help_text="Tenant this notification belongs to",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_notifications",
        help_text="Recipient",
    )
    audit_event = models.ForeignKey(
        "audit.AuditEvent",
        on_delete=models.SET_NULL,
        related_name="user_notifications",
        null=True,
        blank=True,
        help_text="Optional link to the underlying audit event",
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=10,
        choices=NotificationType.choices,
        default=NotificationType.INFO,
    )
    category = models.CharField(
        max_length=20,
        choices=NotificationCategory.choices,
        default=NotificationCategory.SYSTEM,
    )
    resource_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Resource type the notification points at (matches AuditEvent.resource_type)",
    )
    resource_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Resource UUID the notification points at",
    )
    read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "user_notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "read", "-created_at"]),
            models.Index(fields=["tenant", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} -> {self.user_id} ({self.category})"

    def mark_read(self) -> None:
        """Flip the row to read; idempotent — no-ops when already read."""
        if self.read:
            return
        self.read = True
        self.read_at = timezone.now()
        self.save(update_fields=["read", "read_at"])
