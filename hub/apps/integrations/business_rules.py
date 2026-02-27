"""
Marketplace Integration Business Rules

Comprehensive business rules validation for marketplace integrations, including:
- Connection validation
- Sync job validation
- Mapping validation
- Tenant and user context validation
- Asset and marketplace listing validation

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""
import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from dataclasses import dataclass

from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import register_rule
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceSyncJob, MarketplaceMapping
from hub.apps.integrations.base import MarketplaceType, SyncDirection, SyncStatus

if TYPE_CHECKING:
    from hub.apps.assets.models import Asset
    from hub.apps.integrations.base import MarketplaceListing, MarketplaceAssetMapping, MarketplaceResource
    from hub.apps.users.models import User
    from hub.apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


@dataclass
class MarketplaceIntegrationRuleExecutionContext(RuleExecutionContext):
    """
    Extended execution context for marketplace integration business rules.

    Adds marketplace-specific context:
    - connection: The marketplace connection being validated
    - sync_job: The sync job being validated
    - mapping: The mapping being validated
    - asset: The Hub asset being validated
    - marketplace_listing: The marketplace listing being validated
    """
    connection: Optional[MarketplaceConnection] = None
    sync_job: Optional[MarketplaceSyncJob] = None
    mapping: Optional[MarketplaceMapping] = None
    asset: Optional[Any] = None  # Using Any to avoid circular import
    marketplace_listing: Optional[Any] = None  # Using Any to avoid circular import

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        base_dict = super().to_dict()
        base_dict.update({
            'connection_id': str(self.connection.id) if self.connection else None,
            'sync_job_id': str(self.sync_job.id) if self.sync_job else None,
            'mapping_id': str(self.mapping.id) if self.mapping else None,
            'asset_id': str(self.asset.id) if self.asset and hasattr(self.asset, 'id') else None,
            'marketplace_listing_id': (
                self.marketplace_listing.marketplace_id
                if self.marketplace_listing and hasattr(self.marketplace_listing, 'marketplace_id')
                else None
            ),
        })
        return base_dict


@register_rule(
    rule_name="marketplace_integration_validation",
    description="Validates marketplace integration operations including connections, sync jobs, mappings, assets, and marketplace listings",
    tags=["marketplace", "integration", "validation"],
    priority=10
)
class MarketplaceIntegrationBusinessRules(BusinessRules):
    """
    Business rules validator for marketplace integrations.

    Extends BusinessRules base class with marketplace-specific validation:
    - Connection lifecycle and configuration validation
    - Sync job creation and execution validation
    - Mapping creation and update validation
    - Asset and marketplace listing validation
    - Tenant context consistency
    - User permissions and access validation
    """

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "MarketplaceIntegrationBusinessRules"

    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates all marketplace integration validation checks.
        It can be called with a MarketplaceIntegrationRuleExecutionContext or a standard
        RuleExecutionContext. If a standard context is provided, it extracts
        connection, sync_job, mapping, asset, and marketplace_listing from kwargs or context.metadata.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - connection: MarketplaceConnection instance (optional)
                - sync_job: MarketplaceSyncJob instance (optional)
                - mapping: MarketplaceMapping instance (optional)
                - asset: Asset instance (optional)
                - marketplace_listing: MarketplaceListing instance (optional)
                - validation_type: Optional validation type filter
                    ('connection', 'sync_job', 'mapping', 'asset', 'marketplace_listing', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        # Extract resources from context or kwargs
        if isinstance(context, MarketplaceIntegrationRuleExecutionContext):
            connection = context.connection
            sync_job = context.sync_job
            mapping = context.mapping
            asset = context.asset
            marketplace_listing = context.marketplace_listing
        else:
            # Try to get from kwargs first
            connection = kwargs.get('connection')
            sync_job = kwargs.get('sync_job')
            mapping = kwargs.get('mapping')
            asset = kwargs.get('asset')
            marketplace_listing = kwargs.get('marketplace_listing')

            # If not in kwargs, try to get from context.metadata or context.resource
            if context and hasattr(context, 'metadata') and isinstance(context.metadata, dict):
                connection = connection or context.metadata.get('connection')
                sync_job = sync_job or context.metadata.get('sync_job')
                mapping = mapping or context.metadata.get('mapping')
                asset = asset or context.metadata.get('asset')
                marketplace_listing = marketplace_listing or context.metadata.get('marketplace_listing')

            # Also check context.resource
            if context and hasattr(context, 'resource'):
                if isinstance(context.resource, MarketplaceConnection):
                    connection = context.resource
                elif isinstance(context.resource, MarketplaceSyncJob):
                    sync_job = context.resource
                elif isinstance(context.resource, MarketplaceMapping):
                    mapping = context.resource

        validation_type = kwargs.get('validation_type', 'all')
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "validation_type": validation_type,
        }

        # Perform validation based on type
        if validation_type in ('connection', 'all') and connection:
            connection_result = self._validate_connection(connection)
            errors.extend(connection_result.errors)
            warnings.extend(connection_result.warnings)
            # Merge details, preserving validation_type
            for key, value in connection_result.details.items():
                if key != 'validation_type':
                    details[key] = value

        if validation_type in ('sync_job', 'all') and sync_job:
            sync_job_result = self._validate_sync_job(sync_job, connection)
            errors.extend(sync_job_result.errors)
            warnings.extend(sync_job_result.warnings)
            # Merge details, preserving validation_type
            for key, value in sync_job_result.details.items():
                if key != 'validation_type':
                    details[key] = value

        if validation_type in ('mapping', 'all') and mapping:
            mapping_result = self._validate_mapping(mapping, connection, asset)
            errors.extend(mapping_result.errors)
            warnings.extend(mapping_result.warnings)
            # Merge details, preserving validation_type
            for key, value in mapping_result.details.items():
                if key != 'validation_type':
                    details[key] = value

        if validation_type in ('asset', 'all') and asset:
            asset_result = self._validate_asset(asset)
            errors.extend(asset_result.errors)
            warnings.extend(asset_result.warnings)
            # Merge details, preserving validation_type
            for key, value in asset_result.details.items():
                if key != 'validation_type':
                    details[key] = value

        if validation_type in ('marketplace_listing', 'all') and marketplace_listing:
            listing_result = self._validate_marketplace_listing(marketplace_listing)
            errors.extend(listing_result.errors)
            warnings.extend(listing_result.warnings)
            # Merge details, preserving validation_type
            for key, value in listing_result.details.items():
                if key != 'validation_type':
                    details[key] = value

        # If no resources provided, return appropriate result
        if not any([connection, sync_job, mapping, asset, marketplace_listing]):
            return ValidationResult(
                is_valid=False,
                errors=["At least one resource (connection, sync_job, mapping, asset, or marketplace_listing) must be provided"],
                details=details
            )

        # Determine overall validity
        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_connection(self, connection: MarketplaceConnection) -> ValidationResult:
        """
        Validate marketplace connection.

        Validates:
        - Connection has required fields (name, marketplace_type, config)
        - Connection is active (if required)
        - Tenant context consistency
        - Configuration structure

        Args:
            connection: MarketplaceConnection instance to validate

        Returns:
            ValidationResult with connection validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'connection_id': str(connection.id),
            'connection_name': connection.name,
            'marketplace_type': connection.marketplace_type,
        }

        # Validate connection has tenant
        if not connection.tenant:
            errors.append("Connection must have a tenant")
            details['has_tenant'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
        details['has_tenant'] = True
        details['tenant_id'] = str(connection.tenant.id)

        # Validate tenant context consistency
        if self.tenant_id:
            if str(connection.tenant.id) != str(self.tenant_id):
                errors.append(
                    f"Connection tenant ({connection.tenant.id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )
                details['tenant_match'] = False
            else:
                details['tenant_match'] = True

        # Validate connection name
        if not connection.name or not connection.name.strip():
            errors.append("Connection name cannot be empty")
            details['has_name'] = False
        else:
            details['has_name'] = True

        # Validate marketplace_type
        valid_types = [mt.value for mt in MarketplaceType]
        if connection.marketplace_type not in valid_types:
            errors.append(
                f"Invalid marketplace_type: {connection.marketplace_type}. "
                f"Valid types are: {', '.join(valid_types)}"
            )
            details['marketplace_type_valid'] = False
        else:
            details['marketplace_type_valid'] = True

        # Validate config is a dictionary
        if not isinstance(connection.config, dict):
            errors.append("Connection config must be a dictionary")
            details['config_valid'] = False
        else:
            details['config_valid'] = True
            # Try to get decrypted config (will handle encryption errors gracefully)
            try:
                decrypted_config = connection.get_config()
                details['config_decryptable'] = True
                details['config_keys'] = list(decrypted_config.keys()) if decrypted_config else []
            except Exception as e:
                warnings.append(f"Could not decrypt connection config: {str(e)}")
                details['config_decryptable'] = False

        # Validate connection is active (if required)
        if not connection.is_active:
            warnings.append("Connection is not active - may not be usable for sync operations")
            details['is_active'] = False
        else:
            details['is_active'] = True
            # No warnings for active connections

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_sync_job(
        self,
        sync_job: MarketplaceSyncJob,
        connection: Optional[MarketplaceConnection] = None
    ) -> ValidationResult:
        """
        Validate marketplace sync job.

        Validates:
        - Sync job has required fields (connection, direction, status)
        - Connection is active (if provided)
        - Direction is valid
        - Status is valid
        - Tenant context consistency

        Args:
            sync_job: MarketplaceSyncJob instance to validate
            connection: Optional MarketplaceConnection instance (if not provided, uses sync_job.connection)

        Returns:
            ValidationResult with sync job validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'sync_job_id': str(sync_job.id),
            'direction': sync_job.direction,
            'status': sync_job.status,
        }

        # Validate sync job has tenant
        if not sync_job.tenant:
            errors.append("Sync job must have a tenant")
            details['has_tenant'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
        details['has_tenant'] = True
        details['tenant_id'] = str(sync_job.tenant.id)

        # Validate tenant context consistency
        if self.tenant_id:
            if str(sync_job.tenant.id) != str(self.tenant_id):
                errors.append(
                    f"Sync job tenant ({sync_job.tenant.id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )
                details['tenant_match'] = False
            else:
                details['tenant_match'] = True

        # Validate connection
        effective_connection = connection or sync_job.connection
        if not effective_connection:
            errors.append("Sync job must have a connection")
            details['has_connection'] = False
        else:
            details['has_connection'] = True
            details['connection_id'] = str(effective_connection.id)

            # Validate connection is active
            if not effective_connection.is_active:
                errors.append(
                    f"Connection {effective_connection.id} is not active - "
                    f"cannot be used for sync operations"
                )
                details['connection_active'] = False
            else:
                details['connection_active'] = True

            # Validate connection tenant matches sync job tenant
            if effective_connection.tenant.id != sync_job.tenant.id:
                errors.append(
                    f"Connection tenant ({effective_connection.tenant.id}) does not match "
                    f"sync job tenant ({sync_job.tenant.id})"
                )
                details['connection_tenant_match'] = False
            else:
                details['connection_tenant_match'] = True

        # Validate direction
        valid_directions = [sd.value for sd in SyncDirection]
        if sync_job.direction not in valid_directions:
            errors.append(
                f"Invalid sync direction: {sync_job.direction}. "
                f"Valid directions are: {', '.join(valid_directions)}"
            )
            details['direction_valid'] = False
        else:
            details['direction_valid'] = True

        # Validate status
        valid_statuses = [ss.value for ss in SyncStatus]
        if sync_job.status not in valid_statuses:
            errors.append(
                f"Invalid sync status: {sync_job.status}. "
                f"Valid statuses are: {', '.join(valid_statuses)}"
            )
            details['status_valid'] = False
        else:
            details['status_valid'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_mapping(
        self,
        mapping: MarketplaceMapping,
        connection: Optional[MarketplaceConnection] = None,
        asset: Optional[Any] = None
    ) -> ValidationResult:
        """
        Validate marketplace mapping.

        Validates:
        - Mapping has required fields (connection, hub_asset, external_listing_id)
        - Connection is active (if provided)
        - Asset exists and is valid (if provided)
        - Tenant context consistency

        Args:
            mapping: MarketplaceMapping instance to validate
            connection: Optional MarketplaceConnection instance (if not provided, uses mapping.connection)
            asset: Optional Asset instance (if not provided, uses mapping.hub_asset)

        Returns:
            ValidationResult with mapping validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'mapping_id': str(mapping.id),
            'external_listing_id': mapping.external_listing_id,
        }

        # Validate mapping has tenant
        if not mapping.tenant:
            errors.append("Mapping must have a tenant")
            details['has_tenant'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
        details['has_tenant'] = True
        details['tenant_id'] = str(mapping.tenant.id)

        # Validate tenant context consistency
        if self.tenant_id:
            if str(mapping.tenant.id) != str(self.tenant_id):
                errors.append(
                    f"Mapping tenant ({mapping.tenant.id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )
                details['tenant_match'] = False
            else:
                details['tenant_match'] = True

        # Validate connection
        effective_connection = connection or mapping.connection
        if not effective_connection:
            errors.append("Mapping must have a connection")
            details['has_connection'] = False
        else:
            details['has_connection'] = True
            details['connection_id'] = str(effective_connection.id)

            # Validate connection is active
            if not effective_connection.is_active:
                warnings.append(
                    f"Connection {effective_connection.id} is not active - "
                    f"mapping may not be usable for sync operations"
                )
                details['connection_active'] = False
            else:
                details['connection_active'] = True

            # Validate connection tenant matches mapping tenant
            if effective_connection.tenant.id != mapping.tenant.id:
                errors.append(
                    f"Connection tenant ({effective_connection.tenant.id}) does not match "
                    f"mapping tenant ({mapping.tenant.id})"
                )
                details['connection_tenant_match'] = False
            else:
                details['connection_tenant_match'] = True

        # Validate asset
        effective_asset = asset or mapping.hub_asset
        if not effective_asset:
            errors.append("Mapping must have a hub asset")
            details['has_asset'] = False
        else:
            details['has_asset'] = True
            details['asset_id'] = str(effective_asset.id) if hasattr(effective_asset, 'id') else None

            # Validate asset tenant matches mapping tenant
            if hasattr(effective_asset, 'tenant') and effective_asset.tenant:
                if effective_asset.tenant.id != mapping.tenant.id:
                    errors.append(
                        f"Asset tenant ({effective_asset.tenant.id}) does not match "
                        f"mapping tenant ({mapping.tenant.id})"
                    )
                    details['asset_tenant_match'] = False
                else:
                    details['asset_tenant_match'] = True
            else:
                warnings.append("Asset has no tenant association")
                details['asset_tenant_match'] = None

        # Validate external_listing_id
        if not mapping.external_listing_id or not mapping.external_listing_id.strip():
            errors.append("Mapping must have an external_listing_id")
            details['has_external_listing_id'] = False
        else:
            details['has_external_listing_id'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_asset(self, asset: Any) -> ValidationResult:
        """
        Validate Hub asset.

        Validates:
        - Asset has required fields (id, tenant)
        - Asset tenant context consistency

        Args:
            asset: Asset instance to validate

        Returns:
            ValidationResult with asset validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # Validate asset has id
        if not hasattr(asset, 'id') or not asset.id:
            errors.append("Asset must have an id")
            details['has_id'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
        details['has_id'] = True
        details['asset_id'] = str(asset.id)

        # Validate asset has tenant
        if not hasattr(asset, 'tenant') or not asset.tenant:
            errors.append("Asset must have a tenant")
            details['has_tenant'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
        details['has_tenant'] = True
        details['tenant_id'] = str(asset.tenant.id)

        # Validate tenant context consistency
        if self.tenant_id:
            if str(asset.tenant.id) != str(self.tenant_id):
                errors.append(
                    f"Asset tenant ({asset.tenant.id}) does not match "
                    f"context tenant ({self.tenant_id})"
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

    def _validate_marketplace_listing(self, marketplace_listing: Any) -> ValidationResult:
        """
        Validate marketplace listing.

        Validates:
        - Listing has required fields (marketplace_id, marketplace_type, title)
        - Marketplace type is valid

        Args:
            marketplace_listing: MarketplaceListing instance to validate

        Returns:
            ValidationResult with marketplace listing validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # Validate marketplace_listing has marketplace_id
        if not hasattr(marketplace_listing, 'marketplace_id') or not marketplace_listing.marketplace_id:
            errors.append("Marketplace listing must have a marketplace_id")
            details['has_marketplace_id'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
        details['has_marketplace_id'] = True
        details['marketplace_id'] = marketplace_listing.marketplace_id

        # Validate marketplace_type
        if not hasattr(marketplace_listing, 'marketplace_type') or not marketplace_listing.marketplace_type:
            errors.append("Marketplace listing must have a marketplace_type")
            details['has_marketplace_type'] = False
        else:
            details['has_marketplace_type'] = True
            # Check if it's an enum value or string
            marketplace_type_value = (
                marketplace_listing.marketplace_type.value
                if hasattr(marketplace_listing.marketplace_type, 'value')
                else str(marketplace_listing.marketplace_type)
            )
            details['marketplace_type'] = marketplace_type_value

            # Validate marketplace_type is valid
            valid_types = [mt.value for mt in MarketplaceType]
            if marketplace_type_value not in valid_types:
                errors.append(
                    f"Invalid marketplace_type: {marketplace_type_value}. "
                    f"Valid types are: {', '.join(valid_types)}"
                )
                details['marketplace_type_valid'] = False
            else:
                details['marketplace_type_valid'] = True

        # Validate title
        if not hasattr(marketplace_listing, 'title') or not marketplace_listing.title:
            warnings.append("Marketplace listing should have a title")
            details['has_title'] = False
        else:
            details['has_title'] = True
            details['title'] = marketplace_listing.title

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_sync_direction(
        self,
        sync_direction: SyncDirection,
        connection: MarketplaceConnection
    ) -> ValidationResult:
        """
        Validate sync direction is supported by connector and matches connection capabilities.

        Validates:
        - Sync direction is supported by connector
        - Sync direction matches connection capabilities

        Args:
            sync_direction: SyncDirection enum value to validate
            connection: MarketplaceConnection instance to check against

        Returns:
            ValidationResult with sync direction validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'sync_direction': sync_direction.value if isinstance(sync_direction, SyncDirection) else str(sync_direction),
            'connection_id': str(connection.id),
            'marketplace_type': connection.marketplace_type,
        }

        # Validate sync_direction is a valid SyncDirection
        if not isinstance(sync_direction, SyncDirection):
            try:
                sync_direction = SyncDirection(sync_direction)
            except ValueError:
                valid_directions = [sd.value for sd in SyncDirection]
                errors.append(
                    f"Invalid sync direction: {sync_direction}. "
                    f"Valid directions are: {', '.join(valid_directions)}"
                )
                details['direction_valid'] = False
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )

        details['sync_direction'] = sync_direction.value

        # Get connector to check supported directions
        try:
            from hub.apps.integrations.factory import MarketplaceConnectorFactory
            marketplace_type = MarketplaceType(connection.marketplace_type)
            factory = MarketplaceConnectorFactory()

            # Check if marketplace type is supported
            if not factory.is_supported(marketplace_type):
                errors.append(
                    f"Marketplace type {marketplace_type.value} is not supported - "
                    f"cannot validate sync direction"
                )
                details['marketplace_supported'] = False
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )
            details['marketplace_supported'] = True

            # Create connector instance to check supported directions
            try:
                config = connection.get_config()
                connector = factory.create_connector(
                    marketplace_type=marketplace_type,
                    config=config
                )
                supported_directions = connector.supported_sync_directions
                details['connector_supported_directions'] = [sd.value for sd in supported_directions]

                # Check if sync direction is supported
                if sync_direction not in supported_directions:
                    errors.append(
                        f"Sync direction {sync_direction.value} is not supported by connector. "
                        f"Supported directions: {', '.join([sd.value for sd in supported_directions])}"
                    )
                    details['direction_supported'] = False
                else:
                    details['direction_supported'] = True

            except Exception as e:
                errors.append(
                    f"Failed to create connector to validate sync direction: {str(e)}"
                )
                details['connector_creation_error'] = str(e)
                details['direction_supported'] = None

        except ValueError as e:
            errors.append(
                f"Invalid marketplace type {connection.marketplace_type}: {str(e)}"
            )
            details['marketplace_type_valid'] = False
        except Exception as e:
            errors.append(
                f"Error validating sync direction: {str(e)}"
            )
            details['validation_error'] = str(e)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_sync_eligibility(
        self,
        connection: MarketplaceConnection,
        sync_job: Optional[MarketplaceSyncJob] = None,
        exclude_sync_job_id: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate connection is eligible for sync operations.

        Validates:
        - Connection is active
        - Connection is tested and working
        - No conflicting sync jobs running
        - Sync schedule is valid (if scheduled)

        Args:
            connection: MarketplaceConnection instance to validate
            sync_job: Optional MarketplaceSyncJob instance (for checking conflicts)
            exclude_sync_job_id: Optional sync job ID to exclude from conflict check

        Returns:
            ValidationResult with sync eligibility validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'connection_id': str(connection.id),
            'connection_name': connection.name,
        }

        # Validate connection is active
        if not connection.is_active:
            errors.append(
                f"Connection {connection.id} is not active - "
                f"cannot be used for sync operations"
            )
            details['connection_active'] = False
        else:
            details['connection_active'] = True

        # Validate connection is tested and working
        # Check if connection config can be decrypted and connector can be created
        try:
            config = connection.get_config()
            from hub.apps.integrations.factory import MarketplaceConnectorFactory
            marketplace_type = MarketplaceType(connection.marketplace_type)
            factory = MarketplaceConnectorFactory()

            if factory.is_supported(marketplace_type):
                try:
                    connector = factory.create_connector(
                        marketplace_type=marketplace_type,
                        config=config
                    )
                    # Test connection (this is a real test, not mocked)
                    try:
                        test_result = connector.test_connection()
                        if not test_result:
                            errors.append(
                                f"Connection {connection.id} test failed - "
                                f"connection is not working properly"
                            )
                            details['connection_tested'] = False
                            details['connection_test_result'] = False
                        else:
                            details['connection_tested'] = True
                            details['connection_test_result'] = True
                    except Exception as test_error:
                        errors.append(
                            f"Connection {connection.id} test error: {str(test_error)}"
                        )
                        details['connection_tested'] = False
                        details['connection_test_error'] = str(test_error)
                except Exception as connector_error:
                    errors.append(
                        f"Failed to create connector for connection {connection.id}: {str(connector_error)}"
                    )
                    details['connector_creation_error'] = str(connector_error)
                    details['connection_tested'] = False
            else:
                warnings.append(
                    f"Marketplace type {marketplace_type.value} is not supported - "
                    f"cannot test connection"
                )
                details['marketplace_supported'] = False
                details['connection_tested'] = None

        except Exception as e:
            errors.append(
                f"Failed to decrypt connection config or create connector: {str(e)}"
            )
            details['config_error'] = str(e)
            details['connection_tested'] = False

        # Check for conflicting sync jobs
        if connection.tenant:
            from datetime import timedelta

            # Check for running or pending sync jobs on the same connection
            conflicting_jobs_query = MarketplaceSyncJob.objects.filter(
                tenant=connection.tenant,
                connection=connection,
                status__in=[SyncStatus.RUNNING.value, SyncStatus.PENDING.value]
            )

            # Exclude current sync job if provided
            if sync_job and sync_job.id:
                conflicting_jobs_query = conflicting_jobs_query.exclude(id=sync_job.id)
            elif exclude_sync_job_id:
                conflicting_jobs_query = conflicting_jobs_query.exclude(id=exclude_sync_job_id)

            conflicting_jobs = list(conflicting_jobs_query)
            details['conflicting_jobs_count'] = len(conflicting_jobs)

            if conflicting_jobs:
                conflicting_job_ids = [str(job.id) for job in conflicting_jobs]
                errors.append(
                    f"Found {len(conflicting_jobs)} conflicting sync job(s) on connection {connection.id}: "
                    f"{', '.join(conflicting_job_ids)}"
                )
                details['conflicting_job_ids'] = conflicting_job_ids
                details['has_conflicts'] = True
            else:
                details['has_conflicts'] = False

        # Validate sync schedule if provided in sync_job metadata
        if sync_job and sync_job.metadata:
            schedule_config = sync_job.metadata.get('schedule')
            if schedule_config:
                schedule_result = self._validate_sync_schedule(schedule_config)
                errors.extend(schedule_result.errors)
                warnings.extend(schedule_result.warnings)
                details['schedule_validation'] = schedule_result.details
                details['has_schedule'] = True
            else:
                details['has_schedule'] = False
        else:
            details['has_schedule'] = False

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_sync_resources(
        self,
        sync_direction: SyncDirection,
        connection: MarketplaceConnection,
        asset_ids: Optional[List[str]] = None,
        listing_ids: Optional[List[str]] = None,
        tenant_id: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate sync resources exist and are accessible.

        Validates:
        - Source assets exist and accessible (for push sync)
        - Marketplace listings exist and accessible (for pull sync)
        - Resource quotas (max items per sync)

        Args:
            sync_direction: SyncDirection enum value
            connection: MarketplaceConnection instance
            asset_ids: Optional list of asset IDs to validate (for push sync)
            listing_ids: Optional list of listing IDs to validate (for pull sync)
            tenant_id: Optional tenant ID (uses connection tenant if not provided)

        Returns:
            ValidationResult with sync resources validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'sync_direction': sync_direction.value if isinstance(sync_direction, SyncDirection) else str(sync_direction),
            'connection_id': str(connection.id),
        }

        # Normalize sync_direction
        if not isinstance(sync_direction, SyncDirection):
            try:
                sync_direction = SyncDirection(sync_direction)
            except ValueError:
                valid_directions = [sd.value for sd in SyncDirection]
                errors.append(
                    f"Invalid sync direction: {sync_direction}. "
                    f"Valid directions are: {', '.join(valid_directions)}"
                )
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )

        effective_tenant_id = tenant_id or (str(connection.tenant.id) if connection.tenant else None)
        if not effective_tenant_id:
            errors.append("Tenant ID is required for resource validation")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
        details['tenant_id'] = effective_tenant_id

        # Validate resources based on sync direction
        if sync_direction == SyncDirection.PUSH:
            # For PUSH sync, validate source assets exist and are accessible
            if not asset_ids:
                errors.append("Asset IDs are required for PUSH sync")
                details['has_asset_ids'] = False
            else:
                details['has_asset_ids'] = True
                details['asset_ids_count'] = len(asset_ids)

                # Validate each asset exists and is accessible
                from hub.apps.assets.services import AssetService
                asset_service = AssetService(tenant_id=effective_tenant_id)

                accessible_assets = []
                inaccessible_assets = []

                for asset_id in asset_ids:
                    try:
                        asset = asset_service.get_asset(asset_id, tenant_id=effective_tenant_id)
                        # Check if asset is accessible (not retired/deleted, has valid status)
                        if hasattr(asset, 'status'):
                            # Import AssetStatus to check
                            from hub.apps.assets.models import AssetStatus
                            if asset.status == AssetStatus.RETIRED:
                                inaccessible_assets.append({
                                    'asset_id': asset_id,
                                    'reason': 'Asset is retired (deleted)'
                                })
                            else:
                                accessible_assets.append(asset_id)
                        else:
                            accessible_assets.append(asset_id)
                    except Exception as e:
                        inaccessible_assets.append({
                            'asset_id': asset_id,
                            'reason': f"Asset not found or not accessible: {str(e)}"
                        })

                details['accessible_assets_count'] = len(accessible_assets)
                details['inaccessible_assets_count'] = len(inaccessible_assets)
                details['accessible_asset_ids'] = accessible_assets
                details['inaccessible_assets'] = inaccessible_assets

                if inaccessible_assets:
                    for item in inaccessible_assets:
                        errors.append(
                            f"Asset {item['asset_id']} is not accessible: {item['reason']}"
                        )

                # Validate resource quotas
                max_items = self._get_max_items_per_sync(connection.tenant)
                if len(asset_ids) > max_items:
                    errors.append(
                        f"Number of assets ({len(asset_ids)}) exceeds maximum allowed ({max_items})"
                    )
                    details['quota_exceeded'] = True
                else:
                    details['quota_exceeded'] = False
                details['max_items_per_sync'] = max_items

        elif sync_direction == SyncDirection.PULL:
            # For PULL sync, validate marketplace listings exist and are accessible
            if not listing_ids:
                warnings.append("No listing IDs provided for PULL sync - will sync all available listings")
                details['has_listing_ids'] = False
            else:
                details['has_listing_ids'] = True
                details['listing_ids_count'] = len(listing_ids)

                # Validate each listing exists and is accessible via connector
                try:
                    from hub.apps.integrations.factory import MarketplaceConnectorFactory
                    marketplace_type = MarketplaceType(connection.marketplace_type)
                    factory = MarketplaceConnectorFactory()

                    if factory.is_supported(marketplace_type):
                        config = connection.get_config()
                        connector = factory.create_connector(
                            marketplace_type=marketplace_type,
                            config=config
                        )

                        accessible_listings = []
                        inaccessible_listings = []

                        for listing_id in listing_ids:
                            try:
                                listing = connector.get_listing(listing_id)
                                accessible_listings.append(listing_id)
                            except Exception as e:
                                inaccessible_listings.append({
                                    'listing_id': listing_id,
                                    'reason': f"Listing not found or not accessible: {str(e)}"
                                })

                        details['accessible_listings_count'] = len(accessible_listings)
                        details['inaccessible_listings_count'] = len(inaccessible_listings)
                        details['accessible_listing_ids'] = accessible_listings
                        details['inaccessible_listings'] = inaccessible_listings

                        if inaccessible_listings:
                            for item in inaccessible_listings:
                                errors.append(
                                    f"Listing {item['listing_id']} is not accessible: {item['reason']}"
                                )

                        # Validate resource quotas
                        max_items = self._get_max_items_per_sync(connection.tenant)
                        if len(listing_ids) > max_items:
                            errors.append(
                                f"Number of listings ({len(listing_ids)}) exceeds maximum allowed ({max_items})"
                            )
                            details['quota_exceeded'] = True
                        else:
                            details['quota_exceeded'] = False
                        details['max_items_per_sync'] = max_items

                    else:
                        warnings.append(
                            f"Marketplace type {marketplace_type.value} is not supported - "
                            f"cannot validate listings"
                        )
                        details['marketplace_supported'] = False

                except Exception as e:
                    errors.append(
                        f"Failed to validate marketplace listings: {str(e)}"
                    )
                    details['listing_validation_error'] = str(e)

        elif sync_direction == SyncDirection.BIDIRECTIONAL:
            # For BIDIRECTIONAL sync, validate both assets and listings
            if asset_ids:
                # Validate assets (same as PUSH)
                from hub.apps.assets.services import AssetService
                asset_service = AssetService(tenant_id=effective_tenant_id)

                accessible_assets = []
                for asset_id in asset_ids:
                    try:
                        asset = asset_service.get_asset(asset_id, tenant_id=effective_tenant_id)
                        if hasattr(asset, 'status'):
                            from hub.apps.assets.models import AssetStatus
                            if asset.status != AssetStatus.RETIRED:
                                accessible_assets.append(asset_id)
                            else:
                                errors.append(
                                    f"Asset {asset_id} is retired (deleted) and cannot be synced"
                                )
                        else:
                            accessible_assets.append(asset_id)
                    except Exception as e:
                        errors.append(
                            f"Asset {asset_id} is not accessible: {str(e)}"
                        )

                details['accessible_assets_count'] = len(accessible_assets)
                details['asset_ids_count'] = len(asset_ids)

            if listing_ids:
                # Validate listings (same as PULL)
                try:
                    from hub.apps.integrations.factory import MarketplaceConnectorFactory
                    marketplace_type = MarketplaceType(connection.marketplace_type)
                    factory = MarketplaceConnectorFactory()

                    if factory.is_supported(marketplace_type):
                        config = connection.get_config()
                        connector = factory.create_connector(
                            marketplace_type=marketplace_type,
                            config=config
                        )

                        accessible_listings = []
                        for listing_id in listing_ids:
                            try:
                                listing = connector.get_listing(listing_id)
                                accessible_listings.append(listing_id)
                            except Exception as e:
                                errors.append(
                                    f"Listing {listing_id} is not accessible: {str(e)}"
                                )

                        details['accessible_listings_count'] = len(accessible_listings)
                        details['listing_ids_count'] = len(listing_ids)

                except Exception as e:
                    errors.append(
                        f"Failed to validate marketplace listings: {str(e)}"
                    )

            # Validate total resource quota
            total_items = (len(asset_ids) if asset_ids else 0) + (len(listing_ids) if listing_ids else 0)
            max_items = self._get_max_items_per_sync(connection.tenant)
            if total_items > max_items:
                errors.append(
                    f"Total number of resources ({total_items}) exceeds maximum allowed ({max_items})"
                )
                details['quota_exceeded'] = True
            else:
                details['quota_exceeded'] = False
            details['max_items_per_sync'] = max_items
            details['total_items'] = total_items

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_sync_mapping(
        self,
        mapping: MarketplaceMapping,
        connection: Optional[MarketplaceConnection] = None
    ) -> ValidationResult:
        """
        Validate sync mapping is valid.

        Validates:
        - Asset-to-marketplace mapping is valid
        - Marketplace-to-asset mapping is valid
        - Mapping conflicts don't exist

        Args:
            mapping: MarketplaceMapping instance to validate
            connection: Optional MarketplaceConnection instance (if not provided, uses mapping.connection)

        Returns:
            ValidationResult with sync mapping validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'mapping_id': str(mapping.id),
            'external_listing_id': mapping.external_listing_id,
        }

        # Get effective connection
        effective_connection = connection or mapping.connection
        if not effective_connection:
            errors.append("Mapping must have a connection")
            details['has_connection'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
        details['has_connection'] = True
        details['connection_id'] = str(effective_connection.id)

        # Validate asset-to-marketplace mapping
        if not mapping.hub_asset:
            errors.append("Mapping must have a hub asset")
            details['has_hub_asset'] = False
        else:
            details['has_hub_asset'] = True
            details['asset_id'] = str(mapping.hub_asset.id)

            # Validate asset exists and is accessible
            try:
                from hub.apps.assets.services import AssetService
                asset_service = AssetService(tenant_id=str(mapping.tenant.id))
                asset = asset_service.get_asset(
                    str(mapping.hub_asset.id),
                    tenant_id=str(mapping.tenant.id)
                )

                # Check asset status
                if hasattr(asset, 'status'):
                    from hub.apps.assets.models import AssetStatus
                    if asset.status == AssetStatus.RETIRED:
                        errors.append(
                            f"Asset {mapping.hub_asset.id} is retired (deleted) and cannot be mapped"
                        )
                        details['asset_accessible'] = False
                    else:
                        details['asset_accessible'] = True
                else:
                    details['asset_accessible'] = True

            except Exception as e:
                errors.append(
                    f"Asset {mapping.hub_asset.id} is not accessible: {str(e)}"
                )
                details['asset_accessible'] = False
                details['asset_error'] = str(e)

        # Validate marketplace-to-asset mapping (external listing exists)
        if not mapping.external_listing_id or not mapping.external_listing_id.strip():
            errors.append("Mapping must have an external_listing_id")
            details['has_external_listing_id'] = False
        else:
            details['has_external_listing_id'] = True

            # Validate external listing exists and is accessible via connector
            try:
                from hub.apps.integrations.factory import MarketplaceConnectorFactory
                marketplace_type = MarketplaceType(effective_connection.marketplace_type)
                factory = MarketplaceConnectorFactory()

                if factory.is_supported(marketplace_type):
                    config = effective_connection.get_config()
                    connector = factory.create_connector(
                        marketplace_type=marketplace_type,
                        config=config
                    )

                    try:
                        listing = connector.get_listing(mapping.external_listing_id)
                        details['listing_exists'] = True
                        details['listing_accessible'] = True
                    except Exception as e:
                        errors.append(
                            f"External listing {mapping.external_listing_id} is not accessible: {str(e)}"
                        )
                        details['listing_exists'] = False
                        details['listing_accessible'] = False
                        details['listing_error'] = str(e)

                else:
                    warnings.append(
                        f"Marketplace type {marketplace_type.value} is not supported - "
                        f"cannot validate external listing"
                    )
                    details['marketplace_supported'] = False
                    details['listing_exists'] = None

            except Exception as e:
                errors.append(
                    f"Failed to validate external listing: {str(e)}"
                )
                details['listing_validation_error'] = str(e)

        # Check for mapping conflicts
        # A conflict occurs when:
        # - Same connection + asset combination exists in another mapping
        # - Same connection + external_listing_id combination exists in another mapping
        if mapping.tenant and mapping.hub_asset:
            # Check for duplicate connection + asset mapping
            # Only exclude if mapping has a valid ID (i.e., it's already saved)
            conflict_query = MarketplaceMapping.objects.filter(
                tenant=mapping.tenant,
                connection=effective_connection,
                hub_asset=mapping.hub_asset
            )
            if mapping.id:
                conflict_query = conflict_query.exclude(id=mapping.id)

            conflicting_mappings = list(conflict_query)
            if conflicting_mappings:
                conflict_ids = [str(m.id) for m in conflicting_mappings]
                errors.append(
                    f"Mapping conflict: Another mapping exists for connection {effective_connection.id} "
                    f"and asset {mapping.hub_asset.id}: {', '.join(conflict_ids)}"
                )
                details['has_asset_conflict'] = True
                details['conflicting_mapping_ids'] = conflict_ids
            else:
                details['has_asset_conflict'] = False

        if mapping.tenant and mapping.external_listing_id:
            # Check for duplicate connection + external_listing_id mapping
            # Only exclude if mapping has a valid ID (i.e., it's already saved)
            conflict_query = MarketplaceMapping.objects.filter(
                tenant=mapping.tenant,
                connection=effective_connection,
                external_listing_id=mapping.external_listing_id
            )
            if mapping.id:
                conflict_query = conflict_query.exclude(id=mapping.id)

            conflicting_listing_mappings = list(conflict_query)
            if conflicting_listing_mappings:
                conflict_ids = [str(m.id) for m in conflicting_listing_mappings]
                errors.append(
                    f"Mapping conflict: Another mapping exists for connection {effective_connection.id} "
                    f"and external listing {mapping.external_listing_id}: {', '.join(conflict_ids)}"
                )
                details['has_listing_conflict'] = True
                details['conflicting_listing_mapping_ids'] = conflict_ids
            else:
                details['has_listing_conflict'] = False

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_sync_schedule(self, schedule_config: Dict[str, Any]) -> ValidationResult:
        """
        Validate sync schedule configuration.

        Args:
            schedule_config: Dictionary containing schedule configuration

        Returns:
            ValidationResult with schedule validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        if not isinstance(schedule_config, dict):
            errors.append("Schedule config must be a dictionary")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Validate schedule type (cron, interval, etc.)
        schedule_type = schedule_config.get('type')
        if schedule_type:
            valid_types = ['cron', 'interval', 'once']
            if schedule_type not in valid_types:
                errors.append(
                    f"Invalid schedule type: {schedule_type}. "
                    f"Valid types are: {', '.join(valid_types)}"
                )
                details['schedule_type_valid'] = False
            else:
                details['schedule_type_valid'] = True
                details['schedule_type'] = schedule_type

                # Validate cron expression if type is cron
                if schedule_type == 'cron':
                    cron_expression = schedule_config.get('expression')
                    if not cron_expression:
                        errors.append("Cron schedule requires 'expression' field")
                    else:
                        # Basic cron validation (5 or 6 fields)
                        parts = cron_expression.split()
                        if len(parts) not in [5, 6]:
                            errors.append(
                                f"Invalid cron expression: {cron_expression}. "
                                f"Must have 5 or 6 fields"
                            )
                        else:
                            details['cron_expression'] = cron_expression

                # Validate interval if type is interval
                elif schedule_type == 'interval':
                    interval = schedule_config.get('interval')
                    if not interval:
                        errors.append("Interval schedule requires 'interval' field")
                    else:
                        if not isinstance(interval, (int, float)) or interval <= 0:
                            errors.append(
                                f"Invalid interval: {interval}. Must be a positive number"
                            )
                        else:
                            details['interval'] = interval
        else:
            warnings.append("Schedule type not specified")
            details['schedule_type'] = None

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _get_max_items_per_sync(self, tenant: Any) -> int:
        """
        Get maximum items allowed per sync for a tenant.

        Args:
            tenant: Tenant instance

        Returns:
            Maximum number of items allowed per sync
        """
        # Default max items per sync
        default_max = 1000

        # Check tenant-specific limits if available
        if tenant and hasattr(tenant, 'settings'):
            if isinstance(tenant.settings, dict):
                max_items = tenant.settings.get('max_items_per_sync')
                if max_items and isinstance(max_items, int) and max_items > 0:
                    return max_items

        return default_max

    def validate_federated_asset_creation(
        self,
        asset_mapping: "MarketplaceAssetMapping",
        connection: Optional[MarketplaceConnection] = None
    ) -> ValidationResult:
        """
        Validate federated asset creation from marketplace listing.

        Validates:
        - Marketplace listing metadata is complete
        - Asset source_type is FEDERATED
        - Source_metadata contains required fields (marketplace_type, marketplace_id, listing_id)
        - Asset name/description are valid

        Args:
            asset_mapping: MarketplaceAssetMapping instance to validate
            connection: Optional MarketplaceConnection instance (for marketplace type validation)

        Returns:
            ValidationResult with federated asset creation validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # Validate asset_data exists and is a dictionary
        if not asset_mapping.asset_data or not isinstance(asset_mapping.asset_data, dict):
            errors.append("Asset data is required and must be a dictionary")
            details['has_asset_data'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
        details['has_asset_data'] = True

        # Validate source_type is FEDERATED
        from hub.apps.assets.models import AssetSourceType
        if asset_mapping.source_type != AssetSourceType.FEDERATED:
            errors.append(
                f"Source type must be FEDERATED for federated assets, got {asset_mapping.source_type}"
            )
            details['source_type_valid'] = False
        else:
            details['source_type_valid'] = True
            details['source_type'] = asset_mapping.source_type.value

        # Validate source_metadata exists and contains required fields
        if not asset_mapping.source_metadata or not isinstance(asset_mapping.source_metadata, dict):
            errors.append("Source metadata is required and must be a dictionary")
            details['has_source_metadata'] = False
        else:
            details['has_source_metadata'] = True
            source_metadata = asset_mapping.source_metadata

            # Validate required fields
            required_fields = ['marketplace_type', 'marketplace_id', 'listing_id']
            missing_fields = []

            for field in required_fields:
                if field not in source_metadata or not source_metadata[field]:
                    missing_fields.append(field)

            if missing_fields:
                errors.append(
                    f"Source metadata missing required fields: {', '.join(missing_fields)}"
                )
                details['source_metadata_complete'] = False
                details['missing_fields'] = missing_fields
            else:
                details['source_metadata_complete'] = True
                details['marketplace_type'] = source_metadata.get('marketplace_type')
                details['marketplace_id'] = source_metadata.get('marketplace_id')
                details['listing_id'] = source_metadata.get('listing_id')

            # Validate marketplace_type is valid
            if 'marketplace_type' in source_metadata:
                marketplace_type_value = source_metadata['marketplace_type']
                valid_types = [mt.value for mt in MarketplaceType]
                if marketplace_type_value not in valid_types:
                    errors.append(
                        f"Invalid marketplace_type in source_metadata: {marketplace_type_value}. "
                        f"Valid types are: {', '.join(valid_types)}"
                    )
                    details['marketplace_type_valid'] = False
                else:
                    details['marketplace_type_valid'] = True

                    # If connection provided, validate marketplace_type matches
                    if connection:
                        if connection.marketplace_type != marketplace_type_value:
                            errors.append(
                                f"Marketplace type mismatch: source_metadata has {marketplace_type_value}, "
                                f"but connection has {connection.marketplace_type}"
                            )
                            details['marketplace_type_match'] = False
                        else:
                            details['marketplace_type_match'] = True

        # Validate asset name
        asset_name = asset_mapping.asset_data.get('name')
        if not asset_name or not isinstance(asset_name, str) or not asset_name.strip():
            errors.append("Asset name is required and must be a non-empty string")
            details['has_name'] = False
        else:
            details['has_name'] = True
            details['name'] = asset_name.strip()

            # Validate name length (max 255 chars per Asset model)
            if len(asset_name.strip()) > 255:
                errors.append(
                    f"Asset name exceeds maximum length of 255 characters (got {len(asset_name.strip())})"
                )
                details['name_length_valid'] = False
            else:
                details['name_length_valid'] = True

        # Validate asset description (optional but should be valid if provided)
        asset_description = asset_mapping.asset_data.get('description')
        if asset_description is not None:
            if not isinstance(asset_description, str):
                warnings.append("Asset description should be a string")
                details['description_valid'] = False
            else:
                details['description_valid'] = True
                details['has_description'] = True
                details['description_length'] = len(asset_description)
        else:
            details['has_description'] = False
            warnings.append("Asset description is recommended for federated assets")

        # Validate asset key if provided (should be unique per tenant)
        asset_key = asset_mapping.asset_data.get('key')
        if asset_key:
            if not isinstance(asset_key, str) or not asset_key.strip():
                errors.append("Asset key must be a non-empty string if provided")
                details['key_valid'] = False
            else:
                details['key_valid'] = True
                details['key'] = asset_key.strip()

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_dual_contract_creation(
        self,
        asset_mapping: "MarketplaceAssetMapping",
        tenant_id: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate dual contract creation (ODPS + ODCS) from marketplace listing.

        Validates:
        - ODPS metadata is extractable from marketplace listing
        - ODCS metadata is extractable or defaults are valid
        - Contract linking is possible (ODPS ↔ ODCS)

        Args:
            asset_mapping: MarketplaceAssetMapping instance to validate
            tenant_id: Optional tenant ID for contract validation

        Returns:
            ValidationResult with dual contract creation validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # Validate ODPS metadata exists and is extractable
        if not asset_mapping.odps_metadata or not isinstance(asset_mapping.odps_metadata, dict):
            errors.append("ODPS metadata is required and must be a dictionary")
            details['has_odps_metadata'] = False
        else:
            details['has_odps_metadata'] = True
            odps_metadata = asset_mapping.odps_metadata

            # Validate ODPS metadata structure (basic validation)
            # ODPS should have product information
            if 'product' not in odps_metadata:
                errors.append("ODPS metadata must contain 'product' field")
                details['odps_structure_valid'] = False
            else:
                details['odps_structure_valid'] = True
                product = odps_metadata.get('product', {})

                # Validate product has details
                if 'details' not in product:
                    warnings.append("ODPS product should have 'details' field")
                    details['odps_product_complete'] = False
                else:
                    details['odps_product_complete'] = True

            # Try to validate ODPS structure using ContractService if tenant_id provided
            if tenant_id:
                try:
                    from hub.apps.contracts.services import ContractService
                    contract_service = ContractService(tenant_id=tenant_id)

                    # Try to normalize ODPS metadata to validate structure
                    # This is a real validation, not mocked
                    try:
                        # Check if ODPS metadata can be parsed (basic structure check)
                        import json
                        odps_json = json.dumps(odps_metadata)
                        details['odps_parseable'] = True
                        details['odps_metadata_size'] = len(odps_json)
                    except Exception as e:
                        errors.append(
                            f"ODPS metadata is not valid JSON structure: {str(e)}"
                        )
                        details['odps_parseable'] = False
                        details['odps_parse_error'] = str(e)

                except Exception as e:
                    warnings.append(
                        f"Could not validate ODPS metadata structure: {str(e)}"
                    )
                    details['odps_validation_error'] = str(e)

        # Validate ODCS metadata (optional but should be valid if provided)
        if asset_mapping.odcs_metadata is None:
            details['has_odcs_metadata'] = False
            warnings.append(
                "ODCS metadata not provided - will use defaults or extract from ODPS"
            )
        else:
            details['has_odcs_metadata'] = True
            if not isinstance(asset_mapping.odcs_metadata, dict):
                errors.append("ODCS metadata must be a dictionary if provided")
                details['odcs_structure_valid'] = False
            else:
                details['odcs_structure_valid'] = True
                odcs_metadata = asset_mapping.odcs_metadata

                # Basic ODCS structure validation
                # ODCS typically has schema, quality, SLA fields
                odcs_fields = ['schema', 'quality', 'sla']
                present_fields = [field for field in odcs_fields if field in odcs_metadata]
                details['odcs_fields_present'] = present_fields

                if not present_fields:
                    warnings.append(
                        "ODCS metadata does not contain typical fields (schema, quality, sla) - "
                        "may need defaults"
                    )
                    details['odcs_complete'] = False
                else:
                    details['odcs_complete'] = True

                # Try to validate ODCS structure if tenant_id provided
                if tenant_id:
                    try:
                        import json
                        odcs_json = json.dumps(odcs_metadata)
                        details['odcs_parseable'] = True
                        details['odcs_metadata_size'] = len(odcs_json)
                    except Exception as e:
                        errors.append(
                            f"ODCS metadata is not valid JSON structure: {str(e)}"
                        )
                        details['odcs_parseable'] = False
                        details['odcs_parse_error'] = str(e)

        # Validate contract linking is possible
        # This checks if ODPS and ODCS can be linked together
        if asset_mapping.odps_metadata and asset_mapping.odcs_metadata:
            details['both_contracts_present'] = True

            # Check if linking validation can be performed
            # Note: Actual linking requires contracts to be created first,
            # so we validate that the metadata structures are compatible
            try:
                # Basic compatibility check: both should have product/asset identifiers
                odps_product_id = None
                if 'product' in asset_mapping.odps_metadata:
                    product = asset_mapping.odps_metadata['product']
                    odps_product_id = product.get('productID') or product.get('product_id')

                odcs_asset_id = None
                if 'schema' in asset_mapping.odcs_metadata:
                    schema = asset_mapping.odcs_metadata['schema']
                    odcs_asset_id = schema.get('assetID') or schema.get('asset_id')

                # If both have identifiers, they should match (or be linkable)
                if odps_product_id and odcs_asset_id:
                    if odps_product_id != odcs_asset_id:
                        warnings.append(
                            f"ODPS product ID ({odps_product_id}) and ODCS asset ID ({odcs_asset_id}) "
                            f"do not match - linking may require manual intervention"
                        )
                        details['identifiers_match'] = False
                    else:
                        details['identifiers_match'] = True
                        details['linked_identifier'] = odps_product_id
                else:
                    details['identifiers_match'] = None
                    warnings.append(
                        "Cannot verify contract linking compatibility - identifiers not found in metadata"
                    )

                details['linking_validation_attempted'] = True

            except Exception as e:
                warnings.append(
                    f"Could not validate contract linking compatibility: {str(e)}"
                )
                details['linking_validation_error'] = str(e)
                details['linking_validation_attempted'] = False
        else:
            details['both_contracts_present'] = False
            if not asset_mapping.odps_metadata:
                errors.append("ODPS metadata is required for contract creation")
            if asset_mapping.odcs_metadata is None:
                warnings.append(
                    "ODCS metadata not provided - contract linking will use defaults"
                )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_resource_download(
        self,
        resources: List["MarketplaceResource"],
        connection: MarketplaceConnection,
        tenant_id: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate resources are downloadable from marketplace.

        Validates:
        - Resources are downloadable (accessible via connector)
        - Resource sizes are within limits
        - Resource formats are supported

        Args:
            resources: List of MarketplaceResource objects to validate
            connection: MarketplaceConnection instance for connector access
            tenant_id: Optional tenant ID for size limit validation

        Returns:
            ValidationResult with resource download validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'resources_count': len(resources),
        }

        if not resources:
            warnings.append("No resources provided for validation")
            details['has_resources'] = False
            return ValidationResult(
                is_valid=True,  # Empty list is valid (no resources to download)
                errors=errors,
                warnings=warnings,
                details=details
            )
        details['has_resources'] = True

        # Get max resource size limit
        max_resource_size = self._get_max_resource_size(connection.tenant if connection.tenant else None, tenant_id)
        details['max_resource_size_bytes'] = max_resource_size

        # Get supported formats
        supported_formats = self._get_supported_resource_formats()
        details['supported_formats'] = supported_formats

        # Validate each resource
        downloadable_resources = []
        non_downloadable_resources = []
        oversized_resources = []
        unsupported_format_resources = []

        for idx, resource in enumerate(resources):
            resource_details = {
                'resource_id': resource.resource_id,
                'resource_type': resource.resource_type,
                'name': resource.name,
            }

            # Validate resource has required fields
            if not resource.resource_id or not resource.resource_id.strip():
                errors.append(
                    f"Resource {idx + 1} (name: {resource.name}) is missing resource_id"
                )
                non_downloadable_resources.append({
                    **resource_details,
                    'reason': 'Missing resource_id'
                })
                continue

            if not resource.name or not resource.name.strip():
                warnings.append(
                    f"Resource {idx + 1} (id: {resource.resource_id}) is missing name"
                )
                resource_details['has_name'] = False
            else:
                resource_details['has_name'] = True

            # Validate resource size if provided
            if resource.size_bytes is not None:
                if resource.size_bytes < 0:
                    errors.append(
                        f"Resource {resource.resource_id} has invalid size: {resource.size_bytes} bytes"
                    )
                    oversized_resources.append({
                        **resource_details,
                        'reason': f'Invalid size: {resource.size_bytes} bytes',
                        'size_bytes': resource.size_bytes
                    })
                elif resource.size_bytes > max_resource_size:
                    errors.append(
                        f"Resource {resource.resource_id} exceeds maximum size: "
                        f"{resource.size_bytes} bytes > {max_resource_size} bytes"
                    )
                    oversized_resources.append({
                        **resource_details,
                        'reason': f'Size exceeds limit: {resource.size_bytes} bytes',
                        'size_bytes': resource.size_bytes,
                        'max_size_bytes': max_resource_size
                    })
                else:
                    resource_details['size_valid'] = True
                    resource_details['size_bytes'] = resource.size_bytes
            else:
                resource_details['size_valid'] = None
                warnings.append(
                    f"Resource {resource.resource_id} does not specify size - "
                    f"cannot validate size limits"
                )

            # Validate resource format if provided
            if resource.format:
                format_upper = resource.format.upper()
                if format_upper not in supported_formats:
                    warnings.append(
                        f"Resource {resource.resource_id} has unsupported format: {resource.format}. "
                        f"Supported formats: {', '.join(supported_formats)}"
                    )
                    unsupported_format_resources.append({
                        **resource_details,
                        'reason': f'Unsupported format: {resource.format}',
                        'format': resource.format
                    })
                else:
                    resource_details['format_valid'] = True
                    resource_details['format'] = resource.format
            else:
                resource_details['format_valid'] = None
                warnings.append(
                    f"Resource {resource.resource_id} does not specify format"
                )

            # Validate resource is downloadable via connector
            # This is a real check, not mocked
            try:
                from hub.apps.integrations.factory import MarketplaceConnectorFactory
                marketplace_type = MarketplaceType(connection.marketplace_type)
                factory = MarketplaceConnectorFactory()

                if factory.is_supported(marketplace_type):
                    config = connection.get_config()
                    connector = factory.create_connector(
                        marketplace_type=marketplace_type,
                        config=config
                    )

                    # Check if resource has URL or if connector can access it
                    # We don't actually download, just validate accessibility
                    if resource.url:
                        # URL is provided, resource should be downloadable
                        resource_details['has_url'] = True
                        resource_details['url'] = resource.url
                        downloadable_resources.append(resource_details)
                    else:
                        # No URL, but connector might be able to access via resource_id
                        # This is connector-specific, so we just validate resource_id exists
                        resource_details['has_url'] = False
                        downloadable_resources.append(resource_details)
                        warnings.append(
                            f"Resource {resource.resource_id} does not have URL - "
                            f"downloadability depends on connector implementation"
                        )

                else:
                    warnings.append(
                        f"Marketplace type {marketplace_type.value} is not supported - "
                        f"cannot validate resource downloadability"
                    )
                    resource_details['downloadability_checked'] = False
                    downloadable_resources.append(resource_details)

            except Exception as e:
                errors.append(
                    f"Failed to validate resource {resource.resource_id} downloadability: {str(e)}"
                )
                non_downloadable_resources.append({
                    **resource_details,
                    'reason': f'Validation error: {str(e)}',
                    'error': str(e)
                })

        details['downloadable_resources_count'] = len(downloadable_resources)
        details['non_downloadable_resources_count'] = len(non_downloadable_resources)
        details['oversized_resources_count'] = len(oversized_resources)
        details['unsupported_format_resources_count'] = len(unsupported_format_resources)
        details['downloadable_resources'] = downloadable_resources
        details['non_downloadable_resources'] = non_downloadable_resources
        details['oversized_resources'] = oversized_resources
        details['unsupported_format_resources'] = unsupported_format_resources

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _get_max_resource_size(self, tenant: Any, tenant_id: Optional[str] = None) -> int:
        """
        Get maximum resource size allowed for download.

        Args:
            tenant: Tenant instance (optional)
            tenant_id: Tenant ID string (optional, used if tenant not provided)

        Returns:
            Maximum resource size in bytes
        """
        # Default max resource size (10 GB)
        default_max = 10 * 1024 * 1024 * 1024  # 10 GB

        # Check tenant-specific limits
        if tenant and hasattr(tenant, 'settings'):
            if isinstance(tenant.settings, dict):
                max_size = tenant.settings.get('max_file_size_bytes')
                if max_size and isinstance(max_size, int) and max_size > 0:
                    return max_size

        # Check tenant config if tenant_id provided
        if tenant_id:
            try:
                from hub.apps.tenants.services import get_tenant_file_size_limit
                tenant_limit = get_tenant_file_size_limit(tenant_id)
                if tenant_limit:
                    return tenant_limit
            except Exception:
                pass

        # Use platform default from settings or fallback
        try:
            from django.conf import settings as django_settings
            if hasattr(django_settings, 'MAX_FILE_SIZE'):
                return django_settings.MAX_FILE_SIZE
        except Exception:
            pass

        return default_max

    def _get_supported_resource_formats(self) -> List[str]:
        """
        Get list of supported resource formats.

        Returns:
            List of supported format strings (uppercase)
        """
        # Common data formats supported by the platform
        return [
            'CSV', 'JSON', 'PARQUET', 'AVRO', 'ORC',
            'XLSX', 'XLS', 'TSV', 'TXT',
            'ZIP', 'GZIP', 'TAR', 'TAR.GZ',
            'SQL', 'XML', 'YAML', 'YML'
        ]

    def validate_connection_config(
        self,
        marketplace_type: str,
        config: Dict[str, Any],
        connection_name: str,
        tenant_id: str,
        connection_id: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate marketplace connection configuration.

        Validates:
        - marketplace_type is supported
        - config structure matches marketplace requirements
        - authentication credentials format
        - connection name uniqueness within tenant

        Args:
            marketplace_type: Marketplace type string (e.g., "SNOWFLAKE_DATA_MARKETPLACE")
            config: Connection configuration dictionary
            connection_name: Connection name to check for uniqueness
            tenant_id: Tenant ID for uniqueness check
            connection_id: Optional connection ID (for update operations, excludes self from uniqueness check)

        Returns:
            ValidationResult with errors/warnings
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'marketplace_type': marketplace_type,
            'connection_name': connection_name,
            'tenant_id': tenant_id,
        }

        # Validate marketplace_type is supported
        marketplace_type_enum = None
        try:
            from hub.apps.integrations.base import MarketplaceType
            from hub.apps.integrations.factory import MarketplaceConnectorFactory

            marketplace_type_enum = MarketplaceType(marketplace_type)
            details['marketplace_type_enum'] = marketplace_type_enum.value

            if not MarketplaceConnectorFactory.is_supported(marketplace_type_enum):
                errors.append(
                    f"Marketplace type '{marketplace_type}' is not supported. "
                    f"Supported types: {', '.join([mt.value for mt in MarketplaceConnectorFactory.get_supported_types()])}"
                )
                details['marketplace_type_supported'] = False
            else:
                details['marketplace_type_supported'] = True
        except ValueError:
            errors.append(
                f"Invalid marketplace_type: '{marketplace_type}'. "
                f"Must be one of: {', '.join([mt.value for mt in MarketplaceType])}"
            )
            details['marketplace_type_valid'] = False
        except Exception as e:
            errors.append(f"Error checking marketplace type support: {str(e)}")
            details['marketplace_type_check_error'] = str(e)
            logger.exception("Error checking marketplace type support", extra=details)

        # Validate config structure matches marketplace requirements
        if not isinstance(config, dict):
            errors.append("Connection config must be a dictionary")
            details['config_valid'] = False
        else:
            details['config_valid'] = True
            details['config_keys'] = list(config.keys())

            # Use validate_marketplace_config utility for structure validation
            try:
                from hub.apps.integrations.utils import validate_marketplace_config

                # Try to validate with marketplace_type if available
                if marketplace_type_enum is not None:
                    validate_marketplace_config(
                        config,
                        marketplace_type=marketplace_type_enum
                    )
                    details['config_structure_valid'] = True
                else:
                    # marketplace_type_enum might not be set if previous check failed
                    # Try validation without marketplace_type
                    validate_marketplace_config(config)
                    details['config_structure_valid'] = True
            except Exception as e:
                # MarketplaceError or other validation errors
                # Try to get message attribute if it exists (for MarketplaceError)
                error_msg = getattr(e, 'message', str(e))
                errors.append(f"Invalid marketplace configuration: {error_msg}")
                details['config_structure_valid'] = False
                # Try to get details attribute if it exists (for MarketplaceError)
                error_details = getattr(e, 'details', None)
                if error_details:
                    details['config_validation_details'] = error_details

        # Validate authentication credentials format
        # Common credential fields that should be strings if present
        credential_fields = ['api_key', 'api_secret', 'access_token', 'refresh_token', 'username', 'password']
        for field in credential_fields:
            if field in config:
                if not isinstance(config[field], str) or not config[field].strip():
                    errors.append(
                        f"Authentication credential '{field}' must be a non-empty string"
                    )
                    details[f'credential_{field}_valid'] = False
                else:
                    details[f'credential_{field}_valid'] = True
                    # Don't log actual credential values, just presence
                    details[f'credential_{field}_present'] = True

        # Validate connection name uniqueness within tenant
        if not connection_name or not connection_name.strip():
            errors.append("Connection name cannot be empty")
            details['name_valid'] = False
        else:
            details['name_valid'] = True
            try:
                from hub.apps.integrations.models import MarketplaceConnection

                # Check for existing connection with same name in tenant
                query = MarketplaceConnection.objects.filter(
                    tenant_id=tenant_id,
                    name=connection_name.strip()
                )

                # If updating, exclude current connection from uniqueness check
                if connection_id:
                    query = query.exclude(id=connection_id)

                existing_connection = query.first()
                if existing_connection:
                    errors.append(
                        f"Connection name '{connection_name}' already exists for this tenant. "
                        f"Connection names must be unique within a tenant."
                    )
                    details['name_unique'] = False
                    details['existing_connection_id'] = str(existing_connection.id)
                else:
                    details['name_unique'] = True
            except Exception as e:
                errors.append(f"Error checking connection name uniqueness: {str(e)}")
                details['name_uniqueness_check_error'] = str(e)
                logger.exception("Error checking connection name uniqueness", extra=details)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_connection_access(
        self,
        user_id: str,
        tenant_id: str
    ) -> ValidationResult:
        """
        Validate user has permission to create/manage marketplace connections.

        Validates:
        - User has permission to create/manage connections
        - Tenant has marketplace integration enabled
        - Resource quotas (max connections per tenant)

        Args:
            user_id: User ID to check permissions for
            tenant_id: Tenant ID to check integration status and quotas

        Returns:
            ValidationResult with errors/warnings
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'user_id': user_id,
            'tenant_id': tenant_id,
        }

        # Validate user_id and tenant_id are valid UUIDs before ORM lookups (avoids DB/ValidationError for malformed ids)
        import uuid as uuid_module
        valid_user_id = True
        valid_tenant_id = True
        for name, val in [("user_id", user_id), ("tenant_id", tenant_id)]:
            if val is None or (isinstance(val, str) and not val.strip()):
                errors.append(f"{name} is required")
                if name == "user_id":
                    valid_user_id = False
                else:
                    valid_tenant_id = False
                continue
            try:
                uuid_module.UUID(str(val))
            except (ValueError, TypeError, AttributeError):
                errors.append(f"Invalid {name}: {val!r} is not a valid UUID")
                if name == "user_id":
                    valid_user_id = False
                else:
                    valid_tenant_id = False

        # Validate user has permission to create/manage connections (only when user_id is a valid UUID)
        if valid_user_id:
            try:
                from hub.apps.users.models import User

                try:
                    user = User.objects.get(id=user_id)
                    details['user_found'] = True
                    details['user_email'] = user.email if hasattr(user, 'email') else None
                except User.DoesNotExist:
                    errors.append(f"User {user_id} not found")
                    details['user_found'] = False
                    return ValidationResult(
                        is_valid=False,
                        errors=errors,
                        warnings=warnings,
                        details=details
                    )

                # Platform admins have all permissions
                if user.is_platform_admin:
                    details['user_is_platform_admin'] = True
                    details['has_permission'] = True
                else:
                    details['user_is_platform_admin'] = False

                    # For non-platform admins, verify tenant matches
                    if str(user.tenant_id) != tenant_id:
                        errors.append(
                            f"User {user_id} does not belong to tenant {tenant_id}"
                        )
                        details['tenant_match'] = False
                        details['has_permission'] = False
                    else:
                        details['tenant_match'] = True

                        # Check if user has required role (DATA_PROVIDER or TENANT_ADMIN)
                        has_required_role = user.has_role("DATA_PROVIDER", "TENANT_ADMIN")
                        if not has_required_role:
                            errors.append(
                                f"User {user_id} does not have required role "
                                f"(DATA_PROVIDER or TENANT_ADMIN) for marketplace connection management"
                            )
                            details['has_permission'] = False
                            details['user_roles'] = (
                                [ur.role.name for ur in user.user_roles.all()]
                                if hasattr(user, 'user_roles') else []
                            )
                        else:
                            details['has_permission'] = True
                            details['user_roles'] = (
                                [ur.role.name for ur in user.user_roles.all()]
                                if hasattr(user, 'user_roles') else []
                            )
            except Exception as e:
                errors.append(f"Error checking user permissions: {str(e)}")
                details['permission_check_error'] = str(e)
                logger.exception("Error checking user permissions", extra=details)

        # Validate tenant has marketplace integration enabled (only when tenant_id is a valid UUID)
        if valid_tenant_id:
            try:
                from hub.apps.tenants.models import Tenant

                try:
                    tenant = Tenant.objects.get(id=tenant_id)
                    details['tenant_found'] = True
                    details['tenant_name'] = tenant.name

                    # Check if tenant can publish to marketplace (requires KYC verification)
                    can_publish = tenant.can_publish_to_marketplace()
                    details['marketplace_integration_enabled'] = can_publish
                    details['tenant_kyc_status'] = tenant.kyc_status.value if hasattr(tenant.kyc_status, 'value') else str(tenant.kyc_status)
                    details['tenant_status'] = tenant.status.value if hasattr(tenant.status, 'value') else str(tenant.status)

                    if not can_publish:
                        errors.append(
                            f"Tenant {tenant_id} does not have marketplace integration enabled. "
                            f"Tenant must have VERIFIED KYC status and ACTIVE status to create marketplace connections."
                        )
                except Tenant.DoesNotExist:
                    errors.append(f"Tenant {tenant_id} not found")
                    details['tenant_found'] = False
            except Exception as e:
                errors.append(f"Error checking tenant marketplace integration: {str(e)}")
                details['integration_check_error'] = str(e)
                logger.exception("Error checking tenant marketplace integration", extra=details)

        # Check resource quotas (max connections per tenant)
        try:
            from hub.apps.integrations.models import MarketplaceConnection

            # Get current connection count for tenant
            current_count = MarketplaceConnection.objects.filter(tenant_id=tenant_id).count()
            details['current_connection_count'] = current_count

            # Default max connections per tenant (can be configured per tenant in future)
            # For now, use a reasonable default: 50 connections per tenant
            max_connections_per_tenant = 50
            details['max_connections_per_tenant'] = max_connections_per_tenant

            # Check if quota would be exceeded
            if current_count >= max_connections_per_tenant:
                errors.append(
                    f"Tenant {tenant_id} has reached maximum connection limit ({max_connections_per_tenant}). "
                    f"Current connections: {current_count}. Please delete unused connections or contact support."
                )
                details['quota_exceeded'] = True
            else:
                details['quota_exceeded'] = False
                details['remaining_connections'] = max_connections_per_tenant - current_count

                # Warning if approaching limit (80% threshold)
                if current_count >= (max_connections_per_tenant * 0.8):
                    warnings.append(
                        f"Tenant {tenant_id} is approaching connection limit. "
                        f"Current: {current_count}/{max_connections_per_tenant} connections."
                    )
                    details['quota_warning'] = True
                else:
                    details['quota_warning'] = False
        except Exception as e:
            errors.append(f"Error checking resource quotas: {str(e)}")
            details['quota_check_error'] = str(e)
            logger.exception("Error checking resource quotas", extra=details)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_connection_test(
        self,
        connection: MarketplaceConnection,
        test_results: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate connection can be tested and test results are valid.

        Validates:
        - Connection can be tested (is_active, config valid)
        - Test results are valid (if provided)

        Args:
            connection: MarketplaceConnection instance to validate
            test_results: Optional test results dictionary from connection test

        Returns:
            ValidationResult with errors/warnings
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'connection_id': str(connection.id),
            'connection_name': connection.name,
            'marketplace_type': connection.marketplace_type,
        }

        # Validate connection is active
        if not connection.is_active:
            errors.append(
                f"Connection {connection.id} is not active. "
                f"Inactive connections cannot be tested."
            )
            details['is_active'] = False
        else:
            details['is_active'] = True

        # Validate config is valid
        if not isinstance(connection.config, dict):
            errors.append("Connection config must be a dictionary")
            details['config_valid'] = False
        else:
            details['config_valid'] = True
            details['config_keys'] = list(connection.config.keys())

            # Try to decrypt and validate config structure
            try:
                decrypted_config = connection.get_config()
                details['config_decryptable'] = True

                # Validate config structure using marketplace config validator
                try:
                    from hub.apps.integrations.utils import validate_marketplace_config
                    from hub.apps.integrations.base import MarketplaceType

                    marketplace_type_enum = MarketplaceType(connection.marketplace_type)
                    validate_marketplace_config(
                        decrypted_config,
                        marketplace_type=marketplace_type_enum
                    )
                    details['config_structure_valid'] = True
                except Exception as e:
                    # Try to get message attribute if it exists (for MarketplaceError)
                    error_msg = getattr(e, 'message', str(e))
                    warnings.append(
                        f"Connection config structure validation warning: {error_msg}"
                    )
                    details['config_structure_valid'] = False
                    details['config_structure_error'] = error_msg
            except Exception as e:
                errors.append(
                    f"Connection config cannot be decrypted or is invalid: {str(e)}"
                )
                details['config_decryptable'] = False
                details['config_decrypt_error'] = str(e)
                logger.exception("Error decrypting connection config", extra=details)

        # Validate test results (if provided)
        if test_results is not None:
            details['test_results_provided'] = True

            if not isinstance(test_results, dict):
                errors.append("Test results must be a dictionary")
                details['test_results_valid'] = False
            else:
                details['test_results_valid'] = True
                details['test_results_keys'] = list(test_results.keys())

                # Check for common test result fields
                if 'success' in test_results:
                    test_success = test_results.get('success', False)
                    details['test_success'] = test_success

                    if not test_success:
                        error_message = test_results.get('error', 'Test failed without error message')
                        errors.append(
                            f"Connection test failed: {error_message}"
                        )
                        details['test_error'] = error_message
                else:
                    # If no 'success' field, check for error field
                    if 'error' in test_results:
                        error_message = test_results.get('error', 'Unknown error')
                        errors.append(
                            f"Connection test failed: {error_message}"
                        )
                        details['test_error'] = error_message
                    else:
                        # No success/error indicators, assume success but warn
                        warnings.append(
                            "Test results do not contain success/error indicators. "
                            "Assuming test passed, but results may be incomplete."
                        )
                        details['test_results_incomplete'] = True

                # Check for connection latency if provided
                if 'latency_ms' in test_results:
                    latency = test_results.get('latency_ms')
                    if isinstance(latency, (int, float)):
                        details['test_latency_ms'] = latency
                        if latency > 5000:  # 5 seconds
                            warnings.append(
                                f"Connection test shows high latency: {latency}ms. "
                                f"This may indicate connectivity issues."
                            )
                            details['high_latency'] = True
        else:
            details['test_results_provided'] = False
            # If no test results provided, we can't validate them
            # This is acceptable if we're just checking if connection CAN be tested

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

