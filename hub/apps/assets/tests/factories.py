"""
Test Factories for Assets

Real factories (not mocks) for creating test data for Asset models.
"""
import uuid
from typing import Optional
from django.contrib.auth import get_user_model

from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility, DQStatus, ComplianceStatus
from hub.apps.tenants.models import Tenant

User = get_user_model()


class AssetFactory:
    """Factory for creating Asset instances"""
    
    @staticmethod
    def create_asset(
        tenant: Tenant,
        key: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        domain: Optional[str] = None,
        status: AssetStatus = AssetStatus.DRAFT,
        visibility: AssetVisibility = AssetVisibility.INTERNAL,
        dq_status: DQStatus = DQStatus.UNKNOWN,
        compliance_status: ComplianceStatus = ComplianceStatus.UNKNOWN,
        created_by: Optional[User] = None,
        **kwargs
    ) -> Asset:
        """
        Create an Asset instance.
        
        Args:
            tenant: Tenant instance (required)
            key: Asset key (default: auto-generated)
            name: Asset name (default: auto-generated)
            description: Asset description
            domain: Domain (e.g., marketing, finance)
            status: Asset status (default: DRAFT)
            visibility: Asset visibility (default: INTERNAL)
            dq_status: Data Quality status (default: UNKNOWN)
            compliance_status: Compliance status (default: UNKNOWN)
            created_by: User who created the asset
            **kwargs: Additional fields
            
        Returns:
            Asset instance
        """
        if key is None:
            key = f"test-asset-{uuid.uuid4().hex[:8]}"
        
        if name is None:
            name = f"Test Asset {uuid.uuid4().hex[:8]}"
        
        return Asset.objects.create(
            tenant=tenant,
            key=key,
            name=name,
            description=description,
            domain=domain,
            status=status,
            visibility=visibility,
            dq_status=dq_status,
            compliance_status=compliance_status,
            created_by=created_by,
            **kwargs
        )
    
    @staticmethod
    def create_active_asset(
        tenant: Tenant,
        created_by: Optional[User] = None,
        **kwargs
    ) -> Asset:
        """
        Create an ACTIVE asset with PASS statuses.
        
        This factory creates an asset that can be activated (meets all requirements).
        
        Args:
            tenant: Tenant instance
            created_by: User who created the asset
            **kwargs: Additional fields
            
        Returns:
            Asset instance with ACTIVE status
        """
        return AssetFactory.create_asset(
            tenant=tenant,
            status=AssetStatus.ACTIVE,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=created_by,
            **kwargs
        )
    
    @staticmethod
    def create_asset_with_all_statuses(tenant: Tenant, created_by: Optional[User] = None) -> list[Asset]:
        """
        Create Asset instances with all possible statuses.
        
        Args:
            tenant: Tenant instance
            created_by: User who created the assets
            
        Returns:
            List of Asset instances
        """
        assets = []
        for status in AssetStatus:
            assets.append(
                AssetFactory.create_asset(
                    tenant=tenant,
                    status=status,
                    created_by=created_by
                )
            )
        return assets

    def __call__(self, **kwargs) -> Asset:
        """Allow factory to be called directly: AssetFactory(**kwargs)"""
        return self.create_asset(**kwargs)


# Make AssetFactory callable
AssetFactory = AssetFactory()

