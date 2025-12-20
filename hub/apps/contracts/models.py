"""
Contract Models

Contract model for managing data contracts with HubContract normalization.
"""
import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

from .typed_models import validate_hub_contract_dict
from .versioning import get_default_version


class ContractStatus(models.TextChoices):
    """Contract lifecycle status enumeration"""
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    RETIRED = "RETIRED", "Retired"


class ValidationStatus(models.TextChoices):
    """Contract validation status enumeration (from DataContract CLI)"""
    VALID = "VALID", "Valid"
    INVALID = "INVALID", "Invalid"
    WARNING_ONLY = "WARNING_ONLY", "Warning Only"
    ERROR = "ERROR", "Error"


class NormalizationStatus(models.TextChoices):
    """Contract normalization status enumeration"""
    NOT_NORMALIZED = "NOT_NORMALIZED", "Not Normalized"
    NORMALIZED_OK = "NORMALIZED_OK", "Normalized OK"
    NORMALIZED_WITH_WARNINGS = "NORMALIZED_WITH_WARNINGS", "Normalized With Warnings"
    NORMALIZATION_FAILED = "NORMALIZATION_FAILED", "Normalization Failed"


class OriginalSpecType(models.TextChoices):
    """Original specification type enumeration

    Supported types:
    - ODCS: Open Data Contract Standard (technical specification)
    - ODPS: Open Data Product Standard (marketplace specification)
    """
    ODCS = "ODCS", "ODCS"
    ODPS = "ODPS", "ODPS"


class OriginalFormat(models.TextChoices):
    """Original contract format enumeration"""
    JSON = "JSON", "JSON"
    YAML = "YAML", "YAML"


class Contract(models.Model):
    """
    Contract model representing a data contract with HubContract normalization.

    Stores original contract (ODCS) and normalized HubContract.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="contracts",
        help_text="Tenant this contract belongs to"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="contracts",
        null=True,
        blank=True,
        help_text="Asset this contract belongs to (nullable for contract-only assets)"
    )
    version = models.IntegerField(
        default=1,
        help_text="Per-asset contract version counter"
    )
    status = models.CharField(
        max_length=20,
        choices=ContractStatus.choices,
        default=ContractStatus.DRAFT,
        help_text="Contract lifecycle status: DRAFT, ACTIVE, RETIRED"
    )

    # Original specification metadata
    original_spec_type = models.CharField(
        max_length=50,
        choices=OriginalSpecType.choices,
        help_text="Original spec type: ODCS (Open Data Contract Standard) or ODPS (Open Data Product Standard)"
    )
    original_spec_version = models.CharField(
        max_length=20,
        help_text="Original spec version (e.g., 3.0.2, 2.2.2)"
    )
    original_format = models.CharField(
        max_length=10,
        choices=OriginalFormat.choices,
        help_text="Original format: JSON or YAML"
    )
    original_raw = models.TextField(
        help_text="Original contract file content (verbatim)"
    )
    original_raw_resolved = models.TextField(
        null=True,
        blank=True,
        help_text="Original contract content with all $ref references resolved (cached for performance)"
    )

    # HubContract normalization
    hub_contract_version = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="HubContract version (e.g., 1.0.0)"
    )
    hub_contract_json = models.JSONField(
        db_index=True,  # GIN index for JSONB queries (Django 6)
        null=True,
        blank=True,
        help_text="Normalized HubContract JSON"
    )
    normalization_status = models.CharField(
        max_length=30,
        choices=NormalizationStatus.choices,
        null=True,
        blank=True,
        default=NormalizationStatus.NOT_NORMALIZED,
        help_text="Normalization status"
    )
    normalization_errors = models.JSONField(
        null=True,
        blank=True,
        default=list,
        help_text="Normalization errors (JSON array)"
    )
    normalization_warnings = models.JSONField(
        null=True,
        blank=True,
        default=list,
        help_text="Normalization warnings (JSON array)"
    )

    # CLI validation result
    validation_status = models.CharField(
        max_length=20,
        choices=ValidationStatus.choices,
        null=True,
        blank=True,
        help_text="CLI validation status: VALID, INVALID, WARNING_ONLY, ERROR"
    )
    validation_errors = models.JSONField(
        null=True,
        blank=True,
        default=list,
        help_text="Validation errors (JSON array)"
    )
    validation_warnings = models.JSONField(
        null=True,
        blank=True,
        default=list,
        help_text="Validation warnings (JSON array)"
    )
    cli_version = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="DataContract CLI version used"
    )
    last_validated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last validation timestamp"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_contracts",
        null=True,
        blank=True,
        help_text="User who created the contract"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contracts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "asset"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "validation_status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "asset", "version"],
                condition=models.Q(asset__isnull=False),
                name="unique_contract_version_per_asset"
            )
        ]

    def __str__(self):
        asset_name = self.asset.name if self.asset else "No Asset"
        return f"{asset_name} - {self.original_spec_type} v{self.original_spec_version} ({self.status})"

    def clean(self):
        """Validate contract status rules"""
        super().clean()

        if self.hub_contract_json:
            validated_contract, validation_errors = validate_hub_contract_dict(self.hub_contract_json)
            if validation_errors:
                raise ValidationError({"hub_contract_json": validation_errors})
            expected_version = get_default_version()
            if validated_contract and str(validated_contract.hub_contract_version) != expected_version:
                raise ValidationError({"hub_contract_json": [f"hub_contract_version must be {expected_version}"]})

        # Enforce ACTIVE status requirements
        if self.status == ContractStatus.ACTIVE:
            # Must have valid validation status
            if self.validation_status not in [ValidationStatus.VALID, ValidationStatus.WARNING_ONLY]:
                raise ValidationError(
                    f"Contract cannot be ACTIVE with validation_status={self.validation_status}. "
                    f"Required: VALID or WARNING_ONLY"
                )

            # Must have successful normalization
            if self.normalization_status not in [
                NormalizationStatus.NORMALIZED_OK,
                NormalizationStatus.NORMALIZED_WITH_WARNINGS
            ]:
                raise ValidationError(
                    f"Contract cannot be ACTIVE with normalization_status={self.normalization_status}. "
                    f"Required: NORMALIZED_OK or NORMALIZED_WITH_WARNINGS"
                )

    def can_activate(self) -> tuple[bool, str]:
        """
        Check if contract can be activated.

        Returns:
            Tuple of (can_activate: bool, reason: str)
        """
        if self.validation_status not in [ValidationStatus.VALID, ValidationStatus.WARNING_ONLY]:
            return False, f"validation_status must be VALID or WARNING_ONLY (current: {self.validation_status})"

        if self.normalization_status not in [
            NormalizationStatus.NORMALIZED_OK,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS
        ]:
            return False, f"normalization_status must be NORMALIZED_OK or NORMALIZED_WITH_WARNINGS (current: {self.normalization_status})"

        return True, ""
