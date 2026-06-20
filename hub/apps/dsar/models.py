"""DSAR ORM models — separate from ``governance.AccessRequest`` (dataset access)."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class DSARRequestType(models.TextChoices):
    ACCESS = "ACCESS", "Right of access"
    ERASURE = "ERASURE", "Erasure / RTBF"
    RECTIFICATION = "RECTIFICATION", "Rectification"
    PORTABILITY = "PORTABILITY", "Data portability"
    RESTRICTION = "RESTRICTION", "Restriction of processing"
    OBJECTION = "OBJECTION", "Object to processing"
    AUTOMATED_DECISION_REVIEW = (
        "AUTOMATED_DECISION_REVIEW",
        "Automated decision-making review",
    )


class DSARStatus(models.TextChoices):
    SUBMITTED = "SUBMITTED", "Submitted"
    IDV_PENDING = "IDV_PENDING", "Identity verification pending"
    UNDER_REVIEW = "UNDER_REVIEW", "Under review"
    PACKAGE_IN_PROGRESS = "PACKAGE_IN_PROGRESS", "Packaging response"
    AWAITING_DOWNLOAD = "AWAITING_DOWNLOAD", "Response ready for download"
    CLOSED_FULFILLED = "CLOSED_FULFILLED", "Closed — fulfilled"
    CLOSED_REJECTED = "CLOSED_REJECTED", "Closed — rejected"


class DSARVerificationMethod(models.TextChoices):
    EMAIL_OTP = "EMAIL_OTP", "Email OTP"
    MANUAL_REVIEW = "MANUAL_REVIEW", "Manual identity review"
    INTERNAL_API_TOKEN = "INTERNAL_API_TOKEN", "Internal API token (tenant systems)"


class DSARSLALevel(models.TextChoices):
    NONE = "NONE", "None"
    WARN = "WARN", "Warning window"
    ALERT = "ALERT", "Alert window"
    ESCALATED = "ESCALATED", "Escalated / overdue"


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class DSARRequest(models.Model):
    """
    Cross-cutting DSAR case file. ``public_reference_token`` is the opaque
    handle for unauthenticated status pages; it MUST NOT be sequential.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="dsar_requests",
    )
    request_type = models.CharField(
        max_length=40,
        choices=DSARRequestType.choices,
    )
    status = models.CharField(
        max_length=40,
        choices=DSARStatus.choices,
        default=DSARStatus.SUBMITTED,
        db_index=True,
    )

    regimes = models.JSONField(
        default=list,
        help_text="Applicable regime keys (uppercase strings), ordered by applicability.",
    )
    subject_email = models.EmailField(
        help_text="Requester email (may differ from authenticated user)"
    )
    subject_name = models.CharField(max_length=255, blank=True, default="")
    subject_timezone = models.CharField(
        max_length=64,
        default="UTC",
        help_text="IANA TZ for countdown UI (regulator SLA remains UTC in stored deadlines).",
    )
    regulator_timezone = models.CharField(
        max_length=64,
        default="UTC",
        help_text="IANA TZ for supervisory calendar presentation (defaults to UTC).",
    )

    linked_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dsar_requests",
    )

    verification_method = models.CharField(
        max_length=32,
        choices=DSARVerificationMethod.choices,
        default=DSARVerificationMethod.EMAIL_OTP,
    )
    email_otp_digest = models.CharField(max_length=64, blank=True, default="")
    email_otp_expires_at = models.DateTimeField(null=True, blank=True)
    email_otp_attempts = models.PositiveSmallIntegerField(default=0)

    idempotency_key = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text='Client-supplied idempotency key (matched with "Idempotency-Key" header).',
    )
    public_reference_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    statutory_ack_deadline_utc = models.DateTimeField(null=True, blank=True)
    statutory_fulfil_deadline_utc = models.DateTimeField(null=True, blank=True)
    extension_path_selected = models.BooleanField(
        default=False,
        help_text="Whether the extended statutory window is used for fulfilment deadlines.",
    )

    legal_hold = models.BooleanField(
        default=False,
        help_text="When True, SLA timers are frozen per D232 / OpenSpec DSAR SLA scenario.",
    )
    legal_hold_reason = models.TextField(blank=True, default="")

    sla_suspended_event_logged = models.BooleanField(default=False)
    last_sla_level = models.CharField(
        max_length=20,
        choices=DSARSLALevel.choices,
        default=DSARSLALevel.NONE,
    )

    response_object_key = models.CharField(max_length=1024, blank=True, default="")
    response_manifest_sha256 = models.CharField(max_length=64, blank=True, default="")
    response_kms_key_id = models.CharField(max_length=512, blank=True, default="")
    response_generated_at = models.DateTimeField(null=True, blank=True)

    download_url_issued_at = models.DateTimeField(null=True, blank=True)
    download_consumed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set when a one-time presigned download is redeemed.",
    )

    handler_notes = models.TextField(blank=True, default="")
    details_json = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dsar_requests"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "statutory_fulfil_deadline_utc"]),
            models.Index(fields=["subject_email"]),
            models.Index(
                fields=["tenant", "idempotency_key"],
                # Oracle/Django E034: index names must be ≤30 characters.
                name="dsar_req_tnt_idem_ix",
            ),
        ]

    def __str__(self) -> str:
        return f"DSAR {self.id} ({self.request_type})"

    def issue_email_otp(self) -> str:
        """Generate a fresh OTP; returns plaintext for email transport only."""
        code = f"{secrets.randbelow(1000000):06d}"
        self.email_otp_digest = _hash_token(code)
        self.email_otp_expires_at = timezone.now() + timedelta(minutes=15)
        self.email_otp_attempts = 0
        self.save(
            update_fields=[
                "email_otp_digest",
                "email_otp_expires_at",
                "email_otp_attempts",
                "updated_at",
            ]
        )
        return code

    def verify_email_otp(self, code: str) -> bool:
        if not self.email_otp_digest or not self.email_otp_expires_at:
            return False
        if timezone.now() > self.email_otp_expires_at:
            return False
        if self.email_otp_attempts >= 8:
            return False
        digest = _hash_token(code.strip())
        ok = secrets.compare_digest(self.email_otp_digest, digest)
        self.email_otp_attempts += 1
        self.save(update_fields=["email_otp_attempts", "updated_at"])
        return ok


class BackupAffectedBySubject(models.Model):
    """
    D232.9 — backups and cold storage are exempt from inline cascade deletes;
    rows here track restore-scope when a DSAR erasure touches warm storage only.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="backup_affected_subjects",
    )
    dsar = models.ForeignKey(
        DSARRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="backup_affected_rows",
    )
    subject_email_normalized = models.EmailField()
    backup_identifier = models.CharField(
        max_length=512,
        help_text="Opaque backup job / snapshot label (S3 inventory id, etc.).",
    )
    exempt_from_cascade = models.BooleanField(
        default=True,
        help_text="True when regulatory posture keeps backups immutable for a window.",
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dsar_backup_affected_subjects"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "subject_email_normalized"]),
        ]

    def __str__(self) -> str:
        return f"BackupAffected {self.backup_identifier}"
