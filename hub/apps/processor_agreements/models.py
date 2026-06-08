"""Processor entities and agreements (Phase 232.6)."""

from __future__ import annotations
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from hub.apps.processor_agreements.validators import (
    normalize_subprocessors_declared,
    validate_agreement_metadata_for_type,
    validate_document_hash_hex,
    validate_document_uri_for_agreement,
)


class ProcessorAgreementType(models.TextChoices):
    DPA = "DPA", "Data Processing Agreement"
    BAA = "BAA", "Business Associate Agreement"
    SCC = "SCC", "Standard Contractual Clause"
    BCR = "BCR", "Binding Corporate Rules"


class ProcessorAgreementStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    EXPIRED = "EXPIRED", "Expired"
    SUPERSEDED = "SUPERSEDED", "Superseded"


class Processor(models.Model):
    """Data processor / sub-processor counterparty (tenant-scoped)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="processors",
    )
    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=512, blank=True, default="")
    country_code = models.CharField(
        max_length=2,
        blank=True,
        default="",
        help_text="ISO 3166-1 alpha-2 (optional).",
    )
    website = models.URLField(
        max_length=2048,
        blank=True,
        default="",
        help_text="Public website; validated for SSRF when non-empty.",
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pa_processor"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="pa_proc_tnt_name_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "name"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.tenant_id})"

    def clean(self) -> None:
        from hub.apps.processor_agreements.validators import drf_validate_webhook_style_url

        if self.website:
            try:
                drf_validate_webhook_style_url(self.website)
            except Exception as exc:
                raise ValidationError({"website": str(exc)}) from exc


class ProcessorAgreement(models.Model):
    """Governance record for processor agreement artefacts (URI + tamper hash)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="processor_agreements",
    )
    processor = models.ForeignKey(
        Processor,
        on_delete=models.CASCADE,
        related_name="agreements",
    )
    agreement_type = models.CharField(
        max_length=16,
        choices=ProcessorAgreementType.choices,
    )
    document_uri = models.URLField(max_length=2048)
    document_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 hex digest of agreement bytes at registration time.",
    )
    effective_from = models.DateField()
    expires_on = models.DateField(null=True, blank=True)
    sub_processors_declared = models.JSONField(
        default=list,
        blank=True,
        help_text="Structured list of named sub-processors disclosed under the agreement.",
    )
    jurisdiction_region = models.CharField(
        max_length=8,
        blank=True,
        default="",
        help_text="Region hint for type-specific validation (e.g. US for BAA).",
    )
    registration_reference = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="Supervisory register id / corporate instrument reference (esp. BCR).",
    )
    transfer_mechanism_summary = models.TextField(
        blank=True,
        default="",
        help_text="Required detail for SCC-style transfers.",
    )
    status = models.CharField(
        max_length=16,
        choices=ProcessorAgreementStatus.choices,
        default=ProcessorAgreementStatus.ACTIVE,
    )
    expiry_warn_windows_sent = models.JSONField(
        default=list,
        blank=True,
        help_text="Which day-threshold notifications have fired (e.g. [60, 30, 7]).",
    )
    details_json = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processor_agreements_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pa_agreement"
        ordering = ["-effective_from"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "expires_on"]),
            models.Index(fields=["processor", "agreement_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.agreement_type} / {self.processor.name}"

    def clean(self) -> None:
        self.document_uri = validate_document_uri_for_agreement(self.document_uri)
        self.document_hash = validate_document_hash_hex(self.document_hash)
        self.sub_processors_declared = normalize_subprocessors_declared(self.sub_processors_declared)
        validate_agreement_metadata_for_type(
            agreement_type=self.agreement_type,
            expires_on=self.expires_on,
            jurisdiction_region=self.jurisdiction_region,
            registration_reference=self.registration_reference,
            transfer_mechanism_summary=self.transfer_mechanism_summary,
        )


class AssetProcessorMembership(models.Model):
    """Explicit M2M with tenant for RLS (Phase 232.6.6)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="asset_processor_links",
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="_processor_links",
    )
    processor = models.ForeignKey(
        Processor,
        on_delete=models.CASCADE,
        related_name="_asset_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pa_asset_processor"
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "processor"],
                name="pa_ast_proc_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "processor"]),
        ]

    def save(self, *args, **kwargs):
        if self.asset_id:
            self.tenant_id = self.asset.tenant_id
        if self.asset_id and self.processor_id:
            if self.processor.tenant_id != self.asset.tenant_id:
                raise ValidationError("Processor and asset must belong to the same tenant.")
        super().save(*args, **kwargs)
