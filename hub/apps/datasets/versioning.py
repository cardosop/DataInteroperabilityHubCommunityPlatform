"""
Dataset Version History Management

Provides version creation, tree traversal, and querying for dataset version history.
"""

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from django.utils import timezone

from hub.apps.core.services.base import ValidationError
from hub.apps.tenants.services import get_tenant_config_value

from .models import Dataset


class VersionHistoryManager:
    """
    Manager for dataset version history operations.
    """

    @staticmethod
    def calculate_version_hash(dataset: Dataset) -> str:
        """
        Calculate version hash from schema and file content hash.

        Args:
            dataset: Dataset instance

        Returns:
            SHA-256 hash string
        """
        # Combine schema and file content hash for version identification
        schema_str = json.dumps(dataset.schema_json or {}, sort_keys=True)
        file_hash = (dataset.file.content_sha256 if dataset.file else None) or ""

        combined = f"{schema_str}:{file_hash}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    @staticmethod
    def create_version(
        dataset: Dataset,
        parent_version: Dataset | None = None,
        semantic_version: str | None = None,
        version_tags: list[str] | None = None,
        snapshot_metadata: dict[str, Any] | None = None,
        is_current: bool = True,
    ) -> Dataset:
        """
        Create a new dataset version with version history tracking.

        Args:
            dataset: Dataset instance to create version for
            parent_version: Parent version (for version tree)
            semantic_version: Semantic version string (e.g., "1.0.0")
            version_tags: List of version tags (e.g., ["production", "staging"])
            snapshot_metadata: Additional metadata for snapshot
            is_current: Whether this is the current version

        Returns:
            Updated Dataset instance with version history fields

        Raises:
            ValidationError: If versioning is disabled for the tenant (when creating
                a subsequent version, i.e. parent_version is not None).
        """
        # Enforce versioning_enabled when creating a subsequent version (parent_version set).
        # First version (parent_version=None) is always allowed for dataset creation.
        if parent_version is not None:
            versioning_enabled = get_tenant_config_value(
                dataset.tenant, "versioning_enabled", default=True
            )
            if not versioning_enabled:
                raise ValidationError(
                    "Versioning is disabled for this tenant.",
                    code="VERSIONING_DISABLED",
                    http_status=403,
                )

        # Calculate version hash
        version_hash = VersionHistoryManager.calculate_version_hash(dataset)

        # If is_current is True, mark all other versions of same asset as not current
        if is_current and dataset.asset:
            Dataset.objects.filter(
                tenant=dataset.tenant, asset=dataset.asset, is_current=True
            ).exclude(id=dataset.id).update(
                is_current=False,
                archived_at=timezone.now(),
            )

        # Set version history fields
        dataset.parent_version = parent_version
        dataset.version_hash = version_hash
        dataset.snapshot_metadata = snapshot_metadata or {}
        dataset.is_current = is_current
        dataset.semantic_version = (
            semantic_version
            or VersionHistoryManager._infer_semantic_version(dataset, parent_version)
        )
        dataset.version_tags = version_tags or []

        dataset.save()

        # Track schema evolution
        try:
            from .schema_evolution import SchemaEvolutionTracker

            SchemaEvolutionTracker.track_schema_version(
                dataset=dataset, parent_dataset=parent_version
            )
        except Exception:
            # Schema tracking is optional, don't fail version creation
            pass

        return dataset

    @staticmethod
    def _infer_semantic_version(dataset: Dataset, parent_version: Dataset | None = None) -> str:
        """
        Infer semantic version from parent version and changes.

        Version increment rules:
        - Breaking schema change (field removed, type changed, nullable -> non-nullable) → increment major
        - New fields added (non-breaking) → increment minor
        - Bug fix, metadata change, or no schema/data change → increment patch

        Args:
            dataset: New dataset version
            parent_version: Parent version

        Returns:
            Semantic version string (e.g., "1.0.0")
        """
        if not parent_version:
            return "1.0.0"

        # Parse parent semantic version
        parent_semver = VersionHistoryManager._parse_semantic_version(
            parent_version.semantic_version or "1.0.0"
        )

        if not parent_semver:
            return "1.0.0"

        major, minor, patch = parent_semver

        # Always check for breaking changes first (even if field names haven't changed,
        # properties like nullable or type might have changed)
        if VersionHistoryManager._is_breaking_change(
            parent_version.schema_json or {}, dataset.schema_json or {}
        ):
            # Breaking change → increment major
            major += 1
            minor = 0
            patch = 0
        else:
            # Compare schemas to determine version increment
            schema_changed = VersionHistoryManager._schema_changed(
                parent_version.schema_json or {}, dataset.schema_json or {}
            )

            if schema_changed:
                # Non-breaking change (new fields added) → increment minor
                minor += 1
                patch = 0
            # No schema change
            # Check if metadata-only change
            elif VersionHistoryManager._has_metadata_only_changes(parent_version, dataset):
                # Metadata-only change → increment patch
                patch += 1
            else:
                # Data change but no schema change (bug fix, data correction) → increment patch
                patch += 1

        return f"{major}.{minor}.{patch}"

    @staticmethod
    def _parse_semantic_version(version_str: str) -> tuple[int, int, int] | None:
        """Parse semantic version string to tuple."""
        try:
            parts = version_str.split(".")
            if len(parts) != 3:
                return None
            return (int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _schema_changed(old_schema: dict[str, Any], new_schema: dict[str, Any]) -> bool:
        """Check if schema has changed."""
        # Compare field lists
        old_fields = {f.get("name") for f in old_schema.get("fields", [])}
        new_fields = {f.get("name") for f in new_schema.get("fields", [])}

        return old_fields != new_fields

    @staticmethod
    def _is_breaking_change(old_schema: dict[str, Any], new_schema: dict[str, Any]) -> bool:
        """
        Check if schema change is breaking (field removed or type changed).

        Breaking changes:
        - Field removed
        - Field data type changed
        - Field changed from nullable to non-nullable
        - Primary key changed
        """
        old_fields = {f.get("name"): f for f in old_schema.get("fields", [])}
        new_fields = {f.get("name"): f for f in new_schema.get("fields", [])}

        # Check for removed fields
        removed_fields = set(old_fields.keys()) - set(new_fields.keys())
        if removed_fields:
            return True

        # Check for type changes (check both 'type' and 'data_type' for compatibility)
        for field_name, old_field in old_fields.items():
            if field_name in new_fields:
                new_field = new_fields[field_name]
                old_type = old_field.get("data_type") or old_field.get("type")
                new_type = new_field.get("data_type") or new_field.get("type")
                if old_type != new_type:
                    return True

                # Check nullable changes: nullable -> non-nullable is breaking
                old_nullable = old_field.get("nullable", True)
                new_nullable = new_field.get("nullable", True)
                if old_nullable and not new_nullable:
                    return True

        # Check for primary key changes
        old_pk = old_schema.get("primary_key_candidates", [])
        new_pk = new_schema.get("primary_key_candidates", [])
        if old_pk != new_pk:
            return True

        return False

    @staticmethod
    def _has_metadata_only_changes(old_dataset: Dataset, new_dataset: Dataset) -> bool:
        """
        Check if changes are metadata-only (no schema or data changes).

        Metadata changes include:
        - Description changes
        - Tag changes
        - Metadata field changes
        - File metadata changes (but not content hash)
        """
        # Schema unchanged
        schema_changed = VersionHistoryManager._schema_changed(
            old_dataset.schema_json or {}, new_dataset.schema_json or {}
        )
        if schema_changed:
            return False

        # File content unchanged (same hash); if either has no file, not metadata-only
        if not old_dataset.file or not new_dataset.file:
            return False
        if old_dataset.file.content_sha256 != new_dataset.file.content_sha256:
            return False

        # Row count unchanged
        if old_dataset.row_count != new_dataset.row_count:
            return False

        # If all above are unchanged, it's metadata-only
        return True

    @staticmethod
    def get_version_tree(dataset: Dataset) -> list[Dataset]:
        """
        Get complete version tree (all ancestors and descendants).

        Args:
            dataset: Starting dataset version

        Returns:
            List of all versions in tree (ordered by creation time)
        """
        # Get root version (no parent)
        root = VersionHistoryManager.get_root_version(dataset)

        # Get all descendants from root
        all_versions = [root]
        current = root

        while True:
            children = Dataset.objects.filter(
                tenant=current.tenant, asset=current.asset, parent_version=current
            ).order_by("created_at")

            if not children.exists():
                break

            all_versions.extend(list(children))
            current = children.first()

        return all_versions

    @staticmethod
    def get_root_version(dataset: Dataset) -> Dataset:
        """
        Get root version (version with no parent).

        Args:
            dataset: Starting dataset version

        Returns:
            Root version
        """
        current = dataset
        while current.parent_version:
            try:
                current = current.parent_version
            except Dataset.DoesNotExist:
                break
        return current

    @staticmethod
    def get_ancestors(dataset: Dataset) -> list[Dataset]:
        """
        Get all ancestor versions (parent chain to root).

        Args:
            dataset: Starting dataset version

        Returns:
            List of ancestor versions (ordered from parent to root)
        """
        ancestors = []
        current = dataset

        while current.parent_version:
            try:
                parent = current.parent_version
                ancestors.append(parent)
                current = parent
            except Dataset.DoesNotExist:
                break

        return ancestors

    @staticmethod
    def get_descendants(dataset: Dataset) -> list[Dataset]:
        """
        Get all descendant versions (children and their children).

        Args:
            dataset: Starting dataset version

        Returns:
            List of descendant versions (ordered by creation time)
        """
        descendants = []
        to_process = [dataset]

        while to_process:
            current = to_process.pop(0)
            children = Dataset.objects.filter(
                tenant=current.tenant, asset=current.asset, parent_version=current
            ).order_by("created_at")

            for child in children:
                descendants.append(child)
                to_process.append(child)

        return descendants

    @staticmethod
    def get_current_version(asset_id: UUID, tenant_id: UUID) -> Dataset | None:
        """
        Get current version for an asset.

        Args:
            asset_id: Asset UUID
            tenant_id: Tenant UUID

        Returns:
            Current dataset version or None
        """
        return Dataset.objects.filter(
            tenant_id=tenant_id, asset_id=asset_id, is_current=True
        ).first()

    @staticmethod
    def get_version_by_semantic_version(
        asset_id: UUID, tenant_id: UUID, semantic_version: str
    ) -> Dataset | None:
        """
        Get dataset version by semantic version.

        Args:
            asset_id: Asset UUID
            tenant_id: Tenant UUID
            semantic_version: Semantic version string (e.g., "1.0.0")

        Returns:
            Dataset version or None
        """
        return Dataset.objects.filter(
            tenant_id=tenant_id, asset_id=asset_id, semantic_version=semantic_version
        ).first()

    @staticmethod
    def get_versions_by_tag(asset_id: UUID, tenant_id: UUID, tag: str) -> list[Dataset]:
        """
        Get dataset versions by tag.

        Args:
            asset_id: Asset UUID
            tenant_id: Tenant UUID
            tag: Version tag (e.g., "production")

        Returns:
            List of dataset versions with the tag
        """
        return list(
            Dataset.objects.filter(
                tenant_id=tenant_id, asset_id=asset_id, version_tags__contains=[tag]
            ).order_by("-created_at")
        )

    @staticmethod
    def get_versions_by_timestamp(
        asset_id: UUID, tenant_id: UUID, timestamp: datetime
    ) -> Dataset | None:
        """
        Get dataset version at a specific timestamp.

        Args:
            asset_id: Asset UUID
            tenant_id: Tenant UUID
            timestamp: Target timestamp

        Returns:
            Dataset version that was current at the timestamp, or None
        """
        return (
            Dataset.objects.filter(
                tenant_id=tenant_id, asset_id=asset_id, created_at__lte=timestamp
            )
            .order_by("-created_at")
            .first()
        )

    @staticmethod
    def archive_version(dataset: Dataset, archived_at: datetime | None = None) -> Dataset:
        """
        Archive a dataset version.

        Args:
            dataset: Dataset version to archive
            archived_at: Archive timestamp (default: now)

        Returns:
            Updated dataset instance
        """
        dataset.archived_at = archived_at or timezone.now()
        dataset.is_current = False
        dataset.save()
        return dataset

    @staticmethod
    def restore_version(dataset: Dataset) -> Dataset:
        """
        Restore an archived dataset version (make it current).

        Args:
            dataset: Archived dataset version

        Returns:
            Updated dataset instance
        """
        # Mark other versions as not current
        if dataset.asset:
            Dataset.objects.filter(
                tenant=dataset.tenant, asset=dataset.asset, is_current=True
            ).exclude(id=dataset.id).update(
                is_current=False,
                archived_at=timezone.now(),
            )

        dataset.archived_at = None
        dataset.is_current = True
        dataset.save()
        return dataset

    @staticmethod
    def add_version_tag(dataset: Dataset, tag: str) -> Dataset:
        """
        Add a tag to a dataset version.

        Args:
            dataset: Dataset version
            tag: Tag to add (e.g., "production", "staging")

        Returns:
            Updated dataset instance
        """
        if not tag:
            raise ValueError("Tag cannot be empty")

        tags = list(dataset.version_tags or [])
        if tag not in tags:
            tags.append(tag)
            dataset.version_tags = tags
            dataset.save(update_fields=["version_tags"])

        return dataset

    @staticmethod
    def remove_version_tag(dataset: Dataset, tag: str) -> Dataset:
        """
        Remove a tag from a dataset version.

        Args:
            dataset: Dataset version
            tag: Tag to remove

        Returns:
            Updated dataset instance
        """
        tags = list(dataset.version_tags or [])
        if tag in tags:
            tags.remove(tag)
            dataset.version_tags = tags
            dataset.save(update_fields=["version_tags"])

        return dataset

    @staticmethod
    def set_version_tags(dataset: Dataset, tags: list[str]) -> Dataset:
        """
        Set tags for a dataset version (replaces existing tags).

        Args:
            dataset: Dataset version
            tags: List of tags to set

        Returns:
            Updated dataset instance
        """
        # Validate tags
        for tag in tags:
            if not tag or not isinstance(tag, str):
                raise ValueError(f"Invalid tag: {tag}")

        dataset.version_tags = list(set(tags))  # Remove duplicates
        dataset.save(update_fields=["version_tags"])
        return dataset

    @staticmethod
    def get_versions_by_tags(
        asset_id: UUID, tenant_id: UUID, tags: list[str], match_all: bool = False
    ) -> list[Dataset]:
        """
        Get dataset versions by tags.

        Args:
            asset_id: Asset UUID
            tenant_id: Tenant UUID
            tags: List of tags to filter by
            match_all: If True, version must have all tags; if False, version must have any tag

        Returns:
            List of dataset versions matching the tag criteria
        """
        if not tags:
            return []

        queryset = Dataset.objects.filter(tenant_id=tenant_id, asset_id=asset_id)

        if match_all:
            # Version must contain all tags
            for tag in tags:
                queryset = queryset.filter(version_tags__contains=[tag])
        else:
            # Version must contain any tag
            from django.db.models import Q

            tag_filters = Q()
            for tag in tags:
                tag_filters |= Q(version_tags__contains=[tag])
            queryset = queryset.filter(tag_filters)

        return list(queryset.order_by("-created_at"))
