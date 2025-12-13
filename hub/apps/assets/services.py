"""
Asset Service

Business logic for asset operations.
"""
from typing import Dict, Any, Optional, List
from django.db import transaction

from hub.apps.core.services.base import BaseService, ValidationError, NotFoundError, ConflictError
from hub.apps.core.events.service_publishers import AssetEventPublisher
from hub.apps.assets.models import Asset, AssetStatus, DQStatus, ComplianceStatus


class AssetService(BaseService, AssetEventPublisher):
    """
    Service for asset operations.
    
    Provides business logic for creating, retrieving, updating, and managing assets.
    """
    service_name = "asset_service"
    
    def get_asset(
        self,
        asset_id: str,
        tenant_id: Optional[str] = None
    ) -> Asset:
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
        
        return self.execute_with_metrics(
            operation="get_asset",
            tenant_id=effective_tenant_id,
            func=lambda: self.get_resource_or_raise(
                Asset,
                asset_id,
                tenant_id=effective_tenant_id
            )
        )
    
    def get_assets_by_status(
        self,
        status: AssetStatus,
        tenant_id: Optional[str] = None,
        limit: Optional[int] = None
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
            queryset = Asset.objects.filter(
                tenant_id=effective_tenant_id,
                status=status
            )
            if limit:
                queryset = queryset[:limit]
            return list(queryset)
        
        return self.execute_with_metrics(
            operation="get_assets_by_status",
            tenant_id=effective_tenant_id,
            func=_get_assets
        )
    
    def is_asset_active(
        self,
        asset_id: str,
        tenant_id: Optional[str] = None
    ) -> bool:
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
            asset = self.get_resource_or_raise(
                Asset,
                asset_id,
                tenant_id=effective_tenant_id
            )
            return asset.status == AssetStatus.ACTIVE
        
        return self.execute_with_metrics(
            operation="is_asset_active",
            tenant_id=effective_tenant_id,
            func=_check
        )
    
    def validate_asset_eligibility(
        self,
        asset_id: str,
        tenant_id: Optional[str] = None
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
            asset = self.get_resource_or_raise(
                Asset,
                asset_id,
                tenant_id=effective_tenant_id
            )
            
            validation_results = {
                "asset_id": str(asset.id),
                "eligible": True,
                "blockers": []
            }
            
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
                    f"Asset {asset_id} is not eligible",
                    details=validation_results
                )
            
            return validation_results
        
        return self.execute_with_metrics(
            operation="validate_asset_eligibility",
            tenant_id=effective_tenant_id,
            func=_validate
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
        **kwargs
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
        
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")
        if not key:
            raise ValidationError("key is required")
        if not name:
            raise ValidationError("name is required")
        
        def _create():
            # Check for duplicate key
            if Asset.objects.filter(tenant_id=effective_tenant_id, key=key).exists():
                raise ConflictError(
                    f"Asset with key '{key}' already exists",
                    details={"key": key, "tenant_id": effective_tenant_id}
                )
            
            asset = Asset.objects.create(
                tenant_id=effective_tenant_id,
                key=key,
                name=name,
                description=description,
                domain=domain,
                status=AssetStatus.DRAFT,
                **kwargs
            )
            
            return asset
        
        return self.execute_with_metrics(
            operation="create_asset",
            tenant_id=effective_tenant_id,
            func=_create
        )
    
    @transaction.atomic
    def update_asset(
        self,
        asset_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        version: Optional[int] = None,
        status: Optional[str] = None,
        **kwargs
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
            asset = self.get_resource_or_raise(
                Asset,
                asset_id,
                tenant_id=effective_tenant_id
            )
            
            # Check version if provided
            if version is not None and asset.version != version:
                raise ConflictError(
                    f"Asset version mismatch: expected {version}, got {asset.version}",
                    details={"expected_version": version, "current_version": asset.version}
                )
            
            # Update fields
            for field, value in kwargs.items():
                if hasattr(asset, field):
                    setattr(asset, field, value)
            
            # Handle status update
            if status is not None:
                # Validate status
                valid_statuses = [s[0] for s in AssetStatus.choices]
                if status not in valid_statuses:
                    raise ValidationError(
                        f"Invalid status: {status}",
                        details={"valid_statuses": valid_statuses}
                    )
                
                # Check activation requirements
                if status == AssetStatus.ACTIVE:
                    can_activate, blockers = asset.can_activate()
                    if not can_activate:
                        raise ValidationError(
                            "Asset activation blocked",
                            details={
                                "code": "ASSET_ACTIVATION_BLOCKED",
                                "blockers": blockers
                            }
                        )
                
                asset.status = status
            
            # Increment version
            asset.version += 1
            asset.save()
            
            return asset
        
        return self.execute_with_metrics(
            operation="update_asset",
            tenant_id=effective_tenant_id,
            func=_update
        )
    
    @transaction.atomic
    def delete_asset(
        self,
        asset_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
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
            asset = self.get_resource_or_raise(
                Asset,
                asset_id,
                tenant_id=effective_tenant_id
            )
            
            asset.status = AssetStatus.RETIRED
            
            # Unpublish any marketplace listings for this asset
            from hub.apps.marketplace.models import Listing, ListingStatus
            Listing.objects.filter(
                asset=asset,
                status=ListingStatus.PUBLISHED
            ).update(status=ListingStatus.UNLISTED)
            asset.save()
        
        return self.execute_with_metrics(
            operation="delete_asset",
            tenant_id=effective_tenant_id,
            func=_delete
        )