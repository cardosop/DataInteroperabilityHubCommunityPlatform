"""
Time-Travel Queries for Dataset Versions

Provides time-travel query interface for retrieving dataset versions at specific points in time.
"""

from datetime import datetime
from uuid import UUID

from django.utils import timezone

from .models import Dataset, DatasetSnapshot, SnapshotType


class TimeTravelQuery:
    """
    Time-travel query interface for dataset versions.
    """

    @staticmethod
    def get_version_at_timestamp(
        asset_id: UUID, tenant_id: UUID, timestamp: datetime
    ) -> Dataset | None:
        """
        Get dataset version that was current at a specific timestamp.

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
    def get_version_by_number(
        asset_id: UUID, tenant_id: UUID, version_number: int
    ) -> Dataset | None:
        """
        Get dataset version by version number.

        Args:
            asset_id: Asset UUID
            tenant_id: Tenant UUID
            version_number: Version number (integer)

        Returns:
            Dataset version or None
        """
        return Dataset.objects.filter(
            tenant_id=tenant_id, asset_id=asset_id, version=version_number
        ).first()

    @staticmethod
    def get_versions_in_range(
        asset_id: UUID,
        tenant_id: UUID,
        start_timestamp: datetime | None = None,
        end_timestamp: datetime | None = None,
    ) -> list[Dataset]:
        """
        Get all dataset versions within a time range.

        Args:
            asset_id: Asset UUID
            tenant_id: Tenant UUID
            start_timestamp: Start timestamp (inclusive)
            end_timestamp: End timestamp (inclusive)

        Returns:
            List of dataset versions in the range
        """
        queryset = Dataset.objects.filter(tenant_id=tenant_id, asset_id=asset_id)

        if start_timestamp:
            queryset = queryset.filter(created_at__gte=start_timestamp)

        if end_timestamp:
            queryset = queryset.filter(created_at__lte=end_timestamp)

        return list(queryset.order_by("created_at"))

    @staticmethod
    def create_snapshot(dataset: Dataset, snapshot_type="FULL") -> DatasetSnapshot:
        """
        Create a snapshot of a dataset version.

        Args:
            dataset: Dataset to snapshot
            snapshot_type: Snapshot type — accepts ``SnapshotType`` enum
                member or raw string (FULL, SCHEMA_ONLY, METADATA_ONLY).

        Returns:
            DatasetSnapshot instance

        Raises:
            NotImplementedError: when ``snapshot_type`` is INCREMENTAL
                (post-MVP placeholder per ``file-storage`` spec).
            ValueError: when ``snapshot_type`` is not a recognised member
                of ``SnapshotType``.
        """
        # Normalise: accept both bare enum members and raw strings.
        if isinstance(snapshot_type, SnapshotType):
            snapshot_type = snapshot_type.value

        valid = {m.value for m in SnapshotType}
        if snapshot_type not in valid:
            raise ValueError(
                f"Unknown snapshot_type {snapshot_type!r}. Valid types: {', '.join(sorted(valid))}"
            )

        if snapshot_type == SnapshotType.INCREMENTAL:
            raise NotImplementedError(
                "INCREMENTAL snapshots are a post-MVP placeholder "
                "(spec: file-storage). Not yet implemented."
            )

        snapshot_data = {}

        if snapshot_type == "FULL":
            snapshot_data = {
                "dataset_id": str(dataset.id),
                "schema_json": dataset.schema_json,
                "sample_data_json": dataset.sample_data_json,
                "row_count": dataset.row_count,
                "format": dataset.format,
                "version": dataset.version,
                "semantic_version": dataset.semantic_version,
                "version_tags": dataset.version_tags,
                "snapshot_metadata": dataset.snapshot_metadata,
                "created_at": dataset.created_at.isoformat(),
            }
        elif snapshot_type == "SCHEMA_ONLY":
            snapshot_data = {
                "dataset_id": str(dataset.id),
                "schema_json": dataset.schema_json,
                "format": dataset.format,
                "semantic_version": dataset.semantic_version,
            }
        elif snapshot_type == "METADATA_ONLY":
            snapshot_data = {
                "dataset_id": str(dataset.id),
                "version": dataset.version,
                "semantic_version": dataset.semantic_version,
                "version_tags": dataset.version_tags,
                "snapshot_metadata": dataset.snapshot_metadata,
                "created_at": dataset.created_at.isoformat(),
            }

        snapshot = DatasetSnapshot.objects.create(
            dataset=dataset, snapshot_data=snapshot_data, snapshot_type=snapshot_type
        )

        return snapshot

    @staticmethod
    def restore_from_snapshot(
        snapshot: DatasetSnapshot,
        new_asset_id: UUID | None = None,
        new_tenant_id: UUID | None = None,
    ) -> Dataset:
        """
        Restore a dataset from a snapshot.

        Only FULL snapshots can be restored — SCHEMA_ONLY and
        METADATA_ONLY intentionally omit load-bearing fields.

        Args:
            snapshot: DatasetSnapshot to restore from
            new_asset_id: Optional new asset ID (if restoring to different asset)
            new_tenant_id: Optional new tenant ID (if restoring to different tenant)

        Returns:
            New Dataset instance created from snapshot

        Raises:
            ValueError: when ``snapshot.snapshot_type`` is not FULL.
        """

        from .models import Dataset

        if snapshot.snapshot_type != SnapshotType.FULL:
            raise ValueError(
                f"Cannot restore from snapshot type {snapshot.snapshot_type!r}. "
                f"Only FULL snapshots contain the complete payload required "
                f"for restoration. Valid types for restore: FULL"
            )

        original_dataset = snapshot.dataset

        # Use original asset/tenant if not specified
        asset_id = new_asset_id or original_dataset.asset_id
        tenant_id = new_tenant_id or original_dataset.tenant_id

        # Get next version number
        version = 1
        latest = (
            Dataset.objects.filter(tenant_id=tenant_id, asset_id=asset_id)
            .order_by("-version")
            .first()
        )
        if latest:
            version = latest.version + 1

        # Create new dataset from snapshot
        snapshot_data = snapshot.snapshot_data

        # Create new file reference (or reuse if same file)
        file_obj = original_dataset.file

        restored_dataset = Dataset.objects.create(
            tenant_id=tenant_id,
            asset_id=asset_id,
            file=file_obj,
            schema_json=snapshot_data.get("schema_json"),
            sample_data_json=snapshot_data.get("sample_data_json"),
            row_count=snapshot_data.get("row_count"),
            format=snapshot_data.get("format", original_dataset.format),
            version=version,
            created_by=original_dataset.created_by,
        )

        # Initialize version history
        from .versioning import VersionHistoryManager

        VersionHistoryManager.create_version(
            dataset=restored_dataset,
            semantic_version=snapshot_data.get("semantic_version"),
            version_tags=snapshot_data.get("version_tags", []),
            snapshot_metadata={
                "restored_from_snapshot": str(snapshot.id),
                "original_dataset_id": str(original_dataset.id),
                "restored_at": timezone.now().isoformat(),
            },
            is_current=True,
        )

        return restored_dataset

    @staticmethod
    def get_snapshots_for_dataset(dataset: Dataset) -> list[DatasetSnapshot]:
        """
        Get all snapshots for a dataset.

        Args:
            dataset: Dataset to get snapshots for

        Returns:
            List of DatasetSnapshot instances
        """
        return list(DatasetSnapshot.objects.filter(dataset=dataset).order_by("-created_at"))
