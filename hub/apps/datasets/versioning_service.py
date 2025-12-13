"""
Versioning Service

Service layer for dataset versioning operations.
Extracts versioning logic from versioning.py module.
"""
from typing import Dict, Any, Optional, List

from hub.apps.core.services.base import BaseService, NotFoundError
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.versioning import VersionHistoryManager


class VersioningService(BaseService):
    """
    Service for dataset versioning operations.
    
    Provides business logic for:
    - Version creation
    - Version comparison
    - Version history traversal
    - Semantic versioning
    """
    
    service_name = "versioning_service"
    
    def create_version(
        self,
        dataset_id: str,
        tenant_id: str,
        parent_version_id: Optional[str] = None,
        semantic_version: Optional[str] = None,
        version_tags: Optional[List[str]] = None,
        snapshot_metadata: Optional[Dict[str, Any]] = None,
        is_current: bool = True
    ) -> Dataset:
        """
        Create a new dataset version.
        
        Args:
            dataset_id: Dataset ID
            tenant_id: Tenant ID
            parent_version_id: Optional parent version ID
            semantic_version: Optional semantic version string
            version_tags: Optional version tags
            snapshot_metadata: Optional snapshot metadata
            is_current: Whether this is the current version
            
        Returns:
            Updated Dataset instance
            
        Raises:
            NotFoundError: If dataset or parent version not found
        """
        dataset = self.get_resource_or_raise(
            Dataset,
            dataset_id,
            tenant_id=tenant_id
        )
        
        parent_version = None
        if parent_version_id:
            parent_version = self.get_resource_or_raise(
                Dataset,
                parent_version_id,
                tenant_id=tenant_id
            )
        
        return VersionHistoryManager.create_version(
            dataset=dataset,
            parent_version=parent_version,
            semantic_version=semantic_version,
            version_tags=version_tags,
            snapshot_metadata=snapshot_metadata,
            is_current=is_current
        )
    
    def compare_versions(
        self,
        dataset_id_1: str,
        dataset_id_2: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        Compare two dataset versions.
        
        Args:
            dataset_id_1: First dataset ID
            dataset_id_2: Second dataset ID
            tenant_id: Tenant ID
            
        Returns:
            Comparison results dictionary
            
        Raises:
            NotFoundError: If either dataset not found
        """
        from hub.apps.datasets.version_comparison import VersionComparator
        
        dataset1 = self.get_resource_or_raise(
            Dataset,
            dataset_id_1,
            tenant_id=tenant_id
        )
        
        dataset2 = self.get_resource_or_raise(
            Dataset,
            dataset_id_2,
            tenant_id=tenant_id
        )
        
        comparator = VersionComparator()
        return comparator.compare(dataset1, dataset2)
    
    def get_version_history(
        self,
        dataset_id: str,
        tenant_id: str,
        include_snapshots: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get version history for a dataset.
        
        Args:
            dataset_id: Dataset ID
            tenant_id: Tenant ID
            include_snapshots: Whether to include snapshot data
            
        Returns:
            List of version history entries
            
        Raises:
            NotFoundError: If dataset not found
        """
        dataset = self.get_resource_or_raise(
            Dataset,
            dataset_id,
            tenant_id=tenant_id
        )
        
        return VersionHistoryManager.get_version_history(
            dataset=dataset,
            include_snapshots=include_snapshots
        )

