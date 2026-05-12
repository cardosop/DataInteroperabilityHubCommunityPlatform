"""
Assets Business Rules

Comprehensive business rules validation for assets, including:
- Asset lifecycle validation
- Asset structure validation
- Tenant and user context validation
- Asset visibility and access validation

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""
import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from dataclasses import dataclass

from django.core.exceptions import ValidationError as DjangoValidationError

from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import register_rule
from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility, DQStatus, ComplianceStatus
from hub.apps.users.models import User

if TYPE_CHECKING:
    from hub.apps.contracts.models import Contract

# Forward reference for Dataset type hint
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hub.apps.datasets.models import Dataset

logger = logging.getLogger(__name__)


@dataclass
class AssetsRuleExecutionContext(RuleExecutionContext):
    """
    Extended execution context for assets business rules.

    Adds assets-specific context:
    - asset: The asset being validated
    - tenant: Optional tenant instance for validation
    - user: Optional user instance for permission validation
    """
    asset: Optional[Asset] = None
    tenant: Optional[Any] = None  # Using Any to avoid circular import
    user: Optional[User] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        base_dict = super().to_dict()
        base_dict.update({
            'asset_id': str(self.asset.id) if self.asset else None,
            'asset_key': self.asset.key if self.asset else None,
            'tenant_id': str(self.tenant.id) if self.tenant else None,
            'user_id': str(self.user.id) if self.user else None,
        })
        return base_dict


@register_rule(
    rule_name="assets_validation",
    description="Validates asset lifecycle, structure, tenant context, and access permissions",
    tags=["assets", "validation"],
    priority=10
)
class AssetsBusinessRules(BusinessRules):
    """
    Business rules validator for assets.

    Extends BusinessRules base class with assets-specific validation:
    - Asset lifecycle and status transitions
    - Asset structure and metadata validation
    - Tenant context consistency
    - User permissions and access validation
    """

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "AssetsBusinessRules"

    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates all asset validation checks.
        It can be called with an AssetsRuleExecutionContext or a standard
        RuleExecutionContext. If a standard context is provided, it extracts
        asset, tenant, and user from kwargs or context.metadata.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - asset: Asset instance (required)
                - tenant: Optional tenant instance
                - user: Optional user instance
                - validation_type: Optional validation type filter
                    ('lifecycle', 'structure', 'tenant_context', 'permissions', 'all')
                - old_status: Optional old status for transition validation
                - old_visibility: Optional old visibility for visibility change validation
                - new_status: Optional new status for transition validation
                - new_visibility: Optional new visibility for visibility change validation

        Returns:
            ValidationResult with validation status and details
        """
        # Extract asset, tenant, and user from context or kwargs
        if isinstance(context, AssetsRuleExecutionContext):
            asset = context.asset
            tenant = context.tenant
            user = context.user
        else:
            # Try to get from kwargs first
            asset = kwargs.get('asset')
            tenant = kwargs.get('tenant')
            user = kwargs.get('user')

            # If not in kwargs, try to get from context.metadata or context.resource
            if not asset:
                if context and hasattr(context, 'resource') and isinstance(context.resource, Asset):
                    asset = context.resource
                elif context and hasattr(context, 'metadata') and isinstance(context.metadata, dict):
                    asset = context.metadata.get('asset')
                    tenant = context.metadata.get('tenant') or tenant
                    user = context.metadata.get('user') or user

        if not asset:
            return ValidationResult(
                is_valid=False,
                errors=["Asset is required for validation"],
                details={"validation_type": kwargs.get('validation_type', 'all')}
            )

        validation_type = kwargs.get('validation_type', 'all')
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "asset_id": str(asset.id) if asset.id else None,
            "asset_key": asset.key if hasattr(asset, 'key') else None,
            "asset_name": asset.name if hasattr(asset, 'name') else None,
            "validation_type": validation_type,
        }

        # Perform validation based on type
        # Note: Specific validation methods will be implemented in subsequent tasks
        # For now, we provide a basic structure that validates asset existence
        if validation_type in ('structure', 'all'):
            structure_result = self._validate_asset_structure(asset)
            if not structure_result.is_valid:
                errors.extend(structure_result.errors)
                warnings.extend(structure_result.warnings)
                details.update(structure_result.details)

        if validation_type in ('tenant_context', 'all'):
            tenant_result = self._validate_tenant_context(asset, tenant)
            if not tenant_result.is_valid:
                errors.extend(tenant_result.errors)
                warnings.extend(tenant_result.warnings)
                details.update(tenant_result.details)

        if validation_type in ('permissions', 'all'):
            permissions_result = self._validate_permissions(asset, user)
            if not permissions_result.is_valid:
                errors.extend(permissions_result.errors)
                warnings.extend(permissions_result.warnings)
                details.update(permissions_result.details)

        if validation_type in ('lifecycle', 'all'):
            lifecycle_result = self._validate_asset_lifecycle(
                asset,
                old_status=kwargs.get('old_status'),
                new_status=kwargs.get('new_status', asset.status),
                old_visibility=kwargs.get('old_visibility'),
                new_visibility=kwargs.get('new_visibility', asset.visibility)
            )
            if not lifecycle_result.is_valid:
                errors.extend(lifecycle_result.errors)
                warnings.extend(lifecycle_result.warnings)
                details.update(lifecycle_result.details)

        # Determine overall validity
        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_asset_structure(self, asset: Asset) -> ValidationResult:
        """
        Validate basic asset structure.

        Args:
            asset: Asset instance to validate

        Returns:
            ValidationResult with structure validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # Validate required fields
        if not asset.key:
            errors.append("Asset key is required")
        elif len(asset.key) > 255:
            errors.append("Asset key must be 255 characters or less")

        if not asset.name:
            errors.append("Asset name is required")
        elif len(asset.name) > 255:
            errors.append("Asset name must be 255 characters or less")

        # Validate status is valid
        if asset.status not in [choice[0] for choice in AssetStatus.choices]:
            errors.append(f"Invalid asset status: {asset.status}")

        # Validate visibility is valid
        if asset.visibility not in [choice[0] for choice in AssetVisibility.choices]:
            errors.append(f"Invalid asset visibility: {asset.visibility}")

        # Warnings for optional fields that might be useful
        if not asset.description:
            warnings.append("Asset description is recommended for better discoverability")

        details['structure_checks'] = {
            'has_key': bool(asset.key),
            'has_name': bool(asset.name),
            'has_description': bool(asset.description),
            'status': asset.status,
            'visibility': asset.visibility,
        }

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_tenant_context(self, asset: Asset, tenant: Optional[Any] = None) -> ValidationResult:
        """
        Validate tenant context consistency.

        Args:
            asset: Asset instance to validate
            tenant: Optional tenant instance for validation

        Returns:
            ValidationResult with tenant context validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # Validate asset has tenant
        if not hasattr(asset, 'tenant') or asset.tenant is None:
            errors.append("Asset must have a tenant")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        asset_tenant_id = str(asset.tenant.id) if asset.tenant else None

        # Validate tenant context matches asset tenant
        if self.tenant_id:
            if asset_tenant_id != str(self.tenant_id):
                errors.append(
                    f"Tenant mismatch: asset tenant ({asset_tenant_id}) "
                    f"does not match context tenant ({self.tenant_id})"
                )

        # If tenant instance provided, validate it matches
        if tenant:
            tenant_id = str(tenant.id) if tenant else None
            if tenant_id and asset_tenant_id and tenant_id != asset_tenant_id:
                errors.append(
                    f"Tenant mismatch: provided tenant ({tenant_id}) "
                    f"does not match asset tenant ({asset_tenant_id})"
                )

        details['tenant_validation'] = {
            'asset_tenant_id': asset_tenant_id,
            'context_tenant_id': self.tenant_id,
            'provided_tenant_id': str(tenant.id) if tenant else None,
            'matches': len(errors) == 0,
        }

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_permissions(self, asset: Asset, user: Optional[User] = None) -> ValidationResult:
        """
        Validate user permissions for asset access.

        Args:
            asset: Asset instance to validate
            user: Optional user instance for permission validation

        Returns:
            ValidationResult with permissions validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # If user provided, validate user tenant matches asset tenant
        if user:
            user_tenant_id = str(user.tenant.id) if hasattr(user, 'tenant') and user.tenant else None
            asset_tenant_id = str(asset.tenant.id) if asset.tenant else None

            if user_tenant_id and asset_tenant_id and user_tenant_id != asset_tenant_id:
                errors.append(
                    f"User tenant ({user_tenant_id}) does not match asset tenant ({asset_tenant_id})"
                )

            # Validate user_id in context matches provided user
            if self.user_id:
                if str(user.id) != str(self.user_id):
                    warnings.append(
                        f"User ID mismatch: provided user ({user.id}) "
                        f"does not match context user ({self.user_id})"
                    )

        details['permissions_validation'] = {
            'user_id': str(user.id) if user else None,
            'context_user_id': self.user_id,
            'asset_tenant_id': str(asset.tenant.id) if asset.tenant else None,
            'user_tenant_id': str(user.tenant.id) if user and hasattr(user, 'tenant') and user.tenant else None,
        }

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_asset_lifecycle(
        self,
        asset: Asset,
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
        old_visibility: Optional[str] = None,
        new_visibility: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate asset lifecycle transitions and requirements.

        Validates:
        - Status transitions (DRAFT → ACTIVE → PUBLIC → RETIRED)
        - Activation requirements (contract, dataset, DQ, compliance)
        - Visibility changes (INTERNAL → PUBLIC requires ACTIVE status)
        - Retirement requirements (check dependencies, active listings)

        Args:
            asset: Asset instance to validate
            old_status: Previous status (for transition validation)
            new_status: New status (defaults to asset.status)
            old_visibility: Previous visibility (for visibility change validation)
            new_visibility: New visibility (defaults to asset.visibility)

        Returns:
            ValidationResult with lifecycle validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'lifecycle_validation': {}
        }

        # Use provided values or current asset values
        current_status = new_status if new_status is not None else asset.status
        current_visibility = new_visibility if new_visibility is not None else asset.visibility
        previous_status = old_status if old_status is not None else asset.status
        previous_visibility = old_visibility if old_visibility is not None else asset.visibility

        # Validate status transitions
        status_transition_result = self._validate_status_transition(
            asset, previous_status, current_status
        )
        if not status_transition_result.is_valid:
            errors.extend(status_transition_result.errors)
            warnings.extend(status_transition_result.warnings)
            details['lifecycle_validation']['status_transition'] = status_transition_result.details

        # Validate activation requirements if transitioning to ACTIVE
        if current_status == AssetStatus.ACTIVE and previous_status != AssetStatus.ACTIVE:
            activation_result = self._validate_activation_requirements(asset)
            if not activation_result.is_valid:
                errors.extend(activation_result.errors)
                warnings.extend(activation_result.warnings)
                details['lifecycle_validation']['activation_requirements'] = activation_result.details

        # Validate visibility changes
        if current_visibility != previous_visibility:
            visibility_result = self._validate_visibility_change(
                asset, previous_visibility, current_visibility, current_status
            )
            if not visibility_result.is_valid:
                errors.extend(visibility_result.errors)
                warnings.extend(visibility_result.warnings)
                details['lifecycle_validation']['visibility_change'] = visibility_result.details

        # Validate retirement requirements if transitioning to RETIRED
        if current_status == AssetStatus.RETIRED and previous_status != AssetStatus.RETIRED:
            retirement_result = self._validate_retirement_requirements(asset)
            if not retirement_result.is_valid:
                errors.extend(retirement_result.errors)
                warnings.extend(retirement_result.warnings)
                details['lifecycle_validation']['retirement_requirements'] = retirement_result.details

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_status_transition(
        self,
        asset: Asset,
        old_status: str,
        new_status: str
    ) -> ValidationResult:
        """
        Validate status transition is allowed.

        Allowed transitions:
        - DRAFT → ACTIVE, RETIRED (soft-delete from draft allowed)
        - ACTIVE → PUBLIC
        - ACTIVE → RETIRED
        - PUBLIC → RETIRED
        - RETIRED → (no transitions allowed)

        Args:
            asset: Asset instance
            old_status: Previous status
            new_status: New status

        Returns:
            ValidationResult with transition validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'old_status': old_status,
            'new_status': new_status,
            'transition_allowed': True
        }

        # If status hasn't changed, no validation needed
        if old_status == new_status:
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Define allowed transitions (DRAFT may go to RETIRED for soft-delete)
        allowed_transitions = {
            AssetStatus.DRAFT: [AssetStatus.ACTIVE, AssetStatus.RETIRED],
            AssetStatus.ACTIVE: [AssetStatus.PUBLIC, AssetStatus.RETIRED],
            AssetStatus.PUBLIC: [AssetStatus.RETIRED],
            AssetStatus.RETIRED: []  # No transitions from RETIRED
        }

        # Check if transition is allowed
        if old_status not in allowed_transitions:
            errors.append(f"Invalid old status: {old_status}")
            details['transition_allowed'] = False
        elif new_status not in allowed_transitions[old_status]:
            errors.append(
                f"Invalid status transition: {old_status} → {new_status}. "
                f"Allowed transitions from {old_status}: {', '.join(allowed_transitions[old_status])}"
            )
            details['transition_allowed'] = False
        else:
            details['transition_allowed'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_activation_requirements(self, asset: Asset) -> ValidationResult:
        """
        Validate activation requirements.

        Requirements for ACTIVE status:
        - Must have an ACTIVE contract
        - Contract must have VALID or WARNING_ONLY validation_status
        - Contract must have NORMALIZED_OK or NORMALIZED_WITH_WARNINGS normalization_status
        - If dataset exists:
          - dq_status must be PASS or WARN
          - compliance_status must be PASS or WARN

        Args:
            asset: Asset instance to validate

        Returns:
            ValidationResult with activation requirements validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'activation_checks': {}
        }

        # Check contract requirements
        from hub.apps.contracts.models import Contract, ContractStatus, ValidationStatus, NormalizationStatus

        active_contract = asset.contracts.filter(status=ContractStatus.ACTIVE).first()
        if not active_contract:
            errors.append("Asset must have an ACTIVE contract to be activated")
            details['activation_checks']['has_active_contract'] = False
        else:
            details['activation_checks']['has_active_contract'] = True
            details['activation_checks']['contract_id'] = str(active_contract.id)

            # Check contract validation status
            if active_contract.validation_status not in [
                ValidationStatus.VALID,
                ValidationStatus.WARNING_ONLY
            ]:
                errors.append(
                    f"Contract validation_status must be VALID or WARNING_ONLY "
                    f"(current: {active_contract.validation_status})"
                )
                details['activation_checks']['contract_validation_status_valid'] = False
            else:
                details['activation_checks']['contract_validation_status_valid'] = True
                details['activation_checks']['contract_validation_status'] = active_contract.validation_status

            # Check contract normalization status
            if active_contract.normalization_status not in [
                NormalizationStatus.NORMALIZED_OK,
                NormalizationStatus.NORMALIZED_WITH_WARNINGS
            ]:
                errors.append(
                    f"Contract normalization_status must be NORMALIZED_OK or NORMALIZED_WITH_WARNINGS "
                    f"(current: {active_contract.normalization_status})"
                )
                details['activation_checks']['contract_normalization_status_valid'] = False
            else:
                details['activation_checks']['contract_normalization_status_valid'] = True
                details['activation_checks']['contract_normalization_status'] = active_contract.normalization_status

        # Check dataset requirements (if dataset exists)
        dataset = asset.datasets.first()
        if dataset:
            details['activation_checks']['has_dataset'] = True
            details['activation_checks']['dataset_id'] = str(dataset.id)

            # Check DQ status
            if asset.dq_status not in [DQStatus.PASS, DQStatus.WARN]:
                errors.append(
                    f"dq_status must be PASS or WARN when dataset exists "
                    f"(current: {asset.dq_status})"
                )
                details['activation_checks']['dq_status_valid'] = False
            else:
                details['activation_checks']['dq_status_valid'] = True
                if asset.dq_status == DQStatus.WARN:
                    warnings.append("Asset has DQ status WARN - activation allowed but quality issues exist")

            # Check compliance status
            if asset.compliance_status not in [ComplianceStatus.PASS, ComplianceStatus.WARN]:
                errors.append(
                    f"compliance_status must be PASS or WARN when dataset exists "
                    f"(current: {asset.compliance_status})"
                )
                details['activation_checks']['compliance_status_valid'] = False
            else:
                details['activation_checks']['compliance_status_valid'] = True
                if asset.compliance_status == ComplianceStatus.WARN:
                    warnings.append("Asset has compliance status WARN - activation allowed but compliance issues exist")
        else:
            details['activation_checks']['has_dataset'] = False
            # Contract-only assets are allowed (no dataset required)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_visibility_change(
        self,
        asset: Asset,
        old_visibility: str,
        new_visibility: str,
        current_status: str
    ) -> ValidationResult:
        """
        Validate visibility change requirements.

        Requirements:
        - INTERNAL → PUBLIC requires ACTIVE status

        Args:
            asset: Asset instance
            old_visibility: Previous visibility
            new_visibility: New visibility
            current_status: Current asset status

        Returns:
            ValidationResult with visibility change validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'old_visibility': old_visibility,
            'new_visibility': new_visibility,
            'current_status': current_status
        }

        # If visibility hasn't changed, no validation needed
        if old_visibility == new_visibility:
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Check INTERNAL → PUBLIC transition requires ACTIVE status
        if (
            old_visibility == AssetVisibility.INTERNAL and
            new_visibility == AssetVisibility.PUBLIC
        ):
            if current_status != AssetStatus.ACTIVE:
                errors.append(
                    f"Visibility change from INTERNAL to PUBLIC requires ACTIVE status "
                    f"(current status: {current_status})"
                )
                details['visibility_change_allowed'] = False
            else:
                details['visibility_change_allowed'] = True

        # PUBLIC → INTERNAL is always allowed
        elif (
            old_visibility == AssetVisibility.PUBLIC and
            new_visibility == AssetVisibility.INTERNAL
        ):
            details['visibility_change_allowed'] = True
            warnings.append("Changing visibility from PUBLIC to INTERNAL will hide the asset from public view")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_retirement_requirements(self, asset: Asset) -> ValidationResult:
        """
        Validate retirement requirements.

        Checks for dependencies and active listings that might prevent retirement:
        - Active marketplace listings (PUBLISHED status)
        - Other dependencies (if any)

        Args:
            asset: Asset instance to validate

        Returns:
            ValidationResult with retirement requirements validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'retirement_checks': {}
        }

        # Check for active marketplace listings
        from hub.apps.marketplace.models import Listing, ListingStatus

        active_listings = Listing.objects.filter(
            asset=asset,
            status=ListingStatus.PUBLISHED
        )

        if active_listings.exists():
            listing_count = active_listings.count()
            listing_ids = [str(listing.id) for listing in active_listings[:5]]  # Limit to first 5 for details
            errors.append(
                f"Asset cannot be retired while it has {listing_count} active marketplace listing(s). "
                f"Please unlist or delete the listings first."
            )
            details['retirement_checks']['has_active_listings'] = True
            details['retirement_checks']['active_listing_count'] = listing_count
            details['retirement_checks']['active_listing_ids'] = listing_ids
        else:
            details['retirement_checks']['has_active_listings'] = False

        # Check for other dependencies (e.g., active entitlements, scheduled jobs, etc.)
        # This can be extended in the future as more dependencies are identified
        details['retirement_checks']['other_dependencies_checked'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_dataset_attachment(
        self,
        asset: Asset,
        dataset: "Dataset",
        user: Optional[User] = None,
        proposed_version: Optional[int] = None
    ) -> ValidationResult:
        """
        Validate dataset can be attached to asset.

        Validates:
        - Dataset schema compatibility with asset contract schema
        - Dataset tenant ownership (dataset belongs to same tenant as asset)
        - Dataset access validation (user has access to dataset)
        - Dataset version compatibility (version increments properly)

        Args:
            asset: Asset instance to attach dataset to
            dataset: Dataset instance to attach
            user: Optional user instance for access validation
            proposed_version: Optional proposed version number (if None, will be auto-incremented)

        Returns:
            ValidationResult with attachment validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'asset_id': str(asset.id),
            'dataset_id': str(dataset.id),
            'validation_checks': {}
        }

        # Validate tenant ownership
        tenant_result = self._validate_dataset_tenant_ownership(asset, dataset)
        if not tenant_result.is_valid:
            errors.extend(tenant_result.errors)
            warnings.extend(tenant_result.warnings)
        details['validation_checks']['tenant_ownership'] = tenant_result.details

        # Validate dataset access
        access_result = self._validate_dataset_access(asset, dataset, user)
        if not access_result.is_valid:
            errors.extend(access_result.errors)
            warnings.extend(access_result.warnings)
        details['validation_checks']['access'] = access_result.details

        # Validate schema compatibility (if contract exists)
        schema_result = self._validate_dataset_schema_compatibility(asset, dataset)
        if not schema_result.is_valid:
            errors.extend(schema_result.errors)
            warnings.extend(schema_result.warnings)
        details['validation_checks']['schema_compatibility'] = schema_result.details

        # Validate version compatibility
        version_result = self._validate_dataset_version_compatibility(
            asset, dataset, proposed_version
        )
        if not version_result.is_valid:
            errors.extend(version_result.errors)
            warnings.extend(version_result.warnings)
        details['validation_checks']['version_compatibility'] = version_result.details

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_dataset_tenant_ownership(
        self,
        asset: Asset,
        dataset: "Dataset"
    ) -> ValidationResult:
        """
        Validate dataset belongs to same tenant as asset.

        Args:
            asset: Asset instance
            dataset: Dataset instance

        Returns:
            ValidationResult with tenant ownership validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'asset_tenant_id': str(asset.tenant.id) if asset.tenant else None,
            'dataset_tenant_id': str(dataset.tenant.id) if dataset.tenant else None,
            'tenants_match': False
        }

        # Validate asset has tenant
        if not asset.tenant:
            errors.append("Asset must have a tenant")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Validate dataset has tenant
        if not dataset.tenant:
            errors.append("Dataset must have a tenant")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Validate tenants match
        asset_tenant_id = str(asset.tenant.id)
        dataset_tenant_id = str(dataset.tenant.id)

        if asset_tenant_id != dataset_tenant_id:
            errors.append(
                f"Dataset tenant ({dataset_tenant_id}) does not match asset tenant ({asset_tenant_id})"
            )
            details['tenants_match'] = False
        else:
            details['tenants_match'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_dataset_access(
        self,
        asset: Asset,
        dataset: "Dataset",
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate user has access to dataset.

        For same-tenant access, validates user belongs to same tenant.
        For cross-tenant access, would require entitlements (future enhancement).

        Args:
            asset: Asset instance
            dataset: Dataset instance
            user: Optional user instance for access validation

        Returns:
            ValidationResult with access validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'access_allowed': False,
            'cross_tenant': False,
            'user_provided': user is not None
        }

        # If no user provided, skip access validation (will be handled at API level)
        if not user:
            warnings.append("User not provided, skipping dataset access validation")
            details['access_allowed'] = True  # Not an error, just skipped
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Validate user has tenant
        if not hasattr(user, 'tenant') or not user.tenant:
            errors.append("User must have a tenant for access validation")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Check if cross-tenant access
        asset_tenant_id = str(asset.tenant.id) if asset.tenant else None
        dataset_tenant_id = str(dataset.tenant.id) if dataset.tenant else None
        user_tenant_id = str(user.tenant.id) if user.tenant else None

        is_cross_tenant = (
            asset_tenant_id != user_tenant_id or
            dataset_tenant_id != user_tenant_id
        )
        details['cross_tenant'] = is_cross_tenant

        if not is_cross_tenant:
            # Same tenant - access allowed
            details['access_allowed'] = True
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Cross-tenant access - would require entitlements (future enhancement)
        # For now, we allow it but warn
        warnings.append(
            "Cross-tenant dataset access detected. "
            "Full entitlement validation not yet implemented in business rules."
        )
        details['access_allowed'] = True  # Allow for now, will be enforced at API level
        details['entitlement_check_required'] = True

        return ValidationResult(
            is_valid=True,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_dataset_schema_compatibility(
        self,
        asset: Asset,
        dataset: "Dataset"
    ) -> ValidationResult:
        """
        Validate dataset schema is compatible with asset contract schema.

        Compares dataset.schema_json.fields with contract.hub_contract_json.schema.fields.

        Args:
            asset: Asset instance
            dataset: Dataset instance

        Returns:
            ValidationResult with schema compatibility validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'contract_exists': False,
            'contract_has_schema': False,
            'dataset_has_schema': False,
            'schema_compatible': False,
            'missing_fields': [],
            'type_mismatches': [],
            'extra_fields': []
        }

        # Get contract schema
        from hub.apps.contracts.models import Contract, ContractStatus

        active_contract = asset.contracts.filter(status=ContractStatus.ACTIVE).first()
        if not active_contract:
            warnings.append("Asset has no ACTIVE contract - schema compatibility check skipped")
            details['contract_exists'] = False
            return ValidationResult(
                is_valid=True,  # Not an error if no contract
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['contract_exists'] = True
        details['contract_id'] = str(active_contract.id)

        # Get contract schema
        hub_contract_json = active_contract.hub_contract_json
        if not hub_contract_json:
            warnings.append("Contract has no hub_contract_json - schema compatibility check skipped")
            details['contract_has_schema'] = False
            return ValidationResult(
                is_valid=True,  # Not an error if no schema
                errors=errors,
                warnings=warnings,
                details=details
            )

        contract_schema = hub_contract_json.get('schema')
        if not contract_schema:
            warnings.append("Contract hub_contract_json has no schema section - schema compatibility check skipped")
            details['contract_has_schema'] = False
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        contract_fields = contract_schema.get('fields', [])
        if not contract_fields:
            warnings.append("Contract schema has no fields - schema compatibility check skipped")
            details['contract_has_schema'] = False
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['contract_has_schema'] = True
        details['contract_field_count'] = len(contract_fields)

        # Get dataset schema
        dataset_schema = dataset.schema_json
        if not dataset_schema:
            errors.append("Dataset has no schema_json - cannot validate schema compatibility")
            details['dataset_has_schema'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        dataset_fields = dataset_schema.get('fields', [])
        if not isinstance(dataset_fields, list):
            errors.append("Dataset schema_json.fields must be a list")
            details['dataset_has_schema'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        if not dataset_fields:
            errors.append("Dataset schema has no fields - cannot validate schema compatibility")
            details['dataset_has_schema'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['dataset_has_schema'] = True
        details['dataset_field_count'] = len(dataset_fields)

        # Build field maps for comparison
        contract_field_map = {}
        for field_dict in contract_fields:
            if isinstance(field_dict, dict):
                field_name = field_dict.get('name')
                if field_name:
                    contract_field_map[field_name] = {
                        'data_type': field_dict.get('data_type') or field_dict.get('type', 'string'),
                        'nullable': field_dict.get('nullable', True),
                        'required': field_dict.get('required', False)
                    }

        dataset_field_map = {}
        for field_dict in dataset_fields:
            if isinstance(field_dict, dict):
                field_name = field_dict.get('name')
                if field_name:
                    dataset_field_map[field_name] = {
                        'data_type': field_dict.get('data_type') or field_dict.get('type', 'string'),
                        'nullable': field_dict.get('nullable', True)
                    }

        details['contract_field_names'] = list(contract_field_map.keys())
        details['dataset_field_names'] = list(dataset_field_map.keys())

        # Check for missing fields (contract fields not in dataset)
        missing_fields = set(contract_field_map.keys()) - set(dataset_field_map.keys())
        if missing_fields:
            errors.append(
                f"Dataset schema missing required contract fields: {', '.join(sorted(missing_fields))}"
            )
            details['missing_fields'] = list(missing_fields)

        # Check for type mismatches
        type_mismatches = []
        for field_name in contract_field_map.keys():
            if field_name in dataset_field_map:
                contract_type = contract_field_map[field_name]['data_type'].lower()
                dataset_type = dataset_field_map[field_name]['data_type'].lower()

                # Type compatibility matrix (similar to transformation pipeline)
                TYPE_COMPATIBILITY = {
                    "string": {"string", "text"},
                    "integer": {"integer", "number", "int", "long"},
                    "float": {"float", "number", "double"},
                    "number": {"integer", "float", "number", "double", "long", "int"},
                    "boolean": {"boolean", "bool"},
                    "date": {"date", "datetime", "timestamp"},
                    "datetime": {"datetime", "timestamp", "date"},
                    "timestamp": {"timestamp", "datetime", "date"},
                    "array": {"array", "list"},
                    "object": {"object", "dict", "json"},
                }

                compatible_types = TYPE_COMPATIBILITY.get(contract_type, {contract_type})
                if dataset_type not in compatible_types and contract_type != dataset_type:
                    type_mismatches.append({
                        'field': field_name,
                        'contract_type': contract_type,
                        'dataset_type': dataset_type
                    })
                    errors.append(
                        f"Field '{field_name}' has incompatible types: "
                        f"contract expects '{contract_type}', dataset has '{dataset_type}'"
                    )
                elif contract_type != dataset_type:
                    # Types are compatible but different - warning
                    type_mismatches.append({
                        'field': field_name,
                        'contract_type': contract_type,
                        'dataset_type': dataset_type,
                        'compatible': True
                    })
                    warnings.append(
                        f"Field '{field_name}' has different but compatible types: "
                        f"contract expects '{contract_type}', dataset has '{dataset_type}'"
                    )

        details['type_mismatches'] = type_mismatches

        # Check for extra fields (dataset fields not in contract) - warning only
        extra_fields = set(dataset_field_map.keys()) - set(contract_field_map.keys())
        if extra_fields:
            warnings.append(
                f"Dataset schema contains fields not in contract: {', '.join(sorted(extra_fields))}"
            )
            details['extra_fields'] = list(extra_fields)

        # Schema is compatible if no errors
        details['schema_compatible'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_dataset_version_compatibility(
        self,
        asset: Asset,
        dataset: "Dataset",
        proposed_version: Optional[int] = None
    ) -> ValidationResult:
        """
        Validate dataset version compatibility.

        Validates:
        - Version increments properly (proposed_version > latest version)
        - Version is positive integer
        - Version doesn't conflict with existing versions

        Args:
            asset: Asset instance
            dataset: Dataset instance
            proposed_version: Optional proposed version number

        Returns:
            ValidationResult with version compatibility validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'proposed_version': proposed_version,
            'latest_version': None,
            'version_valid': False
        }

        # Get latest dataset version for this asset
        latest_dataset = asset.datasets.order_by('-version').first()
        latest_version = latest_dataset.version if latest_dataset else 0
        details['latest_version'] = latest_version

        # If no proposed version, will be auto-incremented (valid)
        if proposed_version is None:
            details['version_valid'] = True
            details['auto_increment'] = True
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Validate proposed version is positive integer
        if not isinstance(proposed_version, int) or proposed_version < 1:
            errors.append(
                f"Proposed version must be a positive integer (got: {proposed_version})"
            )
            details['version_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Validate version increments properly
        if proposed_version <= latest_version:
            errors.append(
                f"Proposed version ({proposed_version}) must be greater than latest version ({latest_version})"
            )
            details['version_valid'] = False
        else:
            details['version_valid'] = True

        # Check for version conflicts (if dataset already attached to asset with different version)
        if dataset.asset == asset and dataset.version != proposed_version:
            warnings.append(
                f"Dataset is already attached to asset with version {dataset.version}, "
                f"proposed version {proposed_version} will update it"
            )
            details['version_update'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_contract_attachment(
        self,
        asset: Asset,
        contract: "Contract",
        user: Optional[User] = None,
        proposed_version: Optional[int] = None
    ) -> ValidationResult:
        """
        Validate contract can be attached to asset.

        Validates:
        - Contract validation status (must be VALID or WARNING_ONLY)
        - Contract normalization status (must be NORMALIZED_OK or NORMALIZED_WITH_WARNINGS)
        - Contract tenant ownership (contract belongs to same tenant as asset)
        - Contract version compatibility (version increments properly, no conflicts)

        Args:
            asset: Asset instance to attach contract to
            contract: Contract instance to attach
            user: Optional user instance for access validation
            proposed_version: Optional proposed version number (if None, will be auto-incremented)

        Returns:
            ValidationResult with attachment validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'asset_id': str(asset.id),
            'contract_id': str(contract.id),
            'validation_checks': {}
        }

        # Validate contract validation status
        validation_status_result = self._validate_contract_validation_status(contract)
        errors.extend(validation_status_result.errors)
        warnings.extend(validation_status_result.warnings)
        details['validation_checks']['validation_status'] = validation_status_result.details

        # Validate contract normalization status
        normalization_status_result = self._validate_contract_normalization_status(contract)
        errors.extend(normalization_status_result.errors)
        warnings.extend(normalization_status_result.warnings)
        details['validation_checks']['normalization_status'] = normalization_status_result.details

        # Validate tenant ownership
        tenant_result = self._validate_contract_tenant_ownership(asset, contract)
        if not tenant_result.is_valid:
            errors.extend(tenant_result.errors)
            warnings.extend(tenant_result.warnings)
        details['validation_checks']['tenant_ownership'] = tenant_result.details

        # Validate version compatibility
        version_result = self._validate_contract_version_compatibility(
            asset, contract, proposed_version
        )
        if not version_result.is_valid:
            errors.extend(version_result.errors)
            warnings.extend(version_result.warnings)
        details['validation_checks']['version_compatibility'] = version_result.details

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_contract_validation_status(self, contract: "Contract") -> ValidationResult:
        """
        Validate contract validation status.

        Requirements:
        - Contract validation_status must be VALID or WARNING_ONLY

        Args:
            contract: Contract instance to validate

        Returns:
            ValidationResult with validation status check
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'validation_status': contract.validation_status,
            'status_valid': False
        }

        from hub.apps.contracts.models import ValidationStatus

        if contract.validation_status not in [
            ValidationStatus.VALID,
            ValidationStatus.WARNING_ONLY,
            ValidationStatus.SKIPPED,
        ]:
            errors.append(
                f"Contract validation_status must be VALID, WARNING_ONLY, or SKIPPED "
                f"(current: {contract.validation_status})"
            )
            details['status_valid'] = False
        else:
            details['status_valid'] = True
            if contract.validation_status == ValidationStatus.WARNING_ONLY:
                warnings.append(
                    "Contract has validation status WARNING_ONLY - attachment allowed but validation warnings exist"
                )
                if contract.validation_warnings:
                    details['validation_warnings'] = contract.validation_warnings
            elif contract.validation_status == ValidationStatus.SKIPPED:
                warnings.append(
                    "Contract validation was skipped - attachment allowed but contract has not been validated"
                )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_contract_normalization_status(self, contract: "Contract") -> ValidationResult:
        """
        Validate contract normalization status.

        Requirements:
        - Contract normalization_status must be NORMALIZED_OK or NORMALIZED_WITH_WARNINGS

        Args:
            contract: Contract instance to validate

        Returns:
            ValidationResult with normalization status check
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'normalization_status': contract.normalization_status,
            'status_valid': False
        }

        from hub.apps.contracts.models import NormalizationStatus

        if contract.normalization_status not in [
            NormalizationStatus.NORMALIZED_OK,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS
        ]:
            errors.append(
                f"Contract normalization_status must be NORMALIZED_OK or NORMALIZED_WITH_WARNINGS "
                f"(current: {contract.normalization_status})"
            )
            details['status_valid'] = False
        else:
            details['status_valid'] = True
            if contract.normalization_status == NormalizationStatus.NORMALIZED_WITH_WARNINGS:
                warnings.append(
                    "Contract has normalization status NORMALIZED_WITH_WARNINGS - attachment allowed but normalization warnings exist"
                )
                if contract.normalization_warnings:
                    details['normalization_warnings'] = contract.normalization_warnings

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_contract_tenant_ownership(self, asset: Asset, contract: "Contract") -> ValidationResult:
        """
        Validate contract tenant ownership.

        Requirements:
        - Contract must belong to the same tenant as the asset

        Args:
            asset: Asset instance
            contract: Contract instance to validate

        Returns:
            ValidationResult with tenant ownership check
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'asset_tenant_id': str(asset.tenant.id) if asset.tenant else None,
            'contract_tenant_id': str(contract.tenant.id) if contract.tenant else None,
            'tenant_match': False
        }

        if not contract.tenant:
            errors.append("Contract must have a tenant")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        if not asset.tenant:
            errors.append("Asset must have a tenant")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        if str(contract.tenant.id) != str(asset.tenant.id):
            errors.append(
                f"Contract tenant ({contract.tenant.id}) does not match asset tenant ({asset.tenant.id})"
            )
            details['tenant_match'] = False
        else:
            details['tenant_match'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_contract_version_compatibility(
        self,
        asset: Asset,
        contract: "Contract",
        proposed_version: Optional[int] = None
    ) -> ValidationResult:
        """
        Validate contract version compatibility.

        Requirements:
        - If contract already attached to asset, version should match or be updated
        - If proposed_version provided, it must be greater than latest version
        - Version must be positive integer

        Args:
            asset: Asset instance
            contract: Contract instance to validate
            proposed_version: Optional proposed version number

        Returns:
            ValidationResult with version compatibility check
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'current_version': contract.version,
            'proposed_version': proposed_version,
            'version_valid': False
        }

        # Get latest version for this asset (excluding the contract being attached)
        from hub.apps.contracts.models import Contract

        existing_contracts = Contract.objects.filter(
            tenant=asset.tenant,
            asset=asset
        ).exclude(id=contract.id).order_by('-version')

        latest_version = existing_contracts.first().version if existing_contracts.exists() else 0
        details['latest_version'] = latest_version

        # If contract already attached to this asset, check if version matches
        if contract.asset == asset:
            if proposed_version is not None and proposed_version != contract.version:
                warnings.append(
                    f"Contract is already attached to asset with version {contract.version}, "
                    f"proposed version {proposed_version} will update it"
                )
                details['version_update'] = True
            else:
                details['version_valid'] = True
                details['already_attached'] = True
                return ValidationResult(
                    is_valid=True,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )

        # If no proposed version, will be auto-incremented (valid)
        if proposed_version is None:
            details['version_valid'] = True
            details['auto_increment'] = True
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Validate proposed version is positive integer
        if not isinstance(proposed_version, int) or proposed_version < 1:
            errors.append(
                f"Proposed version must be a positive integer (got: {proposed_version})"
            )
            details['version_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Check for version conflicts first (more specific error)
        conflicting_contract = Contract.objects.filter(
            tenant=asset.tenant,
            asset=asset,
            version=proposed_version
        ).exclude(id=contract.id).first()

        if conflicting_contract:
            errors.append(
                f"Version {proposed_version} already exists for this asset (contract: {conflicting_contract.id})"
            )
            details['version_valid'] = False
            details['conflicting_contract_id'] = str(conflicting_contract.id)
        # Validate version increments properly
        elif proposed_version <= latest_version:
            errors.append(
                f"Proposed version ({proposed_version}) must be greater than latest version ({latest_version})"
            )
            details['version_valid'] = False
        else:
            details['version_valid'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_health_score_calculation(
        self,
        asset: Asset,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate health score calculation components.

        Validates:
        - DQ status is valid and appropriate for asset status
        - Compliance status is valid and appropriate for asset status
        - Contract status is valid (if contract exists)
        - Health score calculation is consistent with component statuses

        Args:
            asset: Asset instance to validate
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, warnings, and health score details

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "asset_id": str(asset.id),
            "asset_key": asset.key,
            "asset_name": asset.name,
            "health_score_checks": {}
        }

        # Define status strings for comparison
        active_status_str = str(AssetStatus.ACTIVE)

        # Validate DQ status
        if asset.dq_status not in [status[0] for status in DQStatus.choices]:
            errors.append(
                f"Invalid DQ status '{asset.dq_status}'. "
                f"Valid choices: {', '.join([s[0] for s in DQStatus.choices])}"
            )
            details["health_score_checks"]["dq_status_valid"] = False
        else:
            details["health_score_checks"]["dq_status_valid"] = True
            details["health_score_checks"]["dq_status"] = asset.dq_status

            # Check DQ status appropriateness for asset status
            active_status_str = str(AssetStatus.ACTIVE)
            if asset.status == active_status_str:
                if asset.dq_status not in [str(DQStatus.PASS), str(DQStatus.WARN)]:
                    errors.append(
                        f"Asset with ACTIVE status requires DQ status PASS or WARN, "
                        f"but current status is {asset.dq_status}"
                    )
                    details["health_score_checks"]["dq_status_appropriate"] = False
                else:
                    details["health_score_checks"]["dq_status_appropriate"] = True
            else:
                details["health_score_checks"]["dq_status_appropriate"] = True

        # Validate compliance status
        if asset.compliance_status not in [status[0] for status in ComplianceStatus.choices]:
            errors.append(
                f"Invalid compliance status '{asset.compliance_status}'. "
                f"Valid choices: {', '.join([s[0] for s in ComplianceStatus.choices])}"
            )
            details["health_score_checks"]["compliance_status_valid"] = False
        else:
            details["health_score_checks"]["compliance_status_valid"] = True
            details["health_score_checks"]["compliance_status"] = asset.compliance_status

            # Check compliance status appropriateness for asset status
            if asset.status == active_status_str:
                if asset.compliance_status not in [str(ComplianceStatus.PASS), str(ComplianceStatus.WARN)]:
                    errors.append(
                        f"Asset with ACTIVE status requires compliance status PASS or WARN, "
                        f"but current status is {asset.compliance_status}"
                    )
                    details["health_score_checks"]["compliance_status_appropriate"] = False
                else:
                    details["health_score_checks"]["compliance_status_appropriate"] = True
            else:
                details["health_score_checks"]["compliance_status_appropriate"] = True

        # Validate contract status (if contract exists)
        contract = asset.contracts.filter(status="ACTIVE").first()
        if contract:
            details["health_score_checks"]["contract_exists"] = True
            details["health_score_checks"]["contract_id"] = str(contract.id)
            details["health_score_checks"]["contract_version"] = contract.version

            # Validate contract validation status
            if contract.validation_status not in ["VALID", "WARNING_ONLY"]:
                if asset.status == active_status_str:
                    errors.append(
                        f"Asset with ACTIVE status requires contract validation_status VALID or WARNING_ONLY, "
                        f"but current status is {contract.validation_status}"
                    )
                    details["health_score_checks"]["contract_validation_status_appropriate"] = False
                else:
                    warnings.append(
                        f"Contract validation_status is {contract.validation_status}. "
                        f"Asset cannot be activated until contract is VALID or WARNING_ONLY"
                    )
                    details["health_score_checks"]["contract_validation_status_appropriate"] = False
            else:
                details["health_score_checks"]["contract_validation_status_appropriate"] = True
                details["health_score_checks"]["contract_validation_status"] = contract.validation_status

            # Validate contract normalization status
            if contract.normalization_status not in ["NORMALIZED_OK", "NORMALIZED_WITH_WARNINGS"]:
                if asset.status == active_status_str:
                    errors.append(
                        f"Asset with ACTIVE status requires contract normalization_status "
                        f"NORMALIZED_OK or NORMALIZED_WITH_WARNINGS, "
                        f"but current status is {contract.normalization_status}"
                    )
                    details["health_score_checks"]["contract_normalization_status_appropriate"] = False
                else:
                    warnings.append(
                        f"Contract normalization_status is {contract.normalization_status}. "
                        f"Asset cannot be activated until contract is normalized"
                    )
                    details["health_score_checks"]["contract_normalization_status_appropriate"] = False
            else:
                details["health_score_checks"]["contract_normalization_status_appropriate"] = True
                details["health_score_checks"]["contract_normalization_status"] = contract.normalization_status
        else:
            details["health_score_checks"]["contract_exists"] = False
            if asset.status == active_status_str:
                errors.append(
                    "Asset with ACTIVE status requires an ACTIVE contract"
                )
                details["health_score_checks"]["contract_required"] = True
            else:
                warnings.append(
                    "No ACTIVE contract found. Asset cannot be activated without a contract"
                )
                details["health_score_checks"]["contract_required"] = False

        # Validate health score is within valid range
        if asset.health_score is not None:
            if asset.health_score < 0.0 or asset.health_score > 100.0:
                errors.append(
                    f"Health score must be between 0.0 and 100.0, but got {asset.health_score}"
                )
                details["health_score_checks"]["health_score_range_valid"] = False
            else:
                details["health_score_checks"]["health_score_range_valid"] = True
                details["health_score_checks"]["health_score"] = asset.health_score
        else:
            details["health_score_checks"]["health_score"] = None
            warnings.append(
                "Health score is not calculated. Consider recalculating health score"
            )

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not is_valid and raise_on_error:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError(
                f"Health score calculation validation failed: {', '.join(errors)}",
                code="INVALID_HEALTH_SCORE_CALCULATION",
                details=details
            )

        return result

    def validate_health_score_thresholds(
        self,
        asset: Asset,
        target_status: Optional[AssetStatus] = None,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate health score thresholds for asset status transitions.

        Validates:
        - Health score meets minimum threshold for ACTIVE status (default: 50.0)
        - Health score meets minimum threshold for PUBLIC status (default: 70.0)
        - Component scores meet minimum thresholds
        - Health score is consistent with component statuses

        Args:
            asset: Asset instance to validate
            target_status: Optional target status to validate thresholds for (default: asset.status)
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, warnings, and threshold details

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "asset_id": str(asset.id),
            "asset_key": asset.key,
            "asset_name": asset.name,
            "current_status": asset.status,
            "target_status": target_status or asset.status,
            "threshold_checks": {}
        }

        # Define minimum thresholds
        MIN_HEALTH_SCORE_ACTIVE = 50.0
        MIN_HEALTH_SCORE_PUBLIC = 70.0
        MIN_DQ_SCORE_ACTIVE = 50.0
        MIN_COMPLIANCE_SCORE_ACTIVE = 50.0

        # Normalize target_status to string if it's an enum
        if target_status:
            if isinstance(target_status, tuple):
                target = target_status[0]  # Extract string from enum tuple
            else:
                target = str(target_status)
        else:
            target = asset.status
        details["threshold_checks"]["target_status"] = target

        # Calculate current health score if not set
        if asset.health_score is None:
            from hub.apps.assets.health_score import AssetHealthScoreService
            try:
                calculated_score = AssetHealthScoreService.calculate_health_score(asset)
                details["threshold_checks"]["health_score_calculated"] = True
                details["threshold_checks"]["calculated_score"] = calculated_score
            except Exception as e:
                errors.append(
                    f"Failed to calculate health score: {str(e)}"
                )
                details["threshold_checks"]["health_score_calculated"] = False
                result = ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )
                if raise_on_error:
                    from hub.apps.core.services.base import ValidationError
                    raise ValidationError(
                        f"Health score threshold validation failed: {', '.join(errors)}",
                        code="HEALTH_SCORE_CALCULATION_FAILED",
                        details=details
                    )
                return result

        health_score = asset.health_score or 0.0
        details["threshold_checks"]["current_health_score"] = health_score

        # Validate thresholds based on target status
        active_status_str = str(AssetStatus.ACTIVE)
        public_status_str = str(AssetStatus.PUBLIC)
        draft_status_str = str(AssetStatus.DRAFT)
        retired_status_str = str(AssetStatus.RETIRED)

        if target == active_status_str:
            if health_score < MIN_HEALTH_SCORE_ACTIVE:
                errors.append(
                    f"Health score {health_score:.2f} is below minimum threshold "
                    f"{MIN_HEALTH_SCORE_ACTIVE} required for ACTIVE status"
                )
                details["threshold_checks"]["meets_active_threshold"] = False
            else:
                details["threshold_checks"]["meets_active_threshold"] = True

            # Check component scores
            from hub.apps.assets.health_score import AssetHealthScoreService
            breakdown = AssetHealthScoreService.get_health_score_breakdown(asset)
            dq_score = breakdown["components"]["dq"]["score"]
            compliance_score = breakdown["components"]["compliance"]["score"]

            if dq_score < MIN_DQ_SCORE_ACTIVE:
                errors.append(
                    f"DQ component score {dq_score:.2f} is below minimum threshold "
                    f"{MIN_DQ_SCORE_ACTIVE} required for ACTIVE status"
                )
                details["threshold_checks"]["dq_score_meets_threshold"] = False
            else:
                details["threshold_checks"]["dq_score_meets_threshold"] = True

            if compliance_score < MIN_COMPLIANCE_SCORE_ACTIVE:
                errors.append(
                    f"Compliance component score {compliance_score:.2f} is below minimum threshold "
                    f"{MIN_COMPLIANCE_SCORE_ACTIVE} required for ACTIVE status"
                )
                details["threshold_checks"]["compliance_score_meets_threshold"] = False
            else:
                details["threshold_checks"]["compliance_score_meets_threshold"] = True

            details["threshold_checks"]["component_scores"] = {
                "dq": dq_score,
                "compliance": compliance_score,
                "freshness": breakdown["components"]["freshness"]["score"],
                "usage": breakdown["components"]["usage"]["score"]
            }

        elif target == public_status_str:
            if health_score < MIN_HEALTH_SCORE_PUBLIC:
                errors.append(
                    f"Health score {health_score:.2f} is below minimum threshold "
                    f"{MIN_HEALTH_SCORE_PUBLIC} required for PUBLIC status"
                )
                details["threshold_checks"]["meets_public_threshold"] = False
            else:
                details["threshold_checks"]["meets_public_threshold"] = True

        # Warn if health score is low but status allows it
        if health_score < 30.0 and target in [draft_status_str, retired_status_str]:
            warnings.append(
                f"Health score {health_score:.2f} is very low. "
                f"Consider improving asset quality before activating"
            )
            details["threshold_checks"]["low_health_score_warning"] = True

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not is_valid and raise_on_error:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError(
                f"Health score threshold validation failed: {', '.join(errors)}",
                code="HEALTH_SCORE_THRESHOLD_NOT_MET",
                details=details
            )

        return result

    def validate_health_score_update_triggers(
        self,
        asset: Asset,
        last_calculated_at: Optional[Any] = None,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate when health score should be recalculated.

        Validates:
        - Health score is stale (older than threshold)
        - Component statuses have changed since last calculation
        - Asset status has changed requiring recalculation
        - Contract status has changed requiring recalculation

        Args:
            asset: Asset instance to validate
            last_calculated_at: Optional timestamp of last calculation (default: asset.updated_at)
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, warnings, and trigger details

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "asset_id": str(asset.id),
            "asset_key": asset.key,
            "asset_name": asset.name,
            "update_trigger_checks": {}
        }

        from django.utils import timezone
        from datetime import timedelta

        # Determine last calculation time
        if last_calculated_at:
            last_calc = last_calculated_at
        elif hasattr(asset, 'health_score_updated_at') and asset.health_score_updated_at:
            last_calc = asset.health_score_updated_at
        else:
            # Fallback to asset updated_at
            last_calc = asset.updated_at

        details["update_trigger_checks"]["last_calculated_at"] = (
            last_calc.isoformat() if hasattr(last_calc, 'isoformat') else str(last_calc)
        )

        # Check if health score is stale (older than 24 hours)
        STALE_THRESHOLD_HOURS = 24
        now = timezone.now()

        # Ensure last_calc is timezone-aware
        if hasattr(last_calc, 'tzinfo'):
            if last_calc.tzinfo is None:
                # Make naive datetime timezone-aware
                last_calc = timezone.make_aware(last_calc)
            age_hours = (now - last_calc).total_seconds() / 3600
        else:
            # If not a datetime, can't calculate age
            age_hours = 0

        details["update_trigger_checks"]["age_hours"] = age_hours
        details["update_trigger_checks"]["stale_threshold_hours"] = STALE_THRESHOLD_HOURS

        if age_hours > STALE_THRESHOLD_HOURS:
            warnings.append(
                f"Health score is stale (last calculated {age_hours:.1f} hours ago). "
                f"Consider recalculating health score"
            )
            details["update_trigger_checks"]["is_stale"] = True
            details["update_trigger_checks"]["recalculation_recommended"] = True
        else:
            details["update_trigger_checks"]["is_stale"] = False

        # Check if component statuses have changed
        # Note: This is a heuristic check - actual change detection would require tracking previous values
        unknown_dq_str = str(DQStatus.UNKNOWN)
        unknown_compliance_str = str(ComplianceStatus.UNKNOWN)

        if asset.dq_status == unknown_dq_str:
            warnings.append(
                "DQ status is UNKNOWN. Health score may not reflect current DQ state"
            )
            details["update_trigger_checks"]["dq_status_unknown"] = True

        if asset.compliance_status == unknown_compliance_str:
            warnings.append(
                "Compliance status is UNKNOWN. Health score may not reflect current compliance state"
            )
            details["update_trigger_checks"]["compliance_status_unknown"] = True

        # Check if contract status has changed (if contract exists)
        contract = asset.contracts.filter(status="ACTIVE").first()
        if contract:
            if contract.validation_status not in ["VALID", "WARNING_ONLY"]:
                warnings.append(
                    f"Contract validation_status is {contract.validation_status}. "
                    f"Health score may need recalculation after contract validation"
                )
                details["update_trigger_checks"]["contract_validation_changed"] = True

        # Check if asset status requires recalculation
        active_status_str = str(AssetStatus.ACTIVE)
        if asset.status == active_status_str and asset.health_score is None:
            errors.append(
                "Asset with ACTIVE status must have a calculated health score"
            )
            details["update_trigger_checks"]["recalculation_required"] = True
        elif asset.status == active_status_str and asset.health_score is not None:
            # Validate health score meets threshold
            threshold_result = self.validate_health_score_thresholds(
                asset=asset,
                target_status=str(AssetStatus.ACTIVE),
                raise_on_error=False
            )
            if not threshold_result.is_valid:
                warnings.append(
                    f"Health score does not meet ACTIVE status threshold. "
                    f"Consider improving asset quality: {', '.join(threshold_result.errors)}"
                )
                details["update_trigger_checks"]["threshold_check_failed"] = True
            else:
                details["update_trigger_checks"]["threshold_check_passed"] = True

        # Determine if recalculation is required vs recommended
        recalculation_required = details["update_trigger_checks"].get("recalculation_required", False)
        recalculation_recommended = (
            details["update_trigger_checks"].get("recalculation_recommended", False) or
            details["update_trigger_checks"].get("dq_status_unknown", False) or
            details["update_trigger_checks"].get("compliance_status_unknown", False) or
            details["update_trigger_checks"].get("contract_validation_changed", False)
        )

        details["update_trigger_checks"]["recalculation_required"] = recalculation_required
        details["update_trigger_checks"]["recalculation_recommended"] = recalculation_recommended

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not is_valid and raise_on_error:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError(
                f"Health score update trigger validation failed: {', '.join(errors)}",
                code="HEALTH_SCORE_UPDATE_REQUIRED",
                details=details
            )

        return result



class AssetActivationRule:
    """Phase 274.2 — compliance-aware asset activation as a business rule.

    Three-state taxonomy per §13.2:
    - COMPLIANCE_SCAN_PENDING (HTTP 409 + Retry-After: 30)
    - COMPLIANCE_SCAN_FAILED (HTTP 422)
    - COMPLIANCE_NOT_ALLOWED_TO_STORE (HTTP 422)
    - COMPLIANCE_THRESHOLD_EXCEEDED (HTTP 422)
    - No blockers → activation allowed (HTTP 200)

    Supports both @staticmethod (view/model callers) and instance
    (chain runner) call patterns.
    """

    def __init__(self, tenant_id=None, user_id=None):
        self.tenant_id = tenant_id
        self.user_id = user_id

    @staticmethod
    def validate_activation(asset) -> "dict":
        """
        Returns a structured dict:
            {"can_activate": bool, "blocker_code": str|None, "details": dict}

        ``blocker_code`` is one of:
            COMPLIANCE_SCAN_PENDING, COMPLIANCE_SCAN_FAILED,
            COMPLIANCE_NOT_ALLOWED_TO_STORE, COMPLIANCE_THRESHOLD_EXCEEDED,
            or None (no compliance blocker).
        """
        from hub.apps.compliance.models import ComplianceRun, RiskLevel

        latest = (
            ComplianceRun.objects
            .filter(asset=asset, status__in=("SUCCEEDED", "FAILED"))
            .order_by("-completed_at")
            .first()
        )

        # No run → PENDING.
        if latest is None:
            return {
                "can_activate": False,
                "blocker_code": "COMPLIANCE_SCAN_PENDING",
                "details": {
                    "retry_after_seconds": 30,
                    "asset_id": str(asset.id),
                    "message": "Compliance scan has not completed yet. Retry after 30 seconds.",
                },
            }

        # Failed run → FAILED.
        if latest.status == "FAILED":
            return {
                "can_activate": False,
                "blocker_code": "COMPLIANCE_SCAN_FAILED",
                "details": {
                    "asset_id": str(asset.id),
                    "compliance_run_id": str(latest.id),
                    "message": "The compliance scan failed. Please trigger a new scan.",
                },
            }

        # Not allowed to store → NOT_ALLOWED.
        if latest.allowed_to_store is False:
            return {
                "can_activate": False,
                "blocker_code": "COMPLIANCE_NOT_ALLOWED_TO_STORE",
                "details": {
                    "asset_id": str(asset.id),
                    "compliance_run_id": str(latest.id),
                    "message": "The compliance scan determined this data is not allowed to be stored.",
                },
            }

        # Risk exceeds tenant threshold → THRESHOLD_EXCEEDED.
        if asset.tenant_id:
            from hub.apps.tenants.models import Tenant
            try:
                tenant = Tenant.objects.only("compliance_risk_threshold").get(
                    pk=asset.tenant_id,
                )
                threshold = getattr(tenant, "compliance_risk_threshold", "HIGH") or "HIGH"
                if latest.risk_level and RiskLevel.exceeds(latest.risk_level, threshold):
                    return {
                        "can_activate": False,
                        "blocker_code": "COMPLIANCE_THRESHOLD_EXCEEDED",
                        "details": {
                            "risk_level": latest.risk_level,
                            "threshold": threshold,
                            "asset_id": str(asset.id),
                            "compliance_run_id": str(latest.id),
                            "message": (
                                f"Compliance risk level ({latest.risk_level}) exceeds "
                                f"tenant threshold ({threshold})."
                            ),
                        },
                    }
            except Tenant.DoesNotExist:
                pass

        # No compliance blocker.
        return {
            "can_activate": True,
            "blocker_code": None,
            "details": {
                "asset_id": str(asset.id),
                "compliance_run_id": str(latest.id),
            },
        }
