"""
Data Mesh Models

Models for data mesh domains, federated governance, and mesh topology.
"""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def default_empty_dict():
    """Return a new empty dict. Used as default for JSONField to avoid mutable default argument."""
    return {}


class DomainStatus(models.TextChoices):
    """Data mesh domain status enumeration"""

    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    ARCHIVED = "ARCHIVED", "Archived"


class DataMeshDomain(models.Model):
    """
    Data Mesh Domain model representing a bounded context in a data mesh architecture.

    A domain is a logical grouping of data products, capabilities, and resources
    that share common ownership and governance boundaries. Domains enable
    federated governance while maintaining autonomy.

    Fields:
        id: UUID primary key
        tenant_id: Foreign key to Tenant (CASCADE delete)
        name: Domain name (required, max 255 chars)
        description: Domain description (optional)
        owner_id: Foreign key to User who owns the domain (SET_NULL on delete)
        boundaries: JSONB field storing domain boundaries (data products, schemas, etc.)
        capabilities: JSONB field storing domain capabilities (APIs, services, etc.)
        resource_quota: JSONB field storing resource quotas (storage, compute, etc.)
        resource_usage: JSONB field storing current resource usage
        status: Domain status (ACTIVE, INACTIVE, ARCHIVED)
        created_at: Timestamp when domain was created
        updated_at: Timestamp when domain was last updated
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="mesh_domains",
        help_text="Tenant this domain belongs to",
    )
    name = models.CharField(max_length=255, help_text="Domain name (unique per tenant)")
    description = models.TextField(null=True, blank=True, help_text="Domain description")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="owned_mesh_domains",
        null=True,
        blank=True,
        help_text="User who owns this domain",
    )
    boundaries = models.JSONField(
        default=default_empty_dict,
        blank=True,
        help_text="Domain boundaries as JSON (data products, schemas, access patterns, etc.)",
    )
    capabilities = models.JSONField(
        default=default_empty_dict,
        blank=True,
        help_text="Domain capabilities as JSON (APIs, services, data products, etc.)",
    )
    resource_quota = models.JSONField(
        default=default_empty_dict,
        blank=True,
        help_text="Resource quotas as JSON (storage_gb, compute_hours, api_calls_per_day, etc.)",
    )
    resource_usage = models.JSONField(
        default=default_empty_dict,
        blank=True,
        help_text="Current resource usage as JSON (storage_gb_used, compute_hours_used, etc.)",
    )
    status = models.CharField(
        max_length=20,
        choices=DomainStatus.choices,
        default=DomainStatus.ACTIVE,
        help_text="Domain status: ACTIVE, INACTIVE, or ARCHIVED",
    )
    workflow_instance = models.ForeignKey(
        "orchestration.WorkflowInstance",
        on_delete=models.SET_NULL,
        related_name="created_domains",
        null=True,
        blank=True,
        help_text="Workflow instance that created this domain",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "data_mesh_domains"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["owner"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["workflow_instance"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="unique_domain_name_per_tenant")
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"

    def clean(self):
        """
        Validate domain model data.

        Raises:
            ValidationError: If validation fails
        """
        super().clean()

        # Validate name is not empty
        if not self.name or not self.name.strip():
            raise ValidationError({"name": "Domain name cannot be empty"})

        # Validate boundaries is a dict if provided
        if self.boundaries and not isinstance(self.boundaries, dict):
            raise ValidationError({"boundaries": "Boundaries must be a JSON object"})

        # Validate capabilities is a dict if provided
        if self.capabilities and not isinstance(self.capabilities, dict):
            raise ValidationError({"capabilities": "Capabilities must be a JSON object"})

        # Validate resource_quota is a dict if provided
        if self.resource_quota and not isinstance(self.resource_quota, dict):
            raise ValidationError({"resource_quota": "Resource quota must be a JSON object"})

        # Validate resource_usage is a dict if provided
        if self.resource_usage and not isinstance(self.resource_usage, dict):
            raise ValidationError({"resource_usage": "Resource usage must be a JSON object"})

        # Validate owner belongs to same tenant if provided
        if self.owner and self.tenant and self.owner.tenant != self.tenant:
            raise ValidationError(
                {"owner": "Domain owner must belong to the same tenant as the domain"}
            )

    def save(self, *args, **kwargs):
        """
        Save domain with validation.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        self.full_clean()
        super().save(*args, **kwargs)

    def is_active(self) -> bool:
        """Check if domain is active"""
        return self.status == DomainStatus.ACTIVE

    def is_inactive(self) -> bool:
        """Check if domain is inactive"""
        return self.status == DomainStatus.INACTIVE

    def is_archived(self) -> bool:
        """Check if domain is archived"""
        return self.status == DomainStatus.ARCHIVED

    def get_resource_usage_percentage(self, resource_type: str) -> float:
        """
        Get resource usage percentage for a specific resource type.

        Args:
            resource_type: Resource type (e.g., 'storage_gb', 'compute_hours')

        Returns:
            Usage percentage (0-100) or 0.0 if quota not set
        """
        quota = self.resource_quota.get(resource_type)
        # Check for both resource_type and resource_type + "_used" in usage
        usage = self.resource_usage.get(resource_type, 0)
        if usage == 0:
            usage = self.resource_usage.get(f"{resource_type}_used", 0)

        if quota is None or quota == 0:
            return 0.0

        percentage = (usage / quota) * 100
        return min(percentage, 100.0)  # Cap at 100%

    def is_resource_quota_exceeded(self, resource_type: str) -> bool:
        """
        Check if resource quota is exceeded for a specific resource type.

        Args:
            resource_type: Resource type (e.g., 'storage_gb', 'compute_hours')

        Returns:
            True if quota is exceeded, False otherwise
        """
        quota = self.resource_quota.get(resource_type)
        # Check for both resource_type and resource_type + "_used" in usage
        usage = self.resource_usage.get(resource_type, 0)
        if usage == 0:
            usage = self.resource_usage.get(f"{resource_type}_used", 0)

        if quota is None:
            return False

        return usage > quota


class PolicyApplicationStatus(models.TextChoices):
    """Policy application status enumeration"""

    PENDING = "PENDING", "Pending"
    APPLIED = "APPLIED", "Applied"
    FAILED = "FAILED", "Failed"
    REVOKED = "REVOKED", "Revoked"


class PolicyApplication(models.Model):
    """
    Policy Application model representing the application of a policy to a data mesh domain.

    Tracks which policies are applied to domains, including any overrides or customizations.
    This enables federated governance where domains can have domain-specific policy applications
    while maintaining consistency with tenant-wide policies.

    Fields:
        id: UUID primary key
        domain_id: Foreign key to DataMeshDomain (CASCADE delete)
        policy_id: Foreign key to AccessPolicy (SET_NULL on delete)
        applied_by_id: Foreign key to User who applied the policy (SET_NULL on delete)
        overrides: JSONB field storing policy overrides and customizations
        status: Application status (PENDING, APPLIED, FAILED, REVOKED)
        applied_at: Timestamp when policy was applied
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(
        "mesh.DataMeshDomain",
        on_delete=models.CASCADE,
        related_name="policy_applications",
        help_text="Domain this policy is applied to",
    )
    policy = models.ForeignKey(
        "governance.AccessPolicy",
        on_delete=models.SET_NULL,
        related_name="mesh_domain_applications",
        null=True,
        blank=True,
        help_text="Policy being applied (nullable if policy is deleted)",
    )
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="applied_mesh_policies",
        null=True,
        blank=True,
        help_text="User who applied this policy",
    )
    overrides = models.JSONField(
        default=default_empty_dict,
        blank=True,
        help_text="Policy overrides as JSON (conditions, effect, priority, etc.)",
    )
    status = models.CharField(
        max_length=20,
        choices=PolicyApplicationStatus.choices,
        default=PolicyApplicationStatus.PENDING,
        help_text="Application status: PENDING, APPLIED, FAILED, or REVOKED",
    )
    applied_at = models.DateTimeField(
        null=True, blank=True, help_text="Timestamp when policy was applied"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "policy_applications"
        ordering = ["-applied_at", "-created_at"]
        indexes = [
            models.Index(fields=["domain"]),
            models.Index(fields=["policy"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        policy_name = self.policy.name if self.policy else "Unknown Policy"
        return f"{policy_name} on {self.domain.name} ({self.status})"

    def clean(self):
        """
        Validate policy application model data.

        Raises:
            ValidationError: If validation fails
        """
        super().clean()

        # Validate overrides is a dict if provided
        if self.overrides and not isinstance(self.overrides, dict):
            raise ValidationError({"overrides": "Overrides must be a JSON object"})

        # Validate policy and domain belong to same tenant if both exist
        if self.policy and self.domain and self.policy.tenant != self.domain.tenant:
            raise ValidationError({"policy": "Policy must belong to the same tenant as the domain"})

        # Validate applied_by belongs to same tenant as domain if provided
        if self.applied_by and self.domain and self.applied_by.tenant != self.domain.tenant:
            raise ValidationError(
                {"applied_by": "User must belong to the same tenant as the domain"}
            )

    def save(self, *args, **kwargs):
        """
        Save policy application with validation.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        self.full_clean()

        # Set applied_at when status changes to APPLIED
        if self.status == PolicyApplicationStatus.APPLIED and not self.applied_at:
            self.applied_at = timezone.now()

        super().save(*args, **kwargs)

    def is_applied(self) -> bool:
        """Check if policy is applied"""
        return self.status == PolicyApplicationStatus.APPLIED

    def is_pending(self) -> bool:
        """Check if policy application is pending"""
        return self.status == PolicyApplicationStatus.PENDING

    def is_failed(self) -> bool:
        """Check if policy application failed"""
        return self.status == PolicyApplicationStatus.FAILED

    def is_revoked(self) -> bool:
        """Check if policy application is revoked"""
        return self.status == PolicyApplicationStatus.REVOKED


class MeshComplianceStatus(models.TextChoices):
    """Compliance status enumeration for mesh domain compliance reports"""

    COMPLIANT = "COMPLIANT", "Compliant"
    NON_COMPLIANT = "NON_COMPLIANT", "Non-Compliant"
    PARTIAL = "PARTIAL", "Partially Compliant"
    UNKNOWN = "UNKNOWN", "Unknown"


class ComplianceReport(models.Model):
    """
    Compliance Report model for data mesh domains.

    Tracks compliance status and violations for domains and optionally specific assets.
    This enables federated governance where each domain can track its own compliance
    status independently while maintaining visibility at the tenant level.

    Fields:
        id: UUID primary key
        domain_id: Foreign key to DataMeshDomain (CASCADE delete)
        asset_id: Foreign key to Asset (optional, SET_NULL on delete)
        compliance_status: Compliance status (COMPLIANT, NON_COMPLIANT, PARTIAL, UNKNOWN)
        violations: JSONB field storing violation details
        generated_at: Timestamp when report was generated
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(
        "mesh.DataMeshDomain",
        on_delete=models.CASCADE,
        related_name="compliance_reports",
        help_text="Domain this compliance report is for",
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.SET_NULL,
        related_name="mesh_compliance_reports",
        null=True,
        blank=True,
        help_text="Asset this compliance report is for (optional, for asset-specific reports)",
    )
    compliance_status = models.CharField(
        max_length=20,
        choices=MeshComplianceStatus.choices,
        default=MeshComplianceStatus.UNKNOWN,
        help_text="Compliance status: COMPLIANT, NON_COMPLIANT, PARTIAL, or UNKNOWN",
    )
    violations = models.JSONField(
        default=default_empty_dict,
        blank=True,
        help_text="Violations as JSON (list of violation objects with type, severity, description, etc.)",
    )
    generated_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when report was generated"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mesh_compliance_reports"
        ordering = ["-generated_at"]
        indexes = [
            models.Index(fields=["domain"]),
            models.Index(fields=["asset"]),
            models.Index(fields=["compliance_status"]),
        ]

    def __str__(self):
        asset_str = f" - {self.asset.name}" if self.asset else ""
        return f"Compliance Report for {self.domain.name}{asset_str} ({self.compliance_status})"

    def clean(self):
        """
        Validate compliance report model data.

        Raises:
            ValidationError: If validation fails
        """
        super().clean()

        # Validate violations is a dict if provided
        if self.violations and not isinstance(self.violations, dict):
            raise ValidationError({"violations": "Violations must be a JSON object"})

        # Validate asset belongs to same tenant as domain if provided
        if self.asset and self.domain and self.asset.tenant != self.domain.tenant:
            raise ValidationError({"asset": "Asset must belong to the same tenant as the domain"})

    def save(self, *args, **kwargs):
        """
        Save compliance report with validation.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        self.full_clean()
        super().save(*args, **kwargs)

    def is_compliant(self) -> bool:
        """Check if domain/asset is compliant"""
        return self.compliance_status == MeshComplianceStatus.COMPLIANT

    def is_non_compliant(self) -> bool:
        """Check if domain/asset is non-compliant"""
        return self.compliance_status == MeshComplianceStatus.NON_COMPLIANT

    def is_partial(self) -> bool:
        """Check if domain/asset is partially compliant"""
        return self.compliance_status == MeshComplianceStatus.PARTIAL

    def get_violation_count(self) -> int:
        """
        Get the number of violations.

        Returns:
            Number of violations (0 if none or violations not in expected format)
        """
        if not self.violations:
            return 0

        # If violations is a dict with an 'items' key containing a list
        if isinstance(self.violations, dict) and "items" in self.violations:
            violations_list = self.violations.get("items", [])
            if isinstance(violations_list, list):
                return len(violations_list)

        # If violations is a dict with a 'violations' key containing a list
        if isinstance(self.violations, dict) and "violations" in self.violations:
            violations_list = self.violations.get("violations", [])
            if isinstance(violations_list, list):
                return len(violations_list)

        # If violations is a list directly
        if isinstance(self.violations, list):
            return len(self.violations)

        # If violations is a dict with count
        if isinstance(self.violations, dict) and "count" in self.violations:
            return self.violations.get("count", 0)

        return 0
