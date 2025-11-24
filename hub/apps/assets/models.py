"""
Assets Models

Asset model for managing data products (contract + dataset).
"""
import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class AssetStatus(models.TextChoices):
    """Asset lifecycle status enumeration"""
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    PUBLIC = "PUBLIC", "Public"
    RETIRED = "RETIRED", "Retired"


class AssetVisibility(models.TextChoices):
    """Asset visibility enumeration"""
    INTERNAL = "INTERNAL", "Internal"
    PUBLIC = "PUBLIC", "Public"


class DQStatus(models.TextChoices):
    """Data Quality status enumeration"""
    UNKNOWN = "UNKNOWN", "Unknown"
    PASS = "PASS", "Pass"
    WARN = "WARN", "Warning"
    FAIL = "FAIL", "Fail"


class ComplianceStatus(models.TextChoices):
    """Compliance status enumeration"""
    UNKNOWN = "UNKNOWN", "Unknown"
    PASS = "PASS", "Pass"
    WARN = "WARN", "Warning"
    FAIL = "FAIL", "Fail"


class Asset(models.Model):
    """
    Asset model representing a logical data product (contract + dataset).
    
    Assets are the primary entities in the catalog, linking contracts and datasets.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="assets",
        help_text="Tenant this asset belongs to"
    )
    key = models.CharField(
        max_length=255,
        help_text="Human-friendly identifier, unique per tenant"
    )
    name = models.CharField(
        max_length=255,
        help_text="Asset name"
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Asset description"
    )
    domain = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Domain (e.g., marketing, finance)"
    )
    status = models.CharField(
        max_length=20,
        choices=AssetStatus.choices,
        default=AssetStatus.DRAFT,
        help_text="Asset lifecycle status: DRAFT, ACTIVE, PUBLIC, RETIRED"
    )
    visibility = models.CharField(
        max_length=20,
        choices=AssetVisibility.choices,
        default=AssetVisibility.INTERNAL,
        help_text="Asset visibility: INTERNAL, PUBLIC"
    )
    dq_status = models.CharField(
        max_length=20,
        choices=DQStatus.choices,
        default=DQStatus.UNKNOWN,
        help_text="Data Quality status: UNKNOWN, PASS, WARN, FAIL"
    )
    compliance_status = models.CharField(
        max_length=20,
        choices=ComplianceStatus.choices,
        default=ComplianceStatus.UNKNOWN,
        help_text="Compliance status: UNKNOWN, PASS, WARN, FAIL"
    )
    version = models.IntegerField(
        default=1,
        help_text="Optimistic locking version counter"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_assets",
        null=True,
        blank=True,
        help_text="User who created the asset"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "assets"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "key"]),
            models.Index(fields=["tenant", "visibility"]),
            models.Index(fields=["tenant", "dq_status"]),
            models.Index(fields=["tenant", "compliance_status"]),
            models.Index(fields=["tenant", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "key"],
                name="unique_asset_key_per_tenant"
            )
        ]
    
    def __str__(self):
        return f"{self.name} ({self.key})"
    
    def clean(self):
        """Validate asset activation requirements"""
        super().clean()
        
        # Enforce ACTIVE status requirements
        if self.status == AssetStatus.ACTIVE:
            # Check contract requirements
            active_contract = self.contracts.filter(status="ACTIVE").first()
            if not active_contract:
                raise ValidationError(
                    "Asset cannot be ACTIVE without an ACTIVE contract"
                )
            
            if active_contract.validation_status not in ["VALID", "WARNING_ONLY"]:
                raise ValidationError(
                    f"Asset cannot be ACTIVE with contract validation_status={active_contract.validation_status}. "
                    f"Required: VALID or WARNING_ONLY"
                )
            
            if active_contract.normalization_status not in [
                "NORMALIZED_OK",
                "NORMALIZED_WITH_WARNINGS"
            ]:
                raise ValidationError(
                    f"Asset cannot be ACTIVE with contract normalization_status={active_contract.normalization_status}. "
                    f"Required: NORMALIZED_OK or NORMALIZED_WITH_WARNINGS"
                )
            
            # Check dataset requirements (if dataset exists)
            dataset = self.datasets.first()
            if dataset:
                if self.dq_status not in [DQStatus.PASS, DQStatus.WARN]:
                    raise ValidationError(
                        f"Asset cannot be ACTIVE with dq_status={self.dq_status}. "
                        f"Required: PASS or WARN"
                    )
                
                if self.compliance_status not in [ComplianceStatus.PASS, ComplianceStatus.WARN]:
                    raise ValidationError(
                        f"Asset cannot be ACTIVE with compliance_status={self.compliance_status}. "
                        f"Required: PASS or WARN"
                    )
    
    def can_activate(self) -> tuple[bool, list[str]]:
        """
        Check if asset can be activated.
        
        Returns:
            Tuple of (can_activate: bool, blockers: list[str])
        """
        blockers = []
        
        # Check contract requirements
        active_contract = self.contracts.filter(status="ACTIVE").first()
        if not active_contract:
            blockers.append("Asset must have an ACTIVE contract")
        else:
            # Check contract validation status
            if active_contract.validation_status not in ["VALID", "WARNING_ONLY"]:
                blockers.append(
                    f"Contract validation_status must be VALID or WARNING_ONLY "
                    f"(current: {active_contract.validation_status})"
                )
            
            # Check contract normalization status
            if active_contract.normalization_status not in [
                "NORMALIZED_OK",
                "NORMALIZED_WITH_WARNINGS"
            ]:
                blockers.append(
                    f"Contract normalization_status must be NORMALIZED_OK or NORMALIZED_WITH_WARNINGS "
                    f"(current: {active_contract.normalization_status})"
                )
        
        # Check dataset requirements (if dataset exists)
        # Contract-only assets (no dataset) are allowed
        dataset = self.datasets.first()
        if dataset:
            # Check DQ status
            if self.dq_status not in [DQStatus.PASS, DQStatus.WARN]:
                blockers.append(
                    f"dq_status must be PASS or WARN (current: {self.dq_status})"
                )
            
            # Check compliance status
            if self.compliance_status not in [ComplianceStatus.PASS, ComplianceStatus.WARN]:
                blockers.append(
                    f"compliance_status must be PASS or WARN (current: {self.compliance_status})"
                )
        
        return len(blockers) == 0, blockers
    
    def increment_version(self):
        """Increment version for optimistic locking"""
        self.version += 1
        self.save(update_fields=['version', 'updated_at'])

