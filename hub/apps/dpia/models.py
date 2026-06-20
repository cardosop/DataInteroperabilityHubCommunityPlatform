"""DPIA record model — Phase 232.5."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class DpiaStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    IN_REVIEW = "IN_REVIEW", "In review"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    REQUIRES_CONSULTATION = "REQUIRES_CONSULTATION", "Requires consultation"
    SUPERSEDED = "SUPERSEDED", "Superseded"


class ResidualRiskLevel(models.TextChoices):
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"


class Dpia(models.Model):
    """
    Data Protection Impact Assessment (DPIA) register row.

    One logical assessment may span versions; older approved rows become
    SUPERSEDED when a newer version is approved.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="dpias",
        db_index=True,
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="dpias",
        help_text="When set, DPIA is scoped to this catalog asset.",
    )
    title = models.CharField(max_length=512)
    regime = models.CharField(
        max_length=32,
        default="GDPR",
        help_text="Primary regulation key (GDPR, LGPD, ...).",
    )
    status = models.CharField(
        max_length=32,
        choices=DpiaStatus.choices,
        default=DpiaStatus.DRAFT,
        db_index=True,
    )
    version = models.PositiveIntegerField(
        default=1,
        help_text="Monotonic per (tenant, asset) lineage.",
    )
    previous_version = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="next_versions",
        help_text="Prior version for diff / lineage.",
    )
    derived_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="nested_assessments",
        help_text=(
            "D232.17 — parent assessment for recursive/platform DPIA chains "
            "(tenant row may inherit scope from a platform or supplier template)."
        ),
    )
    wizard_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured wizard answers (steps, narrative fields).",
    )
    risk_residual = models.CharField(
        max_length=16,
        choices=ResidualRiskLevel.choices,
        blank=True,
        default="",
        help_text="Recorded residual risk after mitigations (set at review).",
    )
    next_review_due_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When an approved DPIA must re-enter review (typically +12 months).",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dpias_created",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dpias_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    dpo_summary = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dpia"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "asset", "status"]),
            models.Index(fields=["tenant", "next_review_due_at"]),
            models.Index(fields=["tenant", "derived_from"]),
        ]

    def __str__(self) -> str:
        return f"Dpia {self.title} ({self.status})"

    def clean(self) -> None:
        super().clean()
        if self.derived_from_id:
            if self.pk and self.derived_from_id == self.pk:
                raise ValidationError({"derived_from": "A DPIA cannot be derived from itself."})
            parent = self.derived_from
            if parent.tenant_id != self.tenant_id:
                raise ValidationError(
                    {"derived_from": "Parent DPIA must belong to the same tenant as this row."}
                )
