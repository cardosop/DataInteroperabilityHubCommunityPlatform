from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class ConsentPurpose(models.Model):
    """Tenant-defined processing purpose (TCF-aligned metadata optional)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="consent_purposes",
        db_index=True,
    )
    key = models.SlugField(
        max_length=128,
        help_text="Stable machine key, unique per tenant (e.g. signup.privacy).",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    retention_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Optional retention hint for this purpose (informational).",
    )
    is_active = models.BooleanField(default=True)
    # IAB TCF v2.2 stack / purpose ids — optional, used by banner package.
    iab_purpose_id = models.CharField(max_length=32, blank=True, default="")
    iab_special_feature_optins = models.JSONField(default=list, blank=True)
    # 277.B.086 — version bumped automatically when substance-changing fields
    # (name, description, retention_days, iab_purpose_id) are modified, so
    # that stale consent records can be detected and users re-prompted.
    version = models.PositiveIntegerField(
        default=1,
        help_text="Monotonic version — bumped on substance changes so stale grants trigger re-consent.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "consent_purpose"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "key"], name="consent_purpose_tenant_key_uniq"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
        ]


class ConsentRecordStatus(models.TextChoices):
    GRANTED = "GRANTED", "Granted"
    REVOKED = "REVOKED", "Revoked"


class ConsentRecord(models.Model):
    """
    One logical row per (tenant, user, purpose). Cryptographic proof binds the
    canonical payload to a rolling signing key window.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="consent_records",
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="consent_records",
        db_index=True,
    )
    purpose = models.ForeignKey(
        ConsentPurpose,
        on_delete=models.PROTECT,
        related_name="consent_records",
        db_index=True,
    )
    status = models.CharField(
        max_length=16,
        choices=ConsentRecordStatus.choices,
        default=ConsentRecordStatus.GRANTED,
    )
    granted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    canonical_payload = models.JSONField(default=dict, blank=True)
    proof_hmac = models.CharField(max_length=64, blank=True, default="")
    signing_key_index = models.PositiveSmallIntegerField(
        default=0,
        help_text="Index into the tenant key ring (0 = newest) used when the proof was stamped.",
    )
    # 277.B.086 — snapshot of ConsentPurpose.version at grant time so
    # stale records (record.version < purpose.version) can be detected.
    purpose_version_at_grant = models.PositiveIntegerField(
        default=1,
        help_text="ConsentPurpose.version that was current when this grant was recorded.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "consent_record"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "user", "purpose"],
                name="consent_record_tenant_user_purpose_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "user"]),
        ]
