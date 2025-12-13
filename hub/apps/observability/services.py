"""
Observability Service

Service layer for observability operations.
Extracts observability logic from views.py and monitoring modules.
"""
from typing import Dict, Any, Optional

from hub.apps.core.services.base import BaseService
from hub.apps.observability.freshness import FreshnessMonitor
from hub.apps.observability.volume import VolumeMonitor
from hub.apps.observability.schema_drift import SchemaDriftDetector


class ObservabilityService(BaseService):
    """
    Service for observability operations.
    
    Provides business logic for:
    - Data freshness monitoring
    - Volume monitoring
    - Schema drift detection
    """
    
    service_name = "observability_service"
    
    def get_freshness_dashboard(
        self,
        tenant_id: str,
        dataset_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get data freshness dashboard.
        
        Args:
            tenant_id: Tenant ID
            dataset_id: Optional dataset ID filter
            asset_id: Optional asset ID filter
            limit: Maximum number of records
            
        Returns:
            Freshness dashboard data dictionary
        """
        return self.execute_with_metrics(
            operation="get_freshness_dashboard",
            func=lambda: FreshnessMonitor.get_freshness_dashboard(
                tenant_id=tenant_id,
                dataset_id=dataset_id,
                asset_id=asset_id,
                limit=limit
            ),
            tenant_id=tenant_id
        )
    
    def get_volume_dashboard(
        self,
        tenant_id: str,
        dataset_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        limit: int = 100,
        period_type: str = "DAILY"
    ) -> Dict[str, Any]:
        """
        Get volume monitoring dashboard.
        
        Args:
            tenant_id: Tenant ID
            dataset_id: Optional dataset ID filter
            asset_id: Optional asset ID filter
            limit: Maximum number of records
            period_type: Period type (HOURLY or DAILY, default: DAILY)
            
        Returns:
            Volume dashboard data dictionary
        """
        return self.execute_with_metrics(
            operation="get_volume_dashboard",
            func=lambda: VolumeMonitor.get_volume_dashboard(
                tenant_id=tenant_id,
                dataset_id=dataset_id,
                asset_id=asset_id,
                period_type=period_type,
                limit=limit
            ),
            tenant_id=tenant_id
        )
    
    def get_schema_drift_dashboard(
        self,
        tenant_id: str,
        dataset_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get schema drift detection dashboard.
        
        Args:
            tenant_id: Tenant ID
            dataset_id: Optional dataset ID filter
            asset_id: Optional asset ID filter
            limit: Maximum number of records
            
        Returns:
            Schema drift dashboard data dictionary
        """
        return self.execute_with_metrics(
            operation="get_schema_drift_dashboard",
            func=lambda: SchemaDriftDetector.get_drift_dashboard(
                tenant_id=tenant_id,
                dataset_id=dataset_id,
                asset_id=asset_id,
                limit=limit
            ),
            tenant_id=tenant_id
        )

