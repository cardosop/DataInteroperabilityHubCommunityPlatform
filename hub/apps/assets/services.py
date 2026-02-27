"""
Asset Service

Business logic for asset operations.
"""

from typing import Any, Dict, List, Optional

from django.db import transaction

from hub.apps.assets.business_rules import AssetsBusinessRules
from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility, ComplianceStatus, DQStatus
from hub.apps.core.events.service_publishers import AssetEventPublisher
from hub.apps.core.services.base import BaseService, ConflictError, NotFoundError, ValidationError


class AssetService(BaseService, AssetEventPublisher):
    """
    Service for asset operations.

    Provides business logic for creating, retrieving, updating, and managing assets.
    """

    service_name = "asset_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize AssetService.

        Args:
            tenant_id: Tenant ID
            user_id: User ID
        """
        # Set attributes directly (BaseService doesn't have __init__)
        self.tenant_id = tenant_id
        self.user_id = user_id
        # Initialize event publisher
        AssetEventPublisher.__init__(self)

    def get_asset(self, asset_id: str, tenant_id: Optional[str] = None) -> Asset:
        """
        Get asset by ID.

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            Asset instance

        Raises:
            NotFoundError: If asset not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        # Normalize to str so both UUID and str inputs work (e.g. from serializer validated_data)
        asset_id_str = str(asset_id) if not isinstance(asset_id, str) else asset_id
        tenant_id_str = str(effective_tenant_id) if not isinstance(effective_tenant_id, str) else effective_tenant_id

        # Validate UUID format before querying
        try:
            import uuid
            uuid.UUID(asset_id_str)
            uuid.UUID(tenant_id_str)
        except (ValueError, TypeError) as e:
            raise NotFoundError(
                f"Invalid UUID format: {str(e)}",
                code="NOT_FOUND",
                details={"asset_id": asset_id_str, "tenant_id": tenant_id_str}
            )

        return self.execute_with_metrics(
            operation="get_asset",
            tenant_id=tenant_id_str,
            func=lambda: self.get_resource_or_raise(Asset, asset_id_str, tenant_id=tenant_id_str),
        )

    def get_assets_by_status(
        self, status: AssetStatus, tenant_id: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Asset]:
        """
        Get assets by status.

        Args:
            status: Asset status
            tenant_id: Tenant ID
            limit: Optional limit on results

        Returns:
            List of Asset instances
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _get_assets():
            queryset = Asset.objects.filter(tenant_id=effective_tenant_id, status=status)
            if limit:
                queryset = queryset[:limit]
            return list(queryset)

        return self.execute_with_metrics(
            operation="get_assets_by_status", tenant_id=effective_tenant_id, func=_get_assets
        )

    def is_asset_active(self, asset_id: str, tenant_id: Optional[str] = None) -> bool:
        """
        Check if asset is active.

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID

        Returns:
            True if asset is active, False otherwise

        Raises:
            NotFoundError: If asset not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _check():
            asset = self.get_resource_or_raise(Asset, asset_id, tenant_id=effective_tenant_id)
            return asset.status == AssetStatus.ACTIVE

        return self.execute_with_metrics(
            operation="is_asset_active", tenant_id=effective_tenant_id, func=_check
        )

    def validate_asset_eligibility(
        self, asset_id: str, tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate asset eligibility for operations (e.g., marketplace publication).

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID

        Returns:
            Dictionary with validation results

        Raises:
            NotFoundError: If asset not found
            ValidationError: If asset is not eligible
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _validate():
            asset = self.get_resource_or_raise(Asset, asset_id, tenant_id=effective_tenant_id)

            validation_results = {"asset_id": str(asset.id), "eligible": True, "blockers": []}

            # Check asset status
            if asset.status != AssetStatus.ACTIVE:
                validation_results["blockers"].append(
                    f"Asset status must be ACTIVE (current: {asset.status})"
                )
                validation_results["eligible"] = False

            # Check DQ status
            if asset.dq_status != DQStatus.PASS:
                validation_results["blockers"].append(
                    f"Asset DQ status must be PASS (current: {asset.dq_status})"
                )
                validation_results["eligible"] = False

            # Check compliance status
            if asset.compliance_status != ComplianceStatus.PASS:
                validation_results["blockers"].append(
                    f"Asset compliance status must be PASS (current: {asset.compliance_status})"
                )
                validation_results["eligible"] = False

            if not validation_results["eligible"]:
                raise ValidationError(
                    f"Asset {asset_id} is not eligible", details=validation_results
                )

            return validation_results

        return self.execute_with_metrics(
            operation="validate_asset_eligibility", tenant_id=effective_tenant_id, func=_validate
        )

    @transaction.atomic
    def create_asset(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        key: str = None,
        name: str = None,
        description: Optional[str] = None,
        domain: Optional[str] = None,
        **kwargs,
    ) -> Asset:
        """
        Create a new asset.

        Args:
            tenant_id: Tenant ID
            user_id: User ID
            key: Asset key (unique per tenant)
            name: Asset name
            description: Optional description
            domain: Optional domain
            **kwargs: Additional asset fields

        Returns:
            Created asset instance

        Raises:
            ValidationError: If validation fails
            ConflictError: If asset with same key already exists
        """
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")
        if not key:
            raise ValidationError("key is required")
        if not name:
            raise ValidationError("name is required")

        def _create():
            # Build validation payload (unsaved asset) and run business rules
            payload_asset = Asset(
                tenant_id=effective_tenant_id,
                key=key,
                name=name,
                description=description or "",
                domain=domain or "",
                status=AssetStatus.DRAFT,
                visibility=kwargs.get("visibility", AssetVisibility.INTERNAL),
            )
            rules = AssetsBusinessRules(
                tenant_id=effective_tenant_id,
                user_id=effective_user_id,
            )
            result = rules.validate(
                asset=payload_asset,
                validation_type="structure",
            )
            if not result.is_valid:
                raise ValidationError(
                    "; ".join(result.errors),
                    code="BUSINESS_RULES_VALIDATION",
                    details=result.details,
                )

            # Check for duplicate key
            if Asset.objects.filter(tenant_id=effective_tenant_id, key=key).exists():
                raise ConflictError(
                    f"Asset with key '{key}' already exists",
                    details={"key": key, "tenant_id": effective_tenant_id},
                )

            # Check plan limit (Phase 25.1.2)
            from hub.apps.tenants.services import PlanLimitService

            current_asset_count = Asset.objects.filter(tenant_id=effective_tenant_id).count()
            plan_limit_service = PlanLimitService(
                tenant_id=effective_tenant_id, user_id=effective_user_id
            )
            plan_limit_service.check_limit(
                tenant_id=effective_tenant_id,
                limit_key="max_assets",
                current_usage=current_asset_count,
                delta=1,
            )

            asset = Asset.objects.create(
                tenant_id=effective_tenant_id,
                key=key,
                name=name,
                description=description,
                domain=domain,
                status=AssetStatus.DRAFT,
                **kwargs,
            )

            return asset

        return self.execute_with_metrics(
            operation="create_asset", tenant_id=effective_tenant_id, func=_create
        )

    @transaction.atomic
    def update_asset(
        self,
        asset_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        version: Optional[int] = None,
        status: Optional[str] = None,
        **kwargs,
    ) -> Asset:
        """
        Update an asset.

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID
            user_id: User ID
            version: Expected version (for optimistic locking)
            status: Updated status (optional)
            **kwargs: Additional fields to update

        Returns:
            Updated asset instance

        Raises:
            NotFoundError: If asset not found
            ConflictError: If version mismatch
            ValidationError: If validation fails (e.g., activation blocked)
        """
        effective_tenant_id = tenant_id or self.tenant_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _update():
            asset = self.get_resource_or_raise(Asset, asset_id, tenant_id=effective_tenant_id)

            # Check version if provided (optimistic locking)
            if version is not None and asset.version != version:
                raise ConflictError(
                    f"Asset version mismatch: expected {version}, got {asset.version}",
                    code="ASSET_CONCURRENT_MODIFICATION",
                    details={"expected_version": version, "current_version": asset.version},
                )

            # Run business rules for status/lifecycle when status is being updated
            if status is not None:
                valid_statuses = [s[0] for s in AssetStatus.choices]
                if status not in valid_statuses:
                    raise ValidationError(
                        f"Invalid status: {status}", details={"valid_statuses": valid_statuses}
                    )
                rules = AssetsBusinessRules(
                    tenant_id=effective_tenant_id,
                    user_id=user_id or self.user_id,
                )
                result = rules.validate(
                    asset=asset,
                    validation_type="lifecycle",
                    old_status=asset.status,
                    new_status=status,
                )
                if not result.is_valid:
                    raise ValidationError(
                        "; ".join(result.errors),
                        code="BUSINESS_RULES_VALIDATION",
                        details=result.details,
                    )
                asset.status = status

            # Update other fields
            for field, value in kwargs.items():
                if hasattr(asset, field):
                    setattr(asset, field, value)

            # Increment version
            asset.version += 1
            asset.save()

            return asset

        return self.execute_with_metrics(
            operation="update_asset", tenant_id=effective_tenant_id, func=_update
        )

    @transaction.atomic
    def delete_asset(
        self, asset_id: str, tenant_id: Optional[str] = None, user_id: Optional[str] = None
    ) -> None:
        """
        Delete an asset (soft delete: set status to RETIRED).

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID
            user_id: User ID

        Raises:
            NotFoundError: If asset not found
        """
        effective_tenant_id = tenant_id or self.tenant_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _delete():
            asset = self.get_resource_or_raise(Asset, asset_id, tenant_id=effective_tenant_id)

            # Unpublish any marketplace listings BEFORE retirement validation.
            # Retirement validation blocks if there are active listings; unpublishing first
            # allows retirement to proceed and matches expected behavior (retire unpublishes).
            from hub.apps.marketplace.models import Listing, ListingStatus

            Listing.objects.filter(asset=asset, status=ListingStatus.PUBLISHED).update(
                status=ListingStatus.UNLISTED
            )

            # Run business rules for deletion (retirement requirements)
            rules = AssetsBusinessRules(
                tenant_id=effective_tenant_id,
                user_id=user_id or self.user_id,
            )
            result = rules.validate(
                asset=asset,
                validation_type="lifecycle",
                old_status=asset.status,
                new_status=AssetStatus.RETIRED,
            )
            if not result.is_valid:
                raise ValidationError(
                    "; ".join(result.errors),
                    code="BUSINESS_RULES_VALIDATION",
                    details=result.details,
                )

            asset.status = AssetStatus.RETIRED
            asset.save()

        return self.execute_with_metrics(
            operation="delete_asset", tenant_id=effective_tenant_id, func=_delete
        )

    @transaction.atomic
    def link_odps_contract_to_asset(
        self,
        asset_id: str,
        odps_contract_id: Optional[str] = None,
        odps_raw: Optional[str] = None,
        odps_format: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> "Contract":
        """
        Link ODPS contract to asset (Task 8.1.2).

        Uses ODPSService to create or link an ODPS contract to the asset.
        This method coordinates asset-ODPS contract relationships.

        Args:
            asset_id: Asset ID to link ODPS contract to
            odps_contract_id: Optional existing ODPS contract ID to link
            odps_raw: Optional ODPS document content (if creating new ODPS contract)
            odps_format: Optional ODPS document format (required if odps_raw provided)
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            user_id: User ID (uses service user_id if not provided)

        Returns:
            Linked ODPS Contract instance

        Raises:
            NotFoundError: If asset or contract not found
            ValidationError: If validation fails
        """
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _link():
            from hub.apps.contracts.models import Contract, OriginalSpecType
            from hub.apps.contracts.services import ODPSService

            # Get asset
            asset = self.get_resource_or_raise(Asset, asset_id, tenant_id=effective_tenant_id)

            # Use ODPSService to create or link ODPS contract
            odps_service = ODPSService(tenant_id=effective_tenant_id, user_id=effective_user_id)

            if odps_contract_id:
                # Link existing ODPS contract
                contract_service = odps_service  # ODPSService can get contract
                from hub.apps.contracts.services import ContractService

                contract_service = ContractService(
                    tenant_id=effective_tenant_id, user_id=effective_user_id
                )
                odps_contract = contract_service.get_contract(
                    contract_id=odps_contract_id, tenant_id=effective_tenant_id
                )

                # Verify it's an ODPS contract
                if odps_contract.original_spec_type != OriginalSpecType.ODPS:
                    raise ValidationError(
                        f"Contract {odps_contract_id} is not an ODPS contract",
                        code="INVALID_CONTRACT_TYPE",
                    )

                # Link to asset
                odps_contract.asset = asset

                # Calculate version
                latest_contract = (
                    Contract.objects.filter(tenant_id=effective_tenant_id, asset=asset)
                    .order_by("-version")
                    .first()
                )
                odps_contract.version = (latest_contract.version + 1) if latest_contract else 1
                odps_contract.save(update_fields=["asset", "version"])

                return odps_contract
            elif odps_raw:
                # Create new ODPS contract and link to asset
                odps_contract = odps_service.create_odps(
                    odps_raw=odps_raw,
                    odps_format=odps_format or "json",
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                    asset_id=asset_id,
                )
                return odps_contract
            else:
                raise ValidationError(
                    "Either odps_contract_id or odps_raw must be provided",
                    code="ODPS_SOURCE_REQUIRED",
                )

        return self.execute_with_metrics(
            operation="link_odps_contract_to_asset", tenant_id=effective_tenant_id, func=_link
        )

    def get_odps_contracts_for_asset(
        self, asset_id: str, tenant_id: Optional[str] = None
    ) -> List["Contract"]:
        """
        Get all ODPS contracts linked to an asset (Task 8.1.2).

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            List of ODPS Contract instances linked to the asset

        Raises:
            NotFoundError: If asset not found
        """
        effective_tenant_id = tenant_id or self.tenant_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _get_contracts():
            from hub.apps.contracts.models import Contract, OriginalSpecType

            # Get asset
            asset = self.get_resource_or_raise(Asset, asset_id, tenant_id=effective_tenant_id)

            # Get all ODPS contracts linked to asset
            odps_contracts = Contract.objects.filter(
                tenant_id=effective_tenant_id, asset=asset, original_spec_type=OriginalSpecType.ODPS
            ).order_by("-version")

            return list(odps_contracts)

        return self.execute_with_metrics(
            operation="get_odps_contracts_for_asset",
            tenant_id=effective_tenant_id,
            func=_get_contracts,
        )
