"""
Versioning Service

Service layer for dataset versioning operations.
Extracts versioning logic from versioning.py module.
"""
from typing import Dict, Any, Optional, List

from hub.apps.core.services.base import BaseService, NotFoundError
from hub.apps.core.events.service_publishers import VersioningEventPublisher
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.versioning import VersionHistoryManager


class VersioningService(BaseService, VersioningEventPublisher):
    """
    Service for dataset versioning operations.

    Provides business logic for:
    - Version creation
    - Version comparison
    - Version history traversal
    - Semantic versioning
    """

    service_name = "versioning_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize VersioningService.

        Args:
            tenant_id: Tenant ID
            user_id: User ID
        """
        # Set attributes before calling parent __init__
        self.tenant_id = tenant_id
        self.user_id = user_id
        # Call VersioningEventPublisher.__init__ to initialize event publisher
        VersioningEventPublisher.__init__(self, tenant_id=tenant_id, user_id=user_id)

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

        # Create version using VersionHistoryManager
        updated_dataset = VersionHistoryManager.create_version(
            dataset=dataset,
            parent_version=parent_version,
            semantic_version=semantic_version,
            version_tags=version_tags,
            snapshot_metadata=snapshot_metadata,
            is_current=is_current
        )

        # Publish version.created event
        try:
            self.publish_version_created(
                version_id=str(updated_dataset.id),
                resource_type="DATASET",
                resource_id=str(updated_dataset.id),
                version_number=str(updated_dataset.version) if updated_dataset.version else None,
                version_type="semantic" if semantic_version else "incremental",
                semantic_version=updated_dataset.semantic_version,
                parent_version_id=str(parent_version.id) if parent_version else None,
                tenant_id=tenant_id,
                user_id=self.user_id
            )
        except Exception:
            # Don't fail version creation if event publishing fails
            # Event publishing errors are logged by the publisher
            pass

        return updated_dataset

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
        from hub.apps.datasets.version_comparison import VersionComparisonService

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

        comparison = VersionComparisonService.compare_versions(
            old_version=dataset1,
            new_version=dataset2,
            include_data_diff=True
        )
        
        # Convert VersionComparison dataclass to dict for API compatibility
        return VersionComparisonService.visualize_version_diff(
            comparison,
            format="json"
        )

    def update_version(
        self,
        version_id: str,
        tenant_id: str,
        changes: Dict[str, Any],
        **kwargs
    ) -> Dataset:
        """
        Update a dataset version.

        Args:
            version_id: Version (dataset) ID to update
            tenant_id: Tenant ID
            changes: Dictionary of changes to apply
            **kwargs: Additional update parameters

        Returns:
            Updated Dataset instance

        Raises:
            NotFoundError: If version not found
        """
        dataset = self.get_resource_or_raise(
            Dataset,
            version_id,
            tenant_id=tenant_id
        )

        # Store previous state for event
        previous_semantic_version = dataset.semantic_version
        previous_is_current = dataset.is_current

        # Apply changes
        for key, value in changes.items():
            if hasattr(dataset, key):
                setattr(dataset, key, value)

        dataset.save()

        # Determine new version values
        new_semantic_version = dataset.semantic_version
        new_is_current = dataset.is_current

        # Publish version.updated event
        try:
            self.publish_version_updated(
                version_id=str(dataset.id),
                changes=changes,
                resource_type="DATASET",
                resource_id=str(dataset.id),
                previous_version=previous_semantic_version,
                new_version=new_semantic_version,
                tenant_id=tenant_id,
                user_id=self.user_id,
                **kwargs
            )
        except Exception:
            # Don't fail version update if event publishing fails
            pass

        return dataset

    def delete_version(
        self,
        version_id: str,
        tenant_id: str,
        reason: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Delete a dataset version.

        Args:
            version_id: Version (dataset) ID to delete
            tenant_id: Tenant ID
            reason: Optional reason for deletion
            **kwargs: Additional parameters

        Raises:
            NotFoundError: If version not found
        """
        dataset = self.get_resource_or_raise(
            Dataset,
            version_id,
            tenant_id=tenant_id
        )

        # Store dataset info before deletion
        resource_id = str(dataset.id)

        # Publish version.deleted event before deletion
        try:
            self.publish_version_deleted(
                version_id=str(dataset.id),
                resource_type="DATASET",
                resource_id=resource_id,
                reason=reason,
                tenant_id=tenant_id,
                user_id=self.user_id,
                **kwargs
            )
        except Exception:
            # Don't fail deletion if event publishing fails
            pass

        # Delete the dataset version
        dataset.delete()

    def promote_version(
        self,
        version_id: str,
        tenant_id: str,
        promoted_from: str,
        promoted_to: str,
        promotion_reason: Optional[str] = None,
        **kwargs
    ) -> Dataset:
        """
        Promote a dataset version (e.g., from staging to production).

        Args:
            version_id: Version (dataset) ID to promote
            tenant_id: Tenant ID
            promoted_from: Source environment/tag (e.g., "staging")
            promoted_to: Target environment/tag (e.g., "production")
            promotion_reason: Optional reason for promotion
            **kwargs: Additional parameters

        Returns:
            Updated Dataset instance

        Raises:
            NotFoundError: If version not found
        """
        dataset = self.get_resource_or_raise(
            Dataset,
            version_id,
            tenant_id=tenant_id
        )

        # Update version tags if promotion involves tag changes
        if promoted_to not in (dataset.version_tags or []):
            current_tags = dataset.version_tags or []
            # Remove old tag if it exists
            if promoted_from in current_tags:
                current_tags.remove(promoted_from)
            # Add new tag
            current_tags.append(promoted_to)
            dataset.version_tags = current_tags
            dataset.save()

        # Publish version.promoted event
        try:
            self.publish_version_promoted(
                version_id=str(dataset.id),
                resource_type="DATASET",
                resource_id=str(dataset.id),
                promoted_from=promoted_from,
                promoted_to=promoted_to,
                promotion_reason=promotion_reason,
                tenant_id=tenant_id,
                user_id=self.user_id,
                **kwargs
            )
        except Exception:
            # Don't fail promotion if event publishing fails
            pass

        return dataset

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

        # Get version tree (all versions in the history)
        versions = VersionHistoryManager.get_version_tree(dataset)
        
        # Convert to list of dictionaries if snapshots are requested, otherwise return Dataset objects
        if include_snapshots:
            return [
                {
                    "id": str(v.id),
                    "version": v.version,
                    "semantic_version": v.semantic_version,
                    "is_current": v.is_current,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                    "snapshot_metadata": v.snapshot_metadata,
                }
                for v in versions
            ]
        else:
            # Return list of Dataset objects (which can be serialized as needed)
            return list(versions)

