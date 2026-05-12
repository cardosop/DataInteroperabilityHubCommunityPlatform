"""
Data Mesh Business Rules

Comprehensive business rules validation for data mesh domains, including:
- Domain structure validation
- Ownership transfer validation
- Boundaries validation
- Policy application validation
- Compliance checking
- Topology calculation

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""
import logging
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError as DjangoValidationError

from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import register_rule
from hub.apps.mesh.models import DataMeshDomain, DomainStatus
from hub.apps.users.models import User
from hub.apps.assets.models import Asset

logger = logging.getLogger(__name__)


@dataclass
class DataMeshRuleExecutionContext(RuleExecutionContext):
    """
    Extended execution context for data mesh business rules.

    Adds data mesh-specific context:
    - domain: The data mesh domain being validated
    - asset: Optional asset associated with the domain
    """
    domain: Optional[DataMeshDomain] = None
    asset: Optional[Asset] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        base_dict = super().to_dict()
        base_dict.update({
            'domain_id': str(self.domain.id) if self.domain else None,
            'asset_id': str(self.asset.id) if self.asset else None,
        })
        return base_dict


@register_rule(
    rule_name="data_mesh_domain_validation",
    description="Validates data mesh domain structure, boundaries, ownership transfer, and policy conflicts",
    tags=["mesh", "domain", "validation"],
    priority=10,

    openspec_ref="specs/mesh-business-rules/spec.md",
)
class DataMeshBusinessRules(BusinessRules):
    """
    Business rules validator for data mesh domains.

    Extends BusinessRules base class with data mesh-specific validation:
    - Domain structure and definition
    - Ownership transfer rules
    - Domain boundaries structure
    - Policy conflict detection
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        enable_caching: bool = True,
        enable_metrics: bool = True,
        enable_tracing: bool = True,
        enable_logging: bool = True
    ):
        """
        Initialize DataMeshBusinessRules instance.

        Args:
            tenant_id: Optional tenant ID for tenant-specific validation
            user_id: Optional user ID for permission validation
            enable_caching: Enable result caching (default: True)
            enable_metrics: Enable Prometheus metrics (default: True)
            enable_tracing: Enable OpenTelemetry tracing (default: True)
            enable_logging: Enable structured logging (default: True)
        """
        super().__init__(
            tenant_id=tenant_id,
            user_id=user_id,
            enable_caching=enable_caching,
            enable_metrics=enable_metrics,
            enable_tracing=enable_tracing,
            enable_logging=enable_logging
        )

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "DataMeshBusinessRules"

    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates all data mesh validation checks.
        It can be called with a DataMeshRuleExecutionContext or a standard
        RuleExecutionContext. If a standard context is provided, it extracts
        domain and asset from kwargs or context.metadata.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - domain: DataMeshDomain instance (required)
                - asset: Optional Asset instance
                - validation_type: Optional validation type filter
                    ('structure', 'ownership', 'boundaries', 'policy_conflicts', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        # Extract domain and asset from context or kwargs
        if isinstance(context, DataMeshRuleExecutionContext):
            domain = context.domain
            asset = context.asset
        else:
            # Try to get from kwargs first
            domain = kwargs.get('domain')
            asset = kwargs.get('asset')

            # If not in kwargs, try to get from context.metadata or context.resource
            if not domain:
                if context and hasattr(context, 'resource') and isinstance(context.resource, DataMeshDomain):
                    domain = context.resource
                elif context and hasattr(context, 'metadata') and isinstance(context.metadata, dict):
                    domain = context.metadata.get('domain')

        if not domain:
            return ValidationResult(
                is_valid=False,
                errors=["Domain is required for validation"],
                details={"validation_type": kwargs.get('validation_type', 'all')}
            )

        validation_type = kwargs.get('validation_type', 'all')
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "domain_id": str(domain.id) if domain.id else None,
            "domain_name": domain.name if hasattr(domain, 'name') else None,
            "validation_type": validation_type,
        }

        # Perform validation based on type
        if validation_type in ('structure', 'all'):
            structure_result = self.validate_domain_structure(domain)
            if not structure_result.is_valid:
                errors.extend(structure_result.errors)
                warnings.extend(structure_result.warnings)
                details.update(structure_result.details)

        if validation_type in ('boundaries', 'all'):
            if hasattr(domain, 'boundaries') and domain.boundaries is not None:
                boundaries_result = self.validate_boundaries(domain.boundaries)
                if not boundaries_result.is_valid:
                    errors.extend(boundaries_result.errors)
                    warnings.extend(boundaries_result.warnings)
                    details.update(boundaries_result.details)

        if validation_type in ('ownership', 'all'):
            # Check if this is an ownership transfer validation (new_owner_id provided)
            new_owner_id = kwargs.get('new_owner_id')
            if new_owner_id is not None or (context and hasattr(context, 'metadata') and isinstance(context.metadata, dict) and context.metadata.get('new_owner_id') is not None):
                # Ownership transfer validation
                if new_owner_id is None and context and hasattr(context, 'metadata') and isinstance(context.metadata, dict):
                    new_owner_id = context.metadata.get('new_owner_id')

                ownership_result = self.validate_ownership_transfer(
                    domain=domain,
                    new_owner_id=new_owner_id,
                    raise_on_error=False
                )
            else:
                # Standard domain ownership validation
                ownership_result = self.validate_domain_ownership(domain)

            if not ownership_result.is_valid:
                errors.extend(ownership_result.errors)
                warnings.extend(ownership_result.warnings)
                details.update(ownership_result.details)

            # If asset is provided, validate asset ownership transfer
            if asset:
                asset_transfer_result = self.validate_asset_ownership_transfer(domain, asset)
                if not asset_transfer_result.is_valid:
                    errors.extend(asset_transfer_result.errors)
                    warnings.extend(asset_transfer_result.warnings)
                    details.update(asset_transfer_result.details)

        # Validate tenant context consistency
        if self.tenant_id and domain.tenant:
            if str(domain.tenant.id) != str(self.tenant_id):
                errors.append(
                    f"Tenant mismatch: domain tenant ({domain.tenant.id}) "
                    f"does not match context tenant ({self.tenant_id})"
                )

        is_valid = len(errors) == 0
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_domain_structure(
        self,
        domain: DataMeshDomain,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate domain structure and required fields.

        Validates:
        - Domain name is not empty
        - Domain has a tenant
        - Boundaries, capabilities, resource_quota, resource_usage are dicts if provided
        - Owner belongs to same tenant as domain

        Args:
            domain: DataMeshDomain instance to validate
            raise_on_error: If True, raises ValidationError on validation failure (default: False)

        Returns:
            ValidationResult with validation status, errors, and warnings

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "domain_id": str(domain.id) if domain.id else None,
            "domain_name": domain.name if hasattr(domain, 'name') else None,
        }

        # Validate name
        if not hasattr(domain, 'name') or not domain.name:
            errors.append("Domain name is required")
        elif not isinstance(domain.name, str) or not domain.name.strip():
            errors.append("Domain name cannot be empty or whitespace-only")

        # Validate tenant
        if not hasattr(domain, 'tenant') or domain.tenant is None:
            errors.append("Domain must have a tenant")
        elif self.tenant_id and str(domain.tenant.id) != self.tenant_id:
            errors.append(
                f"Domain tenant ({domain.tenant.id}) does not match expected tenant ({self.tenant_id})"
            )

        # Validate boundaries structure
        if hasattr(domain, 'boundaries') and domain.boundaries is not None:
            if not isinstance(domain.boundaries, dict):
                errors.append("Domain boundaries must be a dictionary/JSON object")
            else:
                # Additional boundaries validation is done in validate_boundaries()
                boundaries_result = self.validate_boundaries(domain.boundaries)
                if not boundaries_result.is_valid:
                    errors.extend(boundaries_result.errors)
                    warnings.extend(boundaries_result.warnings)

        # Validate capabilities structure
        if hasattr(domain, 'capabilities') and domain.capabilities is not None:
            if not isinstance(domain.capabilities, dict):
                errors.append("Domain capabilities must be a dictionary/JSON object")

        # Validate resource_quota structure
        if hasattr(domain, 'resource_quota') and domain.resource_quota is not None:
            if not isinstance(domain.resource_quota, dict):
                errors.append("Domain resource_quota must be a dictionary/JSON object")

        # Validate resource_usage structure
        if hasattr(domain, 'resource_usage') and domain.resource_usage is not None:
            if not isinstance(domain.resource_usage, dict):
                errors.append("Domain resource_usage must be a dictionary/JSON object")

        # Validate owner belongs to same tenant (owner_id set but user may not exist)
        if hasattr(domain, 'owner_id') and domain.owner_id is not None:
            try:
                owner = domain.owner
                if hasattr(domain, 'tenant') and domain.tenant is not None:
                    if owner.tenant != domain.tenant:
                        errors.append(
                            f"Domain owner must belong to the same tenant as the domain. "
                            f"Owner tenant: {owner.tenant.id}, Domain tenant: {domain.tenant.id}"
                        )
            except User.DoesNotExist:
                errors.append(
                    "Domain owner not found or does not belong to tenant"
                )

        # Validate status
        if hasattr(domain, 'status') and domain.status:
            valid_statuses = [choice[0] for choice in DomainStatus.choices]
            if domain.status not in valid_statuses:
                errors.append(
                    f"Invalid domain status '{domain.status}'. "
                    f"Valid statuses: {', '.join(valid_statuses)}"
                )

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if raise_on_error and not is_valid:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError("; ".join(errors))

        return result

    def validate_ownership_transfer(
        self,
        domain: DataMeshDomain,
        new_owner_id: Optional[str],
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate ownership transfer rules.

        Validates:
        - New owner exists (if provided)
        - New owner belongs to same tenant as domain
        - Domain is in a state that allows ownership transfer

        Args:
            domain: DataMeshDomain instance
            new_owner_id: Optional new owner user ID (None to remove owner)
            raise_on_error: If True, raises ValidationError on validation failure (default: False)

        Returns:
            ValidationResult with validation status, errors, and warnings

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "domain_id": str(domain.id),
            "domain_name": domain.name,
            "current_owner_id": str(domain.owner.id) if domain.owner else None,
            "new_owner_id": new_owner_id,
        }

        # If new_owner_id is None, removing owner is always valid
        if new_owner_id is None:
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=warnings,
                details=details
            )

        # Validate new_owner_id is non-empty and valid UUID format before DB lookup
        if not new_owner_id or not str(new_owner_id).strip():
            errors.append("New owner ID cannot be empty")
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                from hub.apps.core.services.base import ValidationError
                raise ValidationError("; ".join(errors))
            return result

        try:
            uuid.UUID(str(new_owner_id))
        except (ValueError, TypeError, AttributeError):
            errors.append(f"New owner ID '{new_owner_id}' is not a valid UUID format")
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                from hub.apps.core.services.base import ValidationError
                raise ValidationError("; ".join(errors))
            return result

        # Validate new owner exists
        try:
            new_owner = User.objects.get(id=new_owner_id)
        except User.DoesNotExist:
            errors.append(f"User with id '{new_owner_id}' not found")
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                from hub.apps.core.services.base import ValidationError
                raise ValidationError("; ".join(errors))
            return result

        details["new_owner_email"] = new_owner.email

        # Validate new owner belongs to same tenant as domain
        if domain.tenant and new_owner.tenant != domain.tenant:
            errors.append(
                f"New owner must belong to the same tenant as the domain. "
                f"Owner tenant: {new_owner.tenant.id}, Domain tenant: {domain.tenant.id}"
            )

        # Validate domain state allows ownership transfer
        # Archived domains might not allow ownership transfer
        if domain.status == DomainStatus.ARCHIVED:
            warnings.append(
                "Transferring ownership of an archived domain may have limited effect"
            )

        # Check if ownership is actually changing
        if domain.owner and str(domain.owner.id) == new_owner_id:
            warnings.append("New owner is the same as current owner (no-op transfer)")

        # Validate tenant context if provided
        if self.tenant_id:
            if domain.tenant and str(domain.tenant.id) != self.tenant_id:
                errors.append(
                    f"Domain tenant ({domain.tenant.id}) does not match validation context tenant ({self.tenant_id})"
                )
            if new_owner.tenant and str(new_owner.tenant.id) != self.tenant_id:
                errors.append(
                    f"New owner tenant ({new_owner.tenant.id}) does not match validation context tenant ({self.tenant_id})"
                )

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if raise_on_error and not is_valid:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError("; ".join(errors))

        return result

    def validate_boundaries(
        self,
        boundaries: Optional[Dict[str, Any]],
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate domain boundaries structure.

        Validates:
        - Boundaries is a dictionary if provided
        - Common boundary fields (data_products, schemas, access_patterns) are lists if present
        - Boundary structure is valid

        Args:
            boundaries: Boundaries dictionary to validate (None is valid)
            raise_on_error: If True, raises ValidationError on validation failure (default: False)

        Returns:
            ValidationResult with validation status, errors, and warnings

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # None boundaries are valid (optional field)
        if boundaries is None:
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                details=details
            )

        # Validate boundaries is a dict
        if not isinstance(boundaries, dict):
            errors.append("Boundaries must be a dictionary/JSON object")
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                from hub.apps.core.services.base import ValidationError
                raise ValidationError("; ".join(errors))
            return result

        details["boundaries_keys"] = list(boundaries.keys())

        # Validate common boundary fields if present
        # data_products should be a list
        if "data_products" in boundaries:
            if not isinstance(boundaries["data_products"], list):
                errors.append("boundaries.data_products must be a list")
            else:
                details["data_products_count"] = len(boundaries["data_products"])

        # schemas should be a list
        if "schemas" in boundaries:
            if not isinstance(boundaries["schemas"], list):
                errors.append("boundaries.schemas must be a list")
            else:
                details["schemas_count"] = len(boundaries["schemas"])

        # access_patterns should be a list
        if "access_patterns" in boundaries:
            if not isinstance(boundaries["access_patterns"], list):
                errors.append("boundaries.access_patterns must be a list")
            else:
                details["access_patterns_count"] = len(boundaries["access_patterns"])

        # Empty boundaries dict is valid
        if len(boundaries) == 0:
            warnings.append("Boundaries dictionary is empty")

        # Additional fields are allowed (flexible structure)
        # No validation errors for unknown fields

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if raise_on_error and not is_valid:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError("; ".join(errors))

        return result

    def validate_domain_boundary_definition(
        self,
        domain: DataMeshDomain,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate domain boundary definition including structure and overlap checks.

        Validates:
        - Boundary structure is valid (via validate_boundaries)
        - No overlaps with other domains' boundaries (data_products, schemas, access_patterns)
        - Boundary definitions are consistent

        Args:
            domain: DataMeshDomain instance to validate
            raise_on_error: If True, raises ValidationError on validation failure (default: False)

        Returns:
            ValidationResult with validation status, errors, warnings, and overlap details

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "domain_id": str(domain.id),
            "domain_name": domain.name,
            "overlaps": []
        }

        # First validate boundary structure
        boundaries_result = self.validate_boundaries(domain.boundaries)
        if not boundaries_result.is_valid:
            errors.extend(boundaries_result.errors)
            warnings.extend(boundaries_result.warnings)
            details.update(boundaries_result.details)

        # Check for overlaps with other domains in the same tenant
        if domain.boundaries and isinstance(domain.boundaries, dict):
            tenant_id = str(domain.tenant.id) if domain.tenant else None
            if tenant_id:
                # Get all other active domains in the same tenant
                other_domains = DataMeshDomain.objects.filter(
                    tenant_id=tenant_id,
                    status__in=[DomainStatus.ACTIVE, DomainStatus.INACTIVE]
                ).exclude(id=domain.id)

                # Check for overlaps in data_products
                if "data_products" in domain.boundaries and isinstance(domain.boundaries["data_products"], list):
                    domain_data_products = set(domain.boundaries["data_products"])
                    for other_domain in other_domains:
                        if other_domain.boundaries and isinstance(other_domain.boundaries, dict):
                            if "data_products" in other_domain.boundaries and isinstance(other_domain.boundaries["data_products"], list):
                                other_data_products = set(other_domain.boundaries["data_products"])
                                overlap = domain_data_products & other_data_products
                                if overlap:
                                    errors.append(
                                        f"Domain boundary overlap detected: data_products {list(overlap)} "
                                        f"are also defined in domain '{other_domain.name}'"
                                    )
                                    details["overlaps"].append({
                                        "type": "data_products",
                                        "overlapping_items": list(overlap),
                                        "conflicting_domain_id": str(other_domain.id),
                                        "conflicting_domain_name": other_domain.name
                                    })

                # Check for overlaps in schemas
                if "schemas" in domain.boundaries and isinstance(domain.boundaries["schemas"], list):
                    domain_schemas = set(domain.boundaries["schemas"])
                    for other_domain in other_domains:
                        if other_domain.boundaries and isinstance(other_domain.boundaries, dict):
                            if "schemas" in other_domain.boundaries and isinstance(other_domain.boundaries["schemas"], list):
                                other_schemas = set(other_domain.boundaries["schemas"])
                                overlap = domain_schemas & other_schemas
                                if overlap:
                                    errors.append(
                                        f"Domain boundary overlap detected: schemas {list(overlap)} "
                                        f"are also defined in domain '{other_domain.name}'"
                                    )
                                    details["overlaps"].append({
                                        "type": "schemas",
                                        "overlapping_items": list(overlap),
                                        "conflicting_domain_id": str(other_domain.id),
                                        "conflicting_domain_name": other_domain.name
                                    })

                # Check for overlaps in access_patterns
                if "access_patterns" in domain.boundaries and isinstance(domain.boundaries["access_patterns"], list):
                    domain_access_patterns = set(domain.boundaries["access_patterns"])
                    for other_domain in other_domains:
                        if other_domain.boundaries and isinstance(other_domain.boundaries, dict):
                            if "access_patterns" in other_domain.boundaries and isinstance(other_domain.boundaries["access_patterns"], list):
                                other_access_patterns = set(other_domain.boundaries["access_patterns"])
                                overlap = domain_access_patterns & other_access_patterns
                                if overlap:
                                    warnings.append(
                                        f"Domain boundary overlap detected: access_patterns {list(overlap)} "
                                        f"are also defined in domain '{other_domain.name}'. "
                                        f"This may be intentional for shared access patterns."
                                    )
                                    details["overlaps"].append({
                                        "type": "access_patterns",
                                        "overlapping_items": list(overlap),
                                        "conflicting_domain_id": str(other_domain.id),
                                        "conflicting_domain_name": other_domain.name
                                    })

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if raise_on_error and not is_valid:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError("; ".join(errors))

        return result

    def validate_asset_domain_boundary(
        self,
        asset: Asset,
        domain: DataMeshDomain,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate that an asset belongs to the domain's boundary.

        Validates:
        - Asset's domain field matches domain name
        - Asset belongs to the same tenant as domain
        - If domain has boundaries.data_products, asset should be listed (if applicable)

        Args:
            asset: Asset instance to validate
            domain: DataMeshDomain instance
            raise_on_error: If True, raises ValidationError on validation failure (default: False)

        Returns:
            ValidationResult with validation status, errors, and warnings

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "asset_id": str(asset.id),
            "asset_key": asset.key,
            "asset_domain": asset.domain,
            "domain_id": str(domain.id),
            "domain_name": domain.name
        }

        # Validate asset and domain belong to same tenant
        if asset.tenant != domain.tenant:
            errors.append(
                f"Asset tenant ({asset.tenant.id}) does not match domain tenant ({domain.tenant.id})"
            )
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                from hub.apps.core.services.base import ValidationError
                raise ValidationError("; ".join(errors))
            return result

        # Check if asset.domain matches domain.name
        if asset.domain:
            if asset.domain != domain.name:
                errors.append(
                    f"Asset domain '{asset.domain}' does not match domain name '{domain.name}'"
                )
            else:
                details["domain_match"] = True
        else:
            warnings.append(
                f"Asset has no domain set. Consider setting asset.domain to '{domain.name}'"
            )
            details["domain_match"] = None

        # If domain has boundaries.data_products, check if asset is listed
        if domain.boundaries and isinstance(domain.boundaries, dict):
            if "data_products" in domain.boundaries and isinstance(domain.boundaries["data_products"], list):
                data_products = domain.boundaries["data_products"]
                # Check if asset key or name is in data_products list
                asset_in_boundary = (
                    asset.key in data_products or
                    asset.name in data_products or
                    str(asset.id) in data_products
                )
                if not asset_in_boundary:
                    warnings.append(
                        f"Asset '{asset.key}' is not listed in domain boundaries.data_products. "
                        f"Consider adding it to maintain boundary consistency."
                    )
                    details["in_boundary_data_products"] = False
                else:
                    details["in_boundary_data_products"] = True

        # Validate tenant context if provided
        if self.tenant_id:
            if asset.tenant and str(asset.tenant.id) != self.tenant_id:
                errors.append(
                    f"Asset tenant ({asset.tenant.id}) does not match validation context tenant ({self.tenant_id})"
                )
            if domain.tenant and str(domain.tenant.id) != self.tenant_id:
                errors.append(
                    f"Domain tenant ({domain.tenant.id}) does not match validation context tenant ({self.tenant_id})"
                )

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if raise_on_error and not is_valid:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError("; ".join(errors))

        return result

    def validate_cross_domain_access(
        self,
        user_id: str,
        source_domain: DataMeshDomain,
        target_domain: DataMeshDomain,
        resource_type: str = "ASSET",
        resource_id: Optional[str] = None,
        access_type: str = "READ",
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate cross-domain access permissions and policies.

        Validates:
        - User has permission to access resources across domains
        - ABAC policies allow cross-domain access
        - Domains are in the same tenant
        - Access policies don't explicitly deny cross-domain access

        Args:
            user_id: User ID requesting access
            source_domain: Source domain (where user is coming from)
            target_domain: Target domain (where resource is located)
            resource_type: Resource type (ASSET, DATASET, etc.)
            resource_id: Optional resource ID to check specific resource access
            access_type: Access type (READ, WRITE, DOWNLOAD)
            raise_on_error: If True, raises ValidationError on validation failure (default: False)

        Returns:
            ValidationResult with validation status, errors, warnings, and policy details

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "user_id": user_id,
            "source_domain_id": str(source_domain.id),
            "source_domain_name": source_domain.name,
            "target_domain_id": str(target_domain.id),
            "target_domain_name": target_domain.name,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "access_type": access_type,
            "policy_evaluation": {}
        }

        # Validate domains belong to same tenant
        if source_domain.tenant != target_domain.tenant:
            errors.append(
                f"Cross-domain access between different tenants is not allowed. "
                f"Source domain tenant: {source_domain.tenant.id}, "
                f"Target domain tenant: {target_domain.tenant.id}"
            )
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                from hub.apps.core.services.base import ValidationError
                raise ValidationError("; ".join(errors))
            return result

        tenant_id = str(source_domain.tenant.id)

        # If same domain, access is always allowed (within domain)
        if source_domain.id == target_domain.id:
            details["same_domain"] = True
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                details=details
            )

        details["same_domain"] = False

        # Validate tenant context if provided
        if self.tenant_id:
            if str(source_domain.tenant.id) != self.tenant_id:
                errors.append(
                    f"Source domain tenant ({source_domain.tenant.id}) does not match validation context tenant ({self.tenant_id})"
                )
            if str(target_domain.tenant.id) != self.tenant_id:
                errors.append(
                    f"Target domain tenant ({target_domain.tenant.id}) does not match validation context tenant ({self.tenant_id})"
                )

        # Check domain status - archived domains may have restricted access
        # This check comes before resource_id check as domain status is more fundamental
        if target_domain.status == DomainStatus.ARCHIVED:
            warnings.append(
                f"Target domain '{target_domain.name}' is archived. "
                f"Cross-domain access to archived domains may be restricted."
            )

        # Check ABAC policies if resource_id is provided
        if resource_id:
            from hub.apps.governance.abac import ABACEngine

            try:
                policy_result = ABACEngine.evaluate_access(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    access_type=access_type
                )

                details["policy_evaluation"] = {
                    "allowed": policy_result.allowed,
                    "policy_id": str(policy_result.policy.id) if policy_result.policy else None,
                    "policy_name": policy_result.policy.name if policy_result.policy else None,
                    "masking_required": policy_result.masking_required
                }

                if not policy_result.allowed:
                    errors.append(
                        f"ABAC policy evaluation denied access. "
                        f"Policy: {policy_result.policy.name if policy_result.policy else 'Unknown'}"
                    )
                elif policy_result.masking_required:
                    warnings.append(
                        f"Access allowed but data masking is required per policy: "
                        f"{policy_result.policy.name if policy_result.policy else 'Unknown'}"
                    )
            except Exception as e:
                warnings.append(
                    f"Failed to evaluate ABAC policies: {str(e)}. "
                    f"Proceeding with basic validation."
                )
                details["policy_evaluation"]["error"] = str(e)
        else:
            warnings.append(
                "No resource_id provided. Only basic cross-domain validation performed. "
                "For full policy evaluation, provide resource_id."
            )

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if raise_on_error and not is_valid:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError("; ".join(errors))

        return result

    def validate_domain_resource_quota(
        self,
        domain: DataMeshDomain,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate domain resource quota against current usage.

        Validates:
        - Resource quota structure is valid
        - Resource usage doesn't exceed quota
        - Quota values are non-negative
        - Usage values are non-negative
        - Quota and usage keys are consistent

        Args:
            domain: DataMeshDomain instance to validate
            raise_on_error: If True, raises ValidationError on validation failure (default: False)

        Returns:
            ValidationResult with validation status, errors, warnings, and quota details

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "domain_id": str(domain.id),
            "domain_name": domain.name,
            "quota_exceeded": [],
            "quota_usage": {}
        }

        # Validate quota structure
        if domain.resource_quota:
            if not isinstance(domain.resource_quota, dict):
                errors.append("Domain resource_quota must be a dictionary/JSON object")
                result = ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )
                if raise_on_error:
                    from hub.apps.core.services.base import ValidationError
                    raise ValidationError("; ".join(errors))
                return result

            # Validate quota values are non-negative numbers
            for key, value in domain.resource_quota.items():
                if not isinstance(value, (int, float)):
                    errors.append(f"Resource quota '{key}' must be a number, got {type(value).__name__}")
                elif value < 0:
                    errors.append(f"Resource quota '{key}' cannot be negative, got {value}")

        # Validate usage structure
        if domain.resource_usage:
            if not isinstance(domain.resource_usage, dict):
                errors.append("Domain resource_usage must be a dictionary/JSON object")
                result = ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )
                if raise_on_error:
                    from hub.apps.core.services.base import ValidationError
                    raise ValidationError("; ".join(errors))
                return result

            # Validate usage values are non-negative numbers
            for key, value in domain.resource_usage.items():
                if not isinstance(value, (int, float)):
                    errors.append(f"Resource usage '{key}' must be a number, got {type(value).__name__}")
                elif value < 0:
                    errors.append(f"Resource usage '{key}' cannot be negative, got {value}")

        # Check quota vs usage
        if domain.resource_quota and domain.resource_usage:
            quota_dict = domain.resource_quota
            usage_dict = domain.resource_usage

            # Check each quota key
            for quota_key, quota_value in quota_dict.items():
                if not isinstance(quota_value, (int, float)) or quota_value < 0:
                    continue  # Already validated above

                # Find corresponding usage key (could be quota_key or quota_key + "_used")
                usage_key = quota_key
                if usage_key not in usage_dict:
                    usage_key = f"{quota_key}_used"

                usage_value = usage_dict.get(usage_key, 0)

                if not isinstance(usage_value, (int, float)):
                    continue  # Already validated above

                # Calculate usage percentage
                usage_percentage = (usage_value / quota_value * 100) if quota_value > 0 else 0
                details["quota_usage"][quota_key] = {
                    "quota": quota_value,
                    "usage": usage_value,
                    "usage_percentage": round(usage_percentage, 2),
                    "exceeded": usage_value > quota_value
                }

                # Check if quota is exceeded
                if usage_value > quota_value:
                    errors.append(
                        f"Resource quota exceeded for '{quota_key}': "
                        f"usage ({usage_value}) > quota ({quota_value})"
                    )
                    details["quota_exceeded"].append(quota_key)
                elif usage_percentage >= 90:
                    warnings.append(
                        f"Resource quota nearly exceeded for '{quota_key}': "
                        f"usage ({usage_value}) is {usage_percentage:.1f}% of quota ({quota_value})"
                    )
                elif usage_percentage >= 80:
                    warnings.append(
                        f"Resource quota usage is high for '{quota_key}': "
                        f"usage ({usage_value}) is {usage_percentage:.1f}% of quota ({quota_value})"
                    )

        # Check if domain has quota but no usage tracking
        if domain.resource_quota and not domain.resource_usage:
            warnings.append(
                "Domain has resource_quota defined but no resource_usage tracking. "
                "Consider initializing resource_usage to track actual usage."
            )

        # Integrate with GovernanceService for domain-level quota limits validation
        if domain.resource_quota and domain.tenant:
            try:
                from hub.apps.governance.services import GovernanceService
                from hub.apps.core.services.base import ValidationError as ServiceValidationError

                governance_service = GovernanceService(
                    tenant_id=str(domain.tenant.id),
                    user_id=self.user_id
                )

                # Validate domain quota against tenant-level limits via GovernanceService
                try:
                    validated_quota = governance_service.validate_resource_quota_allocation(
                        tenant_id=str(domain.tenant.id),
                        requested_quota=domain.resource_quota.copy()
                    )
                    details["governance_validation_passed"] = True
                    details["validated_quota"] = validated_quota

                    # Enforce tenant-level resource limits
                    governance_service.check_tenant_resource_limits(
                        tenant_id=str(domain.tenant.id),
                        requested_quota=validated_quota
                    )
                    details["tenant_limits_check_passed"] = True

                except ServiceValidationError as e:
                    # GovernanceService validation failed
                    error_message = str(e)
                    errors.append(
                        f"Domain resource quota validation failed via GovernanceService: {error_message}"
                    )
                    details["governance_validation_passed"] = False
                    details["governance_validation_error"] = error_message

                    # Determine which quota type was exceeded
                    if "storage" in error_message.lower() or "storage_gb" in error_message.lower():
                        details["quota_exceeded"].append("storage_gb")
                    elif "compute" in error_message.lower() or "compute_hours" in error_message.lower():
                        details["quota_exceeded"].append("compute_hours")

            except Exception as e:
                logger.warning(
                    f"Failed to validate domain resource quota via GovernanceService for domain {domain.id}: {e}",
                    exc_info=True
                )
                warnings.append(
                    f"Could not validate domain resource quota via GovernanceService: {str(e)}. "
                    f"Proceeding with local quota validation."
                )
                details["governance_service_error"] = str(e)
                details["governance_validation_passed"] = None

        # Validate tenant context if provided
        if self.tenant_id:
            if domain.tenant and str(domain.tenant.id) != self.tenant_id:
                errors.append(
                    f"Domain tenant ({domain.tenant.id}) does not match validation context tenant ({self.tenant_id})"
                )

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if raise_on_error and not is_valid:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError("; ".join(errors))

        return result

    def validate_domain_ownership(
        self,
        domain: DataMeshDomain,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate domain ownership - check if user has TENANT_ADMIN role.

        Validates:
        - User has TENANT_ADMIN role (required for domain operations)
        - User belongs to the same tenant as the domain (unless platform admin)
        - Domain exists and is accessible

        Args:
            domain: DataMeshDomain instance
            raise_on_error: If True, raises PermissionError on validation failure (default: False)

        Returns:
            ValidationResult with validation status, errors, and warnings

        Raises:
            PermissionError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "domain_id": str(domain.id),
            "domain_name": domain.name,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "ownership_checks": {}
        }

        if not self.user_id:
            errors.append("user_id is required for domain ownership validation")
            details["ownership_checks"]["user_id_provided"] = False
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                from hub.apps.core.services.base import PermissionError
                raise PermissionError("user_id is required for domain ownership validation")
            return result

        details["ownership_checks"]["user_id_provided"] = True

        # Get user
        try:
            user = User.objects.get(id=self.user_id)
        except User.DoesNotExist:
            errors.append(f"User with id '{self.user_id}' not found")
            details["ownership_checks"]["user_exists"] = False
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                from hub.apps.core.services.base import PermissionError
                raise PermissionError(f"User with id '{self.user_id}' not found")
            return result

        details["ownership_checks"]["user_exists"] = True
        details["user_email"] = user.email

        # Platform admins have all permissions (can operate on any tenant)
        if user.is_platform_admin:
            details["ownership_checks"]["is_platform_admin"] = True
            details["ownership_checks"]["has_tenant_admin_role"] = True
            details["ownership_checks"]["ownership_valid"] = True
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=warnings,
                details=details
            )

        details["ownership_checks"]["is_platform_admin"] = False

        # Validate user belongs to same tenant as domain
        if domain.tenant and user.tenant != domain.tenant:
            errors.append(
                f"User must belong to the same tenant as the domain. "
                f"User tenant: {user.tenant.id if user.tenant else None}, "
                f"Domain tenant: {domain.tenant.id}"
            )
            details["ownership_checks"]["tenant_match"] = False
        else:
            details["ownership_checks"]["tenant_match"] = True

        # Check if user has TENANT_ADMIN role
        has_tenant_admin_role = user.has_role("TENANT_ADMIN")
        details["ownership_checks"]["has_tenant_admin_role"] = has_tenant_admin_role

        if not has_tenant_admin_role:
            errors.append(
                f"User '{user.email}' does not have required role (TENANT_ADMIN) for domain operations. "
                f"Domain: {domain.name}"
            )
            details["ownership_checks"]["ownership_valid"] = False
        else:
            details["ownership_checks"]["ownership_valid"] = True

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if raise_on_error and not is_valid:
            from hub.apps.core.services.base import PermissionError
            raise PermissionError("; ".join(errors))

        return result

    def validate_asset_ownership_transfer(
        self,
        domain: DataMeshDomain,
        asset: Asset,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate asset ownership transfer to domain.

        Validates:
        - Asset exists and is accessible
        - Asset belongs to same tenant as domain
        - User has permission to transfer asset (TENANT_ADMIN role)
        - Asset dependencies are checked (no blocking dependencies)
        - Asset is in a valid state for transfer

        Args:
            domain: DataMeshDomain instance (target domain)
            asset: Asset instance to transfer
            raise_on_error: If True, raises ValidationError on validation failure (default: False)

        Returns:
            ValidationResult with validation status, errors, warnings, and dependency details

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "domain_id": str(domain.id),
            "domain_name": domain.name,
            "asset_id": str(asset.id),
            "asset_key": asset.key,
            "asset_name": asset.name,
            "transfer_checks": {}
        }

        # Validate domain ownership first (user must have TENANT_ADMIN role)
        ownership_result = self.validate_domain_ownership(domain, raise_on_error=False)
        if not ownership_result.is_valid:
            errors.extend(ownership_result.errors)
            details["transfer_checks"]["ownership_check_passed"] = False
            details["transfer_checks"]["ownership_errors"] = ownership_result.errors
        else:
            details["transfer_checks"]["ownership_check_passed"] = True

        # Validate asset belongs to same tenant as domain
        if asset.tenant != domain.tenant:
            errors.append(
                f"Asset '{asset.name}' must belong to the same tenant as the domain. "
                f"Asset tenant: {asset.tenant.id}, Domain tenant: {domain.tenant.id}"
            )
            details["transfer_checks"]["tenant_match"] = False
        else:
            details["transfer_checks"]["tenant_match"] = True

        # Validate asset is in a valid state for transfer
        from hub.apps.assets.models import AssetStatus
        valid_transfer_statuses = [AssetStatus.ACTIVE, AssetStatus.DRAFT, AssetStatus.PUBLIC]
        if asset.status not in valid_transfer_statuses:
            errors.append(
                f"Asset '{asset.name}' must be in ACTIVE, DRAFT, or PUBLIC status for transfer. "
                f"Current status: {asset.status}"
            )
            details["transfer_checks"]["asset_status_valid"] = False
        else:
            details["transfer_checks"]["asset_status_valid"] = True

        # Check asset dependencies
        # Get upstream and downstream dependencies
        try:
            from hub.apps.assets.dependencies import AssetDependencyService

            # Get upstream dependencies (assets this asset depends on)
            upstream_graph = AssetDependencyService.generate_dependency_graph(
                asset_id=str(asset.id),
                tenant_id=str(domain.tenant.id),
                direction="upstream",
                max_depth=10,
                include_metadata=True
            )

            # Get downstream dependencies (assets that depend on this asset)
            downstream_graph = AssetDependencyService.generate_dependency_graph(
                asset_id=str(asset.id),
                tenant_id=str(domain.tenant.id),
                direction="downstream",
                max_depth=10,
                include_metadata=True
            )

            upstream_count = len(upstream_graph.nodes) - 1  # Exclude self
            downstream_count = len(downstream_graph.nodes) - 1  # Exclude self

            details["transfer_checks"]["upstream_dependencies_count"] = upstream_count
            details["transfer_checks"]["downstream_dependencies_count"] = downstream_count
            details["transfer_checks"]["has_dependencies"] = upstream_count > 0 or downstream_count > 0

            # Check if any dependencies are in different domains
            # This is a warning, not an error - cross-domain dependencies are allowed
            if upstream_count > 0 or downstream_count > 0:
                warnings.append(
                    f"Asset '{asset.name}' has dependencies: "
                    f"{upstream_count} upstream, {downstream_count} downstream. "
                    f"Transferring to domain '{domain.name}' may affect dependency relationships."
                )

        except Exception as e:
            logger.warning(
                f"Failed to check asset dependencies for asset {asset.id}: {e}",
                exc_info=True
            )
            warnings.append(
                f"Could not fully validate asset dependencies: {str(e)}. "
                f"Proceeding with transfer validation."
            )
            details["transfer_checks"]["dependency_check_error"] = str(e)

        # Check if asset is already in this domain
        if hasattr(asset, 'domain') and asset.domain:
            if str(asset.domain.id) == str(domain.id):
                warnings.append(
                    f"Asset '{asset.name}' is already in domain '{domain.name}' (no-op transfer)"
                )
                details["transfer_checks"]["already_in_domain"] = True
            else:
                details["transfer_checks"]["already_in_domain"] = False
                details["transfer_checks"]["current_domain_id"] = str(asset.domain.id)
        else:
            details["transfer_checks"]["already_in_domain"] = False
            details["transfer_checks"]["current_domain_id"] = None

        # Validate tenant context if provided
        if self.tenant_id:
            if domain.tenant and str(domain.tenant.id) != self.tenant_id:
                errors.append(
                    f"Domain tenant ({domain.tenant.id}) does not match validation context tenant ({self.tenant_id})"
                )
            if asset.tenant and str(asset.tenant.id) != self.tenant_id:
                errors.append(
                    f"Asset tenant ({asset.tenant.id}) does not match validation context tenant ({self.tenant_id})"
                )

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if raise_on_error and not is_valid:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError("; ".join(errors))

        return result

    def validate_policy_conflicts(
        self,
        domain: DataMeshDomain,
        new_policy: "AccessPolicy",
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate policy conflicts when applying a new policy to a domain.

        Detects conflicts with existing applied policies:
        - Effect conflicts (ALLOW vs DENY with overlapping conditions)
        - Condition overlaps that could create ambiguity
        - Priority conflicts
        - Considers policy overrides in PolicyApplication
        - Integrates with GovernanceService for policy checks

        Args:
            domain: DataMeshDomain instance
            new_policy: AccessPolicy instance to be applied
            raise_on_error: If True, raises ValidationError on validation failure (default: False)

        Returns:
            ValidationResult with validation status, errors, warnings, and conflict details

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "domain_id": str(domain.id),
            "domain_name": domain.name,
            "new_policy_id": str(new_policy.id),
            "new_policy_name": new_policy.name,
            "conflicts": []
        }

        # Import here to avoid circular dependencies
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.governance.services import GovernanceService
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Integrate with GovernanceService for policy validation
        governance_service = GovernanceService(
            tenant_id=str(domain.tenant.id) if domain.tenant else self.tenant_id,
            user_id=self.user_id
        )

        # Get all APPLIED policies for the domain
        applied_policy_applications = PolicyApplication.objects.filter(
            domain=domain,
            status=PolicyApplicationStatus.APPLIED
        ).select_related('policy')

        # Get all policies applied to this domain (any status) to exclude from tenant-wide check
        domain_applied_policy_ids = PolicyApplication.objects.filter(
            domain=domain
        ).values_list('policy_id', flat=True)

        # Also get tenant-wide policies that might apply (inheritance)
        # Exclude policies that are already applied to this domain (regardless of status)
        # Also exclude the new policy being validated (don't check against itself)
        tenant_wide_policies = []
        if domain.tenant:
            exclude_ids = list(domain_applied_policy_ids) + [new_policy.id]
            tenant_wide_policies = AccessPolicy.objects.filter(
                tenant_id=domain.tenant.id,
                enabled=True,
                asset__isnull=True,
                dataset__isnull=True
            ).exclude(id__in=exclude_ids).order_by('priority')

        # Filter only enabled policies from domain applications
        existing_policies = []
        for app in applied_policy_applications:
            if app.policy and app.policy.enabled:
                existing_policies.append({
                    "policy": app.policy,
                    "application": app,
                    "effective_effect": app.overrides.get("effect", app.policy.effect) if isinstance(app.overrides, dict) else app.policy.effect,
                    "effective_priority": app.overrides.get("priority", app.policy.priority) if isinstance(app.overrides, dict) else app.policy.priority,
                    "overrides": app.overrides if isinstance(app.overrides, dict) else {},
                    "source": "domain"
                })

        # Add tenant-wide policies (inherited policies)
        for policy in tenant_wide_policies:
            existing_policies.append({
                "policy": policy,
                "application": None,
                "effective_effect": policy.effect,
                "effective_priority": policy.priority,
                "overrides": {},
                "source": "tenant"
            })

        # Check for conflicts with each existing policy
        for existing in existing_policies:
            existing_policy = existing["policy"]
            existing_effect = existing["effective_effect"]
            existing_priority = existing["effective_priority"]
            new_effect = new_policy.effect
            new_priority = new_policy.priority

            # Check if conditions overlap
            overlap_result = self._check_condition_overlap_detailed(
                existing_policy.conditions, new_policy.conditions
            )

            if overlap_result["overlaps"]:
                # Conditions overlap - check for effect conflicts
                if existing_effect != new_effect:
                    # Conflicting effects with overlapping conditions
                    conflict_info = {
                        "existing_policy_id": str(existing_policy.id),
                        "existing_policy_name": existing_policy.name,
                        "existing_effect": existing_effect,
                        "existing_priority": existing_priority,
                        "new_effect": new_effect,
                        "new_priority": new_priority,
                        "conflict_type": "EFFECT_CONFLICT",
                        "overlapping_conditions": overlap_result["overlapping_keys"],
                        "policy_source": existing["source"]
                    }

                    # Check priority resolution with precedence rules
                    precedence_result = self._resolve_policy_precedence(
                        existing_priority, new_priority, existing["source"]
                    )
                    conflict_info["precedence"] = precedence_result

                    if precedence_result["resolution"] == "EXISTING_HIGHER":
                        # Existing has higher priority - might be acceptable but warn
                        warnings.append(
                            f"Policy '{new_policy.name}' ({new_effect}) conflicts with higher priority "
                            f"policy '{existing_policy.name}' ({existing_effect}) from {existing['source']}. "
                            f"Existing policy will take precedence."
                        )
                        conflict_info["priority_resolution"] = "EXISTING_HIGHER"
                    elif precedence_result["resolution"] == "NEW_HIGHER":
                        # New has higher priority - will override existing
                        errors.append(
                            f"Policy '{new_policy.name}' ({new_effect}) conflicts with existing "
                            f"policy '{existing_policy.name}' ({existing_effect}) from {existing['source']} "
                            f"with overlapping conditions. "
                            f"New policy has higher priority and will override existing policy."
                        )
                        conflict_info["priority_resolution"] = "NEW_HIGHER"
                    else:
                        # Same priority - definite conflict
                        errors.append(
                            f"Policy '{new_policy.name}' ({new_effect}) conflicts with existing "
                            f"policy '{existing_policy.name}' ({existing_effect}) from {existing['source']} "
                            f"with same priority and overlapping conditions. "
                            f"This creates ambiguous access control."
                        )
                        conflict_info["priority_resolution"] = "SAME_PRIORITY"

                    details["conflicts"].append(conflict_info)
                else:
                    # Same effect but overlapping conditions - might be redundant
                    if existing_priority == new_priority:
                        warnings.append(
                            f"Policy '{new_policy.name}' has overlapping conditions with existing "
                            f"policy '{existing_policy.name}' from {existing['source']} with same effect and priority. "
                            f"This may be redundant."
                        )

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if raise_on_error and not is_valid:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError("; ".join(errors))

        return result

    def validate_policy_compatibility(
        self,
        domain: DataMeshDomain,
        new_policy: "AccessPolicy",
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate policy compatibility (policies don't conflict).

        This is a convenience method that checks if policies are compatible
        without raising errors for conflicts. It focuses on compatibility rather
        than conflict detection. Policies are considered compatible if they
        don't have conflicting effects with overlapping conditions.

        Args:
            domain: DataMeshDomain instance
            new_policy: AccessPolicy instance to be checked
            raise_on_error: If True, raises ValidationError on validation failure (default: False)

        Returns:
            ValidationResult with compatibility status
        """
        # Use conflict detection but treat only errors as incompatibility
        # Warnings (like redundant policies) don't make policies incompatible
        conflict_result = self.validate_policy_conflicts(domain, new_policy, raise_on_error=False)

        # Policies are compatible if there are no errors (conflicts)
        # Warnings (like redundant policies or priority warnings) don't make them incompatible
        is_compatible = conflict_result.is_valid

        result = ValidationResult(
            is_valid=is_compatible,
            errors=conflict_result.errors,
            warnings=conflict_result.warnings,
            details={
                **conflict_result.details,
                "compatible": is_compatible
            }
        )

        if raise_on_error and not is_compatible:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError("Policy compatibility check failed")

        return result

    def _resolve_policy_precedence(
        self,
        existing_priority: int,
        new_priority: int,
        existing_source: str
    ) -> Dict[str, Any]:
        """
        Resolve policy precedence based on priority and inheritance rules.

        Precedence rules:
        1. Lower priority number = higher priority
        2. Domain-specific policies override tenant-wide policies (same priority)
        3. Explicit policies override inherited policies

        Args:
            existing_priority: Priority of existing policy
            new_priority: Priority of new policy
            existing_source: Source of existing policy ("domain" or "tenant")

        Returns:
            Dictionary with precedence resolution details
        """
        if existing_priority < new_priority:
            return {
                "resolution": "EXISTING_HIGHER",
                "reason": f"Existing policy has higher priority ({existing_priority} < {new_priority})"
            }
        elif existing_priority > new_priority:
            return {
                "resolution": "NEW_HIGHER",
                "reason": f"New policy has higher priority ({new_priority} < {existing_priority})"
            }
        else:
            # Same priority - domain policies override tenant policies
            if existing_source == "tenant":
                return {
                    "resolution": "NEW_HIGHER",
                    "reason": "Domain-specific policy overrides tenant-wide policy at same priority"
                }
            else:
                return {
                    "resolution": "SAME_PRIORITY",
                    "reason": "Both policies have same priority and source - ambiguous"
                }

    def _check_condition_overlap_detailed(
        self,
        conditions1: Dict[str, Any],
        conditions2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check if two policy conditions overlap with detailed information.

        Returns detailed overlap information including which keys overlap.

        Args:
            conditions1: First policy conditions dictionary
            conditions2: Second policy conditions dictionary

        Returns:
            Dictionary with overlap status and details
        """
        overlaps = False
        overlapping_keys = []

        if not isinstance(conditions1, dict) or not isinstance(conditions2, dict):
            return {
                "overlaps": False,
                "overlapping_keys": [],
                "details": {}
            }

        # Check for overlapping keys with matching values
        for key, value1 in conditions1.items():
            if key in conditions2:
                value2 = conditions2[key]
                overlap_detail = self._check_value_overlap(value1, value2)

                if overlap_detail["overlaps"]:
                    overlaps = True
                    overlap_info = {
                        "key": key,
                        "value1": value1,
                        "value2": value2,
                        "overlap_type": overlap_detail["type"]
                    }
                    # Include overlap_values if present (for LIST_INTERSECTION)
                    if "overlap_values" in overlap_detail:
                        overlap_info["overlap_values"] = overlap_detail["overlap_values"]
                    overlapping_keys.append(overlap_info)

        # Also check nested structures (user, resource, environment)
        for section in ["user", "resource", "environment"]:
            if section in conditions1 and section in conditions2:
                section_overlap = self._check_condition_overlap_detailed(
                    conditions1[section], conditions2[section]
                )
                if section_overlap["overlaps"]:
                    overlaps = True
                    overlapping_keys.extend([
                        {**key_info, "section": section}
                        for key_info in section_overlap["overlapping_keys"]
                    ])

        return {
            "overlaps": overlaps,
            "overlapping_keys": overlapping_keys,
            "details": {
                "total_overlaps": len(overlapping_keys)
            }
        }

    def _check_value_overlap(
        self,
        value1: Any,
        value2: Any
    ) -> Dict[str, Any]:
        """
        Check if two values overlap (could match the same attributes).

        Args:
            value1: First value
            value2: Second value

        Returns:
            Dictionary with overlap status and type
        """
        # Handle list values (e.g., user_roles)
        if isinstance(value1, list) and isinstance(value2, list):
            overlap_set = set(value1) & set(value2)
            return {
                "overlaps": len(overlap_set) > 0,
                "type": "LIST_INTERSECTION",
                "overlap_values": list(overlap_set)
            }
        elif isinstance(value1, list):
            # value2 is not a list - check if it's in value1
            return {
                "overlaps": value2 in value1,
                "type": "VALUE_IN_LIST"
            }
        elif isinstance(value2, list):
            # value1 is not a list - check if it's in value2
            return {
                "overlaps": value1 in value2,
                "type": "VALUE_IN_LIST"
            }
        elif isinstance(value1, dict) and isinstance(value2, dict):
            # Nested dict - recursively check overlap
            nested_overlap = self._check_condition_overlap_detailed(value1, value2)
            return {
                "overlaps": nested_overlap["overlaps"],
                "type": "NESTED_DICT",
                "nested_details": nested_overlap
            }
        elif value1 == value2:
            # Exact match
            return {
                "overlaps": True,
                "type": "EXACT_MATCH"
            }
        else:
            return {
                "overlaps": False,
                "type": "NO_MATCH"
            }

    def _conditions_overlap(self, conditions1: Dict[str, Any], conditions2: Dict[str, Any]) -> bool:
        """
        Check if two policy conditions overlap.

        Conditions overlap if they could match the same set of attributes.
        This method uses the detailed overlap check for consistency.

        Args:
            conditions1: First policy conditions dictionary
            conditions2: Second policy conditions dictionary

        Returns:
            True if conditions overlap, False otherwise
        """
        result = self._check_condition_overlap_detailed(conditions1, conditions2)
        return result["overlaps"]


class PolicyBusinessRules(BusinessRules):
    """
    Business rules for policy application and compliance checking.

    Provides validation and compliance logic for:
    - Policy application validation
    - Compliance checking
    - Violation detection
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        enable_caching: bool = True,
        enable_metrics: bool = True,
        enable_tracing: bool = True,
        enable_logging: bool = True
    ):
        """
        Initialize PolicyBusinessRules instance.

        Args:
            tenant_id: Optional tenant ID for tenant-specific validation
            user_id: Optional user ID for permission validation
            enable_caching: Enable result caching (default: True)
            enable_metrics: Enable Prometheus metrics (default: True)
            enable_tracing: Enable OpenTelemetry tracing (default: True)
            enable_logging: Enable structured logging (default: True)
        """
        super().__init__(
            tenant_id=tenant_id,
            user_id=user_id,
            enable_caching=enable_caching,
            enable_metrics=enable_metrics,
            enable_tracing=enable_tracing,
            enable_logging=enable_logging
        )

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "PolicyBusinessRules"

    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates policy validation checks.
        It can be called with domain and policy in kwargs or context.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - domain: DataMeshDomain instance (required)
                - policy: AccessPolicy instance (optional, for policy application validation)

        Returns:
            ValidationResult with validation status and details
        """
        # Extract domain and policy from context or kwargs
        domain = kwargs.get('domain')
        policy = kwargs.get('policy')

        if context and hasattr(context, 'resource') and isinstance(context.resource, DataMeshDomain):
            domain = domain or context.resource
        elif context and hasattr(context, 'metadata') and isinstance(context.metadata, dict):
            domain = domain or context.metadata.get('domain')
            policy = policy or context.metadata.get('policy')

        if not domain:
            return ValidationResult(
                is_valid=False,
                errors=["Domain is required for policy validation"],
                details={"validation_type": "policy"}
            )

        # If policy is provided, validate policy application
        if policy:
            result = self.validate_policy_application(domain, policy, kwargs.get('overrides'))
            # Ensure validation_type is set in details
            if 'validation_type' not in result.details:
                result.details['validation_type'] = 'policy'
            return result

        # Otherwise, perform basic domain validation
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "domain_id": str(domain.id) if domain.id else None,
            "domain_name": domain.name if hasattr(domain, 'name') else None,
            "validation_type": "policy"
        }

        # Basic domain validation
        if domain.status != DomainStatus.ACTIVE:
            warnings.append(f"Domain '{domain.name}' is not ACTIVE")

        # Validate tenant context consistency
        if self.tenant_id and domain.tenant:
            if str(domain.tenant.id) != str(self.tenant_id):
                errors.append(
                    f"Tenant mismatch: domain tenant ({domain.tenant.id}) "
                    f"does not match context tenant ({self.tenant_id})"
                )

        is_valid = len(errors) == 0
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_policy_application(
        self,
        domain: DataMeshDomain,
        policy: "AccessPolicy",
        overrides: Optional[Dict[str, Any]] = None,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate policy application rules.

        Validates:
        - Domain is active
        - Policy is enabled
        - Domain and policy belong to same tenant
        - Overrides structure is valid
        - User has permission to apply policy

        Args:
            domain: DataMeshDomain instance
            policy: AccessPolicy instance to apply
            overrides: Optional policy overrides dictionary
            raise_on_error: If True, raises ValidationError on validation failure (default: False)

        Returns:
            ValidationResult with validation status, errors, and warnings

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "domain_id": str(domain.id),
            "domain_name": domain.name,
            "policy_id": str(policy.id),
            "policy_name": policy.name,
        }

        # Validate domain is active
        if domain.status != DomainStatus.ACTIVE:
            errors.append(
                f"Domain must be ACTIVE to apply policies. Current status: {domain.status}"
            )

        # Validate policy is enabled
        if not policy.enabled:
            errors.append(f"Policy '{policy.name}' is disabled and cannot be applied")

        # Validate domain and policy belong to same tenant
        if policy.tenant_id != domain.tenant_id:
            errors.append(
                f"Policy must belong to the same tenant as the domain. "
                f"Policy tenant: {policy.tenant_id}, Domain tenant: {domain.tenant_id}"
            )

        # Validate tenant context if provided
        if self.tenant_id:
            if str(domain.tenant_id) != self.tenant_id:
                errors.append(
                    f"Domain tenant ({domain.tenant_id}) does not match validation context tenant ({self.tenant_id})"
                )
            if str(policy.tenant_id) != self.tenant_id:
                errors.append(
                    f"Policy tenant ({policy.tenant_id}) does not match validation context tenant ({self.tenant_id})"
                )

        # Validate overrides structure
        overrides_dict = overrides or {}
        if not isinstance(overrides_dict, dict):
            errors.append("Overrides must be a dictionary")
        else:
            # Validate override keys are valid
            valid_override_keys = ["conditions", "effect", "priority", "expires_at"]
            for key in overrides_dict.keys():
                if key not in valid_override_keys:
                    warnings.append(f"Unknown override key '{key}' (allowed: {', '.join(valid_override_keys)})")

        # Check for existing policy application
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus
        existing_app = PolicyApplication.objects.filter(
            domain=domain,
            policy=policy,
            status=PolicyApplicationStatus.APPLIED
        ).first()
        if existing_app:
            warnings.append(
                f"Policy '{policy.name}' is already applied to domain '{domain.name}' "
                f"(application ID: {existing_app.id})"
            )

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if raise_on_error and not is_valid:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError("; ".join(errors))

        return result

    def check_compliance(
        self,
        domain: DataMeshDomain,
        asset: Optional["Asset"] = None,
    ) -> Dict[str, Any]:
        """
        Check compliance for a domain.

        This method performs compliance checking logic without creating a report.
        It returns compliance status and violations for use by services.

        Args:
            domain: DataMeshDomain instance
            asset: Optional Asset instance for asset-specific compliance check

        Returns:
            Dictionary with keys:
                - compliance_status: MeshComplianceStatus value
                - violations: List of violation dictionaries
        """
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus, MeshComplianceStatus
        from hub.apps.assets.models import Asset as AssetModel

        violations = []
        compliance_status = MeshComplianceStatus.COMPLIANT

        # Check domain-level compliance
        if domain.status != DomainStatus.ACTIVE:
            violations.append({
                "type": "DOMAIN_INACTIVE",
                "severity": "HIGH",
                "description": f"Domain {domain.name} is not active",
                "domain_id": str(domain.id)
            })
            compliance_status = MeshComplianceStatus.NON_COMPLIANT

        # Retrieve all applied policies for the domain
        applied_policies = PolicyApplication.objects.filter(
            domain=domain,
            status=PolicyApplicationStatus.APPLIED
        ).select_related('policy')

        # Check policy compliance
        for policy_app in applied_policies:
            policy = policy_app.policy
            if not policy:
                violations.append({
                    "type": "POLICY_MISSING",
                    "severity": "MEDIUM",
                    "description": f"Policy application {policy_app.id} references missing policy",
                    "policy_application_id": str(policy_app.id)
                })
                if compliance_status == MeshComplianceStatus.COMPLIANT:
                    compliance_status = MeshComplianceStatus.PARTIAL
                continue

            # Check if policy is enabled
            if not policy.enabled:
                violations.append({
                    "type": "POLICY_DISABLED",
                    "severity": "MEDIUM",
                    "description": f"Applied policy {policy.name} is disabled",
                    "policy_application_id": str(policy_app.id),
                    "policy_id": str(policy.id)
                })
                if compliance_status == MeshComplianceStatus.COMPLIANT:
                    compliance_status = MeshComplianceStatus.PARTIAL

            # Check policy expiration (if applicable)
            if hasattr(policy_app, 'expires_at') and policy_app.expires_at:
                from django.utils import timezone
                if policy_app.expires_at < timezone.now():
                    violations.append({
                        "type": "POLICY_EXPIRED",
                        "severity": "HIGH",
                        "description": f"Policy {policy.name} has expired",
                        "policy_application_id": str(policy_app.id),
                        "policy_id": str(policy.id),
                        "expires_at": policy_app.expires_at.isoformat()
                    })
                    compliance_status = MeshComplianceStatus.NON_COMPLIANT

        # Validate assets if asset provided or check domain assets
        if asset:
            # Asset-specific compliance check
            if asset.status not in ["ACTIVE", "PUBLIC"]:
                violations.append({
                    "type": "ASSET_INACTIVE",
                    "severity": "MEDIUM",
                    "description": f"Asset {asset.name} is not active or public",
                    "asset_id": str(asset.id),
                    "asset_status": asset.status
                })
                if compliance_status == MeshComplianceStatus.COMPLIANT:
                    compliance_status = MeshComplianceStatus.PARTIAL

            if asset.compliance_status == "FAIL":
                violations.append({
                    "type": "ASSET_COMPLIANCE_FAIL",
                    "severity": "HIGH",
                    "description": f"Asset {asset.name} has compliance failures",
                    "asset_id": str(asset.id)
                })
                compliance_status = MeshComplianceStatus.NON_COMPLIANT
            elif asset.compliance_status == "WARN":
                violations.append({
                    "type": "ASSET_COMPLIANCE_WARN",
                    "severity": "MEDIUM",
                    "description": f"Asset {asset.name} has compliance warnings",
                    "asset_id": str(asset.id)
                })
                if compliance_status == MeshComplianceStatus.COMPLIANT:
                    compliance_status = MeshComplianceStatus.PARTIAL
        else:
            # Domain-level asset validation
            domain_assets = AssetModel.objects.filter(
                tenant_id=domain.tenant_id,
                domain=domain.name
            )

            failed_assets = domain_assets.filter(compliance_status="FAIL")
            if failed_assets.exists():
                violations.append({
                    "type": "DOMAIN_ASSETS_COMPLIANCE_FAIL",
                    "severity": "HIGH",
                    "description": f"Domain has {failed_assets.count()} assets with compliance failures",
                    "failed_asset_count": failed_assets.count(),
                    "failed_asset_ids": [str(a.id) for a in failed_assets[:10]]
                })
                compliance_status = MeshComplianceStatus.NON_COMPLIANT

            warned_assets = domain_assets.filter(compliance_status="WARN")
            if warned_assets.exists() and compliance_status == MeshComplianceStatus.COMPLIANT:
                violations.append({
                    "type": "DOMAIN_ASSETS_COMPLIANCE_WARN",
                    "severity": "MEDIUM",
                    "description": f"Domain has {warned_assets.count()} assets with compliance warnings",
                    "warned_asset_count": warned_assets.count()
                })
                compliance_status = MeshComplianceStatus.PARTIAL

        return {
            "compliance_status": compliance_status,
            "violations": violations
        }

    def detect_violations(
        self,
        domain: DataMeshDomain,
        asset: Optional["Asset"] = None,
    ) -> List[Dict[str, Any]]:
        """
        Detect violations for a domain.

        This method focuses solely on violation detection without determining
        overall compliance status. Useful for detailed violation reporting.

        Args:
            domain: DataMeshDomain instance
            asset: Optional Asset instance for asset-specific violation detection

        Returns:
            List of violation dictionaries, each with:
                - type: Violation type (e.g., "DOMAIN_INACTIVE", "POLICY_DISABLED")
                - severity: Violation severity ("HIGH", "MEDIUM", "LOW")
                - description: Human-readable description
                - Additional context fields (domain_id, policy_id, etc.)
        """
        violations = []

        # Domain-level violations
        if domain.status != DomainStatus.ACTIVE:
            violations.append({
                "type": "DOMAIN_INACTIVE",
                "severity": "HIGH",
                "description": f"Domain {domain.name} is not active",
                "domain_id": str(domain.id),
                "domain_status": domain.status
            })

        # Policy violations
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus
        applied_policies = PolicyApplication.objects.filter(
            domain=domain,
            status=PolicyApplicationStatus.APPLIED
        ).select_related('policy')

        for policy_app in applied_policies:
            policy = policy_app.policy
            if not policy:
                violations.append({
                    "type": "POLICY_MISSING",
                    "severity": "MEDIUM",
                    "description": f"Policy application {policy_app.id} references missing policy",
                    "policy_application_id": str(policy_app.id)
                })
                continue

            if not policy.enabled:
                violations.append({
                    "type": "POLICY_DISABLED",
                    "severity": "MEDIUM",
                    "description": f"Applied policy {policy.name} is disabled",
                    "policy_application_id": str(policy_app.id),
                    "policy_id": str(policy.id),
                    "policy_name": policy.name
                })

            if hasattr(policy_app, 'expires_at') and policy_app.expires_at:
                from django.utils import timezone
                if policy_app.expires_at < timezone.now():
                    violations.append({
                        "type": "POLICY_EXPIRED",
                        "severity": "HIGH",
                        "description": f"Policy {policy.name} has expired",
                        "policy_application_id": str(policy_app.id),
                        "policy_id": str(policy.id),
                        "policy_name": policy.name,
                        "expires_at": policy_app.expires_at.isoformat()
                    })

        # Asset violations
        if asset:
            if asset.status not in ["ACTIVE", "PUBLIC"]:
                violations.append({
                    "type": "ASSET_INACTIVE",
                    "severity": "MEDIUM",
                    "description": f"Asset {asset.name} is not active or public",
                    "asset_id": str(asset.id),
                    "asset_name": asset.name,
                    "asset_status": asset.status
                })

            if asset.compliance_status == "FAIL":
                violations.append({
                    "type": "ASSET_COMPLIANCE_FAIL",
                    "severity": "HIGH",
                    "description": f"Asset {asset.name} has compliance failures",
                    "asset_id": str(asset.id),
                    "asset_name": asset.name
                })
            elif asset.compliance_status == "WARN":
                violations.append({
                    "type": "ASSET_COMPLIANCE_WARN",
                    "severity": "MEDIUM",
                    "description": f"Asset {asset.name} has compliance warnings",
                    "asset_id": str(asset.id),
                    "asset_name": asset.name
                })
        else:
            # Domain-level asset violations
            from hub.apps.assets.models import Asset as AssetModel
            domain_assets = AssetModel.objects.filter(
                tenant_id=domain.tenant_id,
                domain=domain.name
            )

            failed_assets = domain_assets.filter(compliance_status="FAIL")
            if failed_assets.exists():
                violations.append({
                    "type": "DOMAIN_ASSETS_COMPLIANCE_FAIL",
                    "severity": "HIGH",
                    "description": f"Domain has {failed_assets.count()} assets with compliance failures",
                    "failed_asset_count": failed_assets.count(),
                    "failed_asset_ids": [str(a.id) for a in failed_assets[:10]]
                })

            warned_assets = domain_assets.filter(compliance_status="WARN")
            if warned_assets.exists():
                violations.append({
                    "type": "DOMAIN_ASSETS_COMPLIANCE_WARN",
                    "severity": "MEDIUM",
                    "description": f"Domain has {warned_assets.count()} assets with compliance warnings",
                    "warned_asset_count": warned_assets.count()
                })

        return violations


class TopologyBusinessRules(BusinessRules):
    """
    Business rules for topology calculation and health metrics.

    Provides logic for:
    - Relationship calculation between domains
    - Health metrics calculation for domains
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        enable_caching: bool = True,
        enable_metrics: bool = True,
        enable_tracing: bool = True,
        enable_logging: bool = True
    ):
        """
        Initialize TopologyBusinessRules instance.

        Args:
            tenant_id: Optional tenant ID for tenant-specific calculations
            user_id: Optional user ID (not used but required for base class compatibility)
            enable_caching: Enable result caching (default: True)
            enable_metrics: Enable Prometheus metrics (default: True)
            enable_tracing: Enable OpenTelemetry tracing (default: True)
            enable_logging: Enable structured logging (default: True)
        """
        super().__init__(
            tenant_id=tenant_id,
            user_id=user_id,
            enable_caching=enable_caching,
            enable_metrics=enable_metrics,
            enable_tracing=enable_tracing,
            enable_logging=enable_logging
        )

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "TopologyBusinessRules"

    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method validates domain structure for topology calculations.
        It can be called with domain in kwargs or context.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - domain: DataMeshDomain instance (required)
                - domains: List of DataMeshDomain instances (optional, for relationship calculation)

        Returns:
            ValidationResult with validation status and details
        """
        # Extract domain or domains from context or kwargs
        domain = kwargs.get('domain')
        domains = kwargs.get('domains')

        if context and hasattr(context, 'resource'):
            if isinstance(context.resource, DataMeshDomain):
                domain = domain or context.resource
            elif isinstance(context.resource, list):
                domains = domains or context.resource
        elif context and hasattr(context, 'metadata') and isinstance(context.metadata, dict):
            domain = domain or context.metadata.get('domain')
            domains = domains or context.metadata.get('domains')

        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "validation_type": "topology"
        }

        # Validate single domain if provided
        if domain:
            details["domain_id"] = str(domain.id) if domain.id else None
            details["domain_name"] = domain.name if hasattr(domain, 'name') else None

            # Validate tenant context consistency
            if self.tenant_id and domain.tenant:
                if str(domain.tenant.id) != str(self.tenant_id):
                    errors.append(
                        f"Tenant mismatch: domain tenant ({domain.tenant.id}) "
                        f"does not match context tenant ({self.tenant_id})"
                    )

        # Validate domains list if provided
        elif domains:
            details["domains_count"] = len(domains)
            for idx, dom in enumerate(domains):
                if not isinstance(dom, DataMeshDomain):
                    errors.append(f"Domain at index {idx} is not a DataMeshDomain instance")
                elif self.tenant_id and dom.tenant:
                    if str(dom.tenant.id) != str(self.tenant_id):
                        errors.append(
                            f"Tenant mismatch: domain '{dom.name}' tenant ({dom.tenant.id}) "
                            f"does not match context tenant ({self.tenant_id})"
                        )

        else:
            errors.append("Domain or domains list is required for topology validation")

        is_valid = len(errors) == 0
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def calculate_relationships(
        self,
        domains: List[DataMeshDomain],
    ) -> List[Dict[str, Any]]:
        """
        Calculate relationships between domains.

        Relationships are determined by:
        - Shared policies (domains with common applied policies)
        - Shared assets (domains that share data products)
        - Domain dependencies (future: explicit dependency tracking)

        Args:
            domains: List of DataMeshDomain instances

        Returns:
            List of relationship dictionaries, each with:
                - source: Source domain ID
                - target: Target domain ID
                - type: Relationship type (e.g., "SHARED_POLICY", "SHARED_ASSET")
                - weight: Relationship strength/weight (number of shared items)
        """
        relationships = []

        # Calculate relationships based on shared policies
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        for i, domain1 in enumerate(domains):
            for domain2 in domains[i+1:]:
                # Get policies for both domains
                domain1_policies = set(
                    PolicyApplication.objects.filter(
                        domain=domain1,
                        status=PolicyApplicationStatus.APPLIED
                    ).values_list('policy_id', flat=True)
                )
                domain2_policies = set(
                    PolicyApplication.objects.filter(
                        domain=domain2,
                        status=PolicyApplicationStatus.APPLIED
                    ).values_list('policy_id', flat=True)
                )

                # Check for shared policies
                shared_policies = domain1_policies & domain2_policies
                if shared_policies:
                    relationships.append({
                        "source": str(domain1.id),
                        "target": str(domain2.id),
                        "type": "SHARED_POLICY",
                        "weight": len(shared_policies)
                    })

        return relationships

    def calculate_health_metrics(
        self,
        domain: DataMeshDomain,
    ) -> Dict[str, Any]:
        """
        Calculate health metrics for a domain.

        Health metrics include:
        - Health score (0-100)
        - Policy count
        - Compliance status
        - Violation count
        - Active status

        Args:
            domain: DataMeshDomain instance

        Returns:
            Dictionary with health metrics:
                - health_score: Integer 0-100
                - policy_count: Number of applied policies
                - compliance_status: MeshComplianceStatus value
                - violation_count: Number of violations
                - is_active: Boolean indicating if domain is active
        """
        from hub.apps.mesh.models import (
            PolicyApplication,
            PolicyApplicationStatus,
            ComplianceReport,
            MeshComplianceStatus
        )

        # Get policy count
        policy_count = PolicyApplication.objects.filter(
            domain=domain,
            status=PolicyApplicationStatus.APPLIED
        ).count()

        # Get latest compliance report
        latest_compliance = ComplianceReport.objects.filter(
            domain=domain,
            asset=None  # Domain-level report
        ).order_by('-generated_at').first()

        compliance_status = latest_compliance.compliance_status if latest_compliance else MeshComplianceStatus.UNKNOWN
        violation_count = latest_compliance.get_violation_count() if latest_compliance else 0

        # Calculate health score (0-100)
        health_score = 100

        # Deduct points for inactive status
        if domain.status != DomainStatus.ACTIVE:
            health_score -= 30

        # Deduct points for compliance issues
        if compliance_status == MeshComplianceStatus.NON_COMPLIANT:
            health_score -= 40
        elif compliance_status == MeshComplianceStatus.PARTIAL:
            health_score -= 20

        # Deduct points for violations
        if violation_count > 0:
            health_score -= min(10 * violation_count, 30)  # Max 30 points deduction

        # Ensure non-negative
        health_score = max(0, health_score)

        return {
            "health_score": health_score,
            "policy_count": policy_count,
            "compliance_status": compliance_status,
            "violation_count": violation_count,
            "is_active": domain.status == DomainStatus.ACTIVE,
        }

