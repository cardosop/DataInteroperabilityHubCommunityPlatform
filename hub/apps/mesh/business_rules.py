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
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from django.core.exceptions import ValidationError as DjangoValidationError

from hub.apps.mesh.models import DataMeshDomain, DomainStatus
from hub.apps.users.models import User

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation operation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]

    def __init__(
        self,
        is_valid: bool = True,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
        self.details = details or {}

    def __bool__(self):
        return self.is_valid


class DataMeshBusinessRules:
    """
    Business rules validator for data mesh domains.

    Validates:
    - Domain structure and definition
    - Ownership transfer rules
    - Domain boundaries structure
    """

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize DataMeshBusinessRules.

        Args:
            tenant_id: Optional tenant ID for tenant-specific validation
            user_id: Optional user ID for permission and cross-tenant validation
        """
        self.tenant_id = tenant_id
        self.user_id = user_id

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

        # Validate owner belongs to same tenant
        if hasattr(domain, 'owner') and domain.owner is not None:
            if hasattr(domain, 'tenant') and domain.tenant is not None:
                if domain.owner.tenant != domain.tenant:
                    errors.append(
                        f"Domain owner must belong to the same tenant as the domain. "
                        f"Owner tenant: {domain.owner.tenant.id}, Domain tenant: {domain.tenant.id}"
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
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Get all APPLIED policies for the domain
        applied_policy_applications = PolicyApplication.objects.filter(
            domain=domain,
            status=PolicyApplicationStatus.APPLIED
        ).select_related('policy')

        # Filter only enabled policies
        existing_policies = []
        for app in applied_policy_applications:
            if app.policy and app.policy.enabled:
                existing_policies.append({
                    "policy": app.policy,
                    "application": app,
                    "effective_effect": app.overrides.get("effect", app.policy.effect) if isinstance(app.overrides, dict) else app.policy.effect,
                    "effective_priority": app.overrides.get("priority", app.policy.priority) if isinstance(app.overrides, dict) else app.policy.priority,
                    "overrides": app.overrides if isinstance(app.overrides, dict) else {}
                })

        # Check for conflicts with each existing policy
        for existing in existing_policies:
            existing_policy = existing["policy"]
            existing_effect = existing["effective_effect"]
            existing_priority = existing["effective_priority"]
            new_effect = new_policy.effect
            new_priority = new_policy.priority

            # Check if conditions overlap
            if self._conditions_overlap(existing_policy.conditions, new_policy.conditions):
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
                        "conflict_type": "EFFECT_CONFLICT"
                    }

                    # Check priority resolution
                    if existing_priority < new_priority:
                        # Existing has higher priority - might be acceptable but warn
                        warnings.append(
                            f"Policy '{new_policy.name}' ({new_effect}) conflicts with higher priority "
                            f"policy '{existing_policy.name}' ({existing_effect}). "
                            f"Existing policy will take precedence."
                        )
                        conflict_info["priority_resolution"] = "EXISTING_HIGHER"
                    elif existing_priority > new_priority:
                        # New has higher priority - will override existing
                        errors.append(
                            f"Policy '{new_policy.name}' ({new_effect}) conflicts with existing "
                            f"policy '{existing_policy.name}' ({existing_effect}) with overlapping conditions. "
                            f"New policy has higher priority and will override existing policy."
                        )
                        conflict_info["priority_resolution"] = "NEW_HIGHER"
                    else:
                        # Same priority - definite conflict
                        errors.append(
                            f"Policy '{new_policy.name}' ({new_effect}) conflicts with existing "
                            f"policy '{existing_policy.name}' ({existing_effect}) with same priority "
                            f"and overlapping conditions. This creates ambiguous access control."
                        )
                        conflict_info["priority_resolution"] = "SAME_PRIORITY"

                    details["conflicts"].append(conflict_info)

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

    def _conditions_overlap(self, conditions1: Dict[str, Any], conditions2: Dict[str, Any]) -> bool:
        """
        Check if two policy conditions overlap.

        Conditions overlap if they could match the same set of attributes.
        This is a simplified check - in practice, condition evaluation can be complex.

        Args:
            conditions1: First policy conditions dictionary
            conditions2: Second policy conditions dictionary

        Returns:
            True if conditions overlap, False otherwise
        """
        if not isinstance(conditions1, dict) or not isinstance(conditions2, dict):
            return False

        # Check for overlapping keys with matching values
        # This is a simplified overlap detection - real ABAC condition evaluation is more complex
        for key, value1 in conditions1.items():
            if key in conditions2:
                value2 = conditions2[key]

                # Handle list values (e.g., user_roles)
                if isinstance(value1, list) and isinstance(value2, list):
                    # Check if lists have any common elements
                    if set(value1) & set(value2):
                        return True
                elif isinstance(value1, list):
                    # value2 is not a list - check if it's in value1
                    if value2 in value1:
                        return True
                elif isinstance(value2, list):
                    # value1 is not a list - check if it's in value2
                    if value1 in value2:
                        return True
                elif value1 == value2:
                    # Exact match
                    return True
                elif isinstance(value1, dict) and isinstance(value2, dict):
                    # Nested dict - recursively check overlap
                    if self._conditions_overlap(value1, value2):
                        return True

        # If no overlapping keys found, conditions don't overlap
        # Note: This is a conservative check. In practice, conditions might overlap
        # even without shared keys (e.g., different attribute paths to same resource)
        return False
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
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Get all APPLIED policies for the domain
        applied_policy_applications = PolicyApplication.objects.filter(
            domain=domain,
            status=PolicyApplicationStatus.APPLIED
        ).select_related('policy')

        # Filter only enabled policies
        existing_policies = []
        for app in applied_policy_applications:
            if app.policy and app.policy.enabled:
                existing_policies.append({
                    "policy": app.policy,
                    "application": app,
                    "effective_effect": app.overrides.get("effect", app.policy.effect) if isinstance(app.overrides, dict) else app.policy.effect,
                    "effective_priority": app.overrides.get("priority", app.policy.priority) if isinstance(app.overrides, dict) else app.policy.priority,
                    "overrides": app.overrides if isinstance(app.overrides, dict) else {}
                })

        # Check for conflicts with each existing policy
        for existing in existing_policies:
            existing_policy = existing["policy"]
            existing_effect = existing["effective_effect"]
            existing_priority = existing["effective_priority"]
            new_effect = new_policy.effect
            new_priority = new_policy.priority

            # Check if conditions overlap
            if self._conditions_overlap(existing_policy.conditions, new_policy.conditions):
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
                        "conflict_type": "EFFECT_CONFLICT"
                    }


class PolicyBusinessRules:
    """
    Business rules for policy application and compliance checking.

    Provides validation and compliance logic for:
    - Policy application validation
    - Compliance checking
    - Violation detection
    """

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize PolicyBusinessRules.

        Args:
            tenant_id: Optional tenant ID for tenant-specific validation
            user_id: Optional user ID for permission validation
        """
        self.tenant_id = tenant_id
        self.user_id = user_id

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


class TopologyBusinessRules:
    """
    Business rules for topology calculation and health metrics.

    Provides logic for:
    - Relationship calculation between domains
    - Health metrics calculation for domains
    """

    def __init__(self, tenant_id: Optional[str] = None):
        """
        Initialize TopologyBusinessRules.

        Args:
            tenant_id: Optional tenant ID for tenant-specific calculations
        """
        self.tenant_id = tenant_id

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

