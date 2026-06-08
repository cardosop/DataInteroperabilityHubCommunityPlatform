"""Phase 232.3 — personal data breach incidents and supervisory notifications."""

from __future__ import annotations
import uuid

from django.utils import timezone

from django.conf import settings
from django.db import models


class BreachIncidentStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    CONTAINED = "CONTAINED", "Contained"
    NOTIFIED = "NOTIFIED", "Notifications issued"
    CLOSED = "CLOSED", "Closed"


class BreachSLALevel(models.TextChoices):
    NONE = "NONE", "None"
    WARN = "WARN", "Warning window"
    ALERT = "ALERT", "Alert window"
    ESCALATED = "ESCALATED", "Escalated / overdue"


class BreachNotificationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"


class BreachNotificationChannel(models.TextChoices):
    EMAIL = "EMAIL", "Email"
    MANUAL = "MANUAL", "Manual / portal"


class BreachIncident(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="breach_incidents",
    )
    title = models.CharField(max_length=512)
    summary = models.TextField(blank=True, default="")
    regimes = models.JSONField(
        default=list,
        help_text="Applicable regime keys (uppercase strings).",
    )
    discovered_at = models.DateTimeField(db_index=True)
    status = models.CharField(
        max_length=32,
        choices=BreachIncidentStatus.choices,
        default=BreachIncidentStatus.OPEN,
        db_index=True,
    )
    statutory_authority_deadline_utc = models.DateTimeField(
        db_index=True,
        default=timezone.now,
        help_text="Soonest supervisory-notification deadline (UTC).",
    )
    legal_hold = models.BooleanField(
        default=False,
        help_text="When True, breach SLA scans skip this incident.",
    )
    legal_hold_reason = models.TextField(blank=True, default="")
    last_sla_level = models.CharField(
        max_length=20,
        choices=BreachSLALevel.choices,
        default=BreachSLALevel.NONE,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="breach_incidents_created",
    )
    details_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "breach_incident"
        ordering = ["-discovered_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "statutory_authority_deadline_utc"]),
        ]

    def __str__(self) -> str:
        return f"BreachIncident {self.id} ({self.status})"


class BreachNotification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="breach_notifications",
    )
    incident = models.ForeignKey(
        BreachIncident,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    regime = models.CharField(max_length=32, db_index=True)
    supervisory_authority_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Id from regulation_authorities.yaml (empty when none).",
    )
    status = models.CharField(
        max_length=16,
        choices=BreachNotificationStatus.choices,
        default=BreachNotificationStatus.PENDING,
        db_index=True,
    )
    channel = models.CharField(
        max_length=16,
        choices=BreachNotificationChannel.choices,
        default=BreachNotificationChannel.MANUAL,
    )
    statutory_due_at_utc = models.DateTimeField()
    rendered_subject = models.TextField(blank=True, default="")
    rendered_body = models.TextField(blank=True, default="")
    template_version = models.PositiveIntegerField(default=1)
    delivery_proof_sha256 = models.CharField(max_length=64, blank=True, default="")
    proof_storage_path = models.CharField(max_length=1024, blank=True, default="")
    proof_s3_version_id = models.CharField(max_length=256, blank=True, default="")
    object_lock_retention_days = models.PositiveIntegerField(
        default=0,
        help_text="Days requested for S3 Object Lock retention when archiving proof.",
    )
    outbound_reference = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="Operator reference (ticket id, case number, message id).",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "breach_notification"
        ordering = ["regime", "supervisory_authority_id"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "statutory_due_at_utc"]),
        ]

    def __str__(self) -> str:
        return f"BreachNotification {self.id} ({self.regime}/{self.supervisory_authority_id})"


class BreachTenantTemplateOverride(models.Model):
    """Per-tenant template body overrides (Phase 232.3.15)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="breach_template_overrides",
    )
    regime = models.CharField(max_length=32, db_index=True)
    subject_template = models.TextField(blank=True, default="")
    body_template = models.TextField(blank=True, default="")
    template_version = models.PositiveIntegerField(default=1)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="breach_template_updates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "breach_tenant_template_override"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "regime"],
                # Django/Oracle E034: constraint names must be ≤30 characters.
                name="br_tt_ovr_tnt_reg_uniq",
            ),
        ]
