"""
Test Factories for Version History

Real factories (not mocks) for creating test data for version history models.

NOTE: These factories are placeholders for future version history models.
They will be updated when the version history models are created in Phase 6.
"""

from typing import Any

from django.contrib.auth import get_user_model

from hub.apps.datasets.models import Dataset

User = get_user_model()


class DatasetVersionFactory:
    """
    Factory for creating Dataset version instances.

    NOTE: This is a placeholder factory. The actual version history fields
    will be added to the Dataset model in Phase 6. This factory will be updated at that time.

    Expected fields to be added to Dataset model (from design.md):
    - parent_version_id: ForeignKey to Dataset (self-referential)
    - version_hash: str
    - snapshot_metadata: JSONField
    - is_current: bool
    - archived_at: DateTime (optional)
    - semantic_version: str (e.g., "1.2.3")
    - version_tags: JSONField (array of strings)
    """

    @staticmethod
    def create_dataset_version(
        dataset: Dataset,
        parent_version: Dataset | None = None,
        version_hash: str | None = None,
        snapshot_metadata: dict[str, Any] | None = None,
        is_current: bool = True,
        semantic_version: str | None = None,
        version_tags: list[str] | None = None,
        **kwargs,
    ) -> Dataset:
        """
        Create a Dataset version.

        NOTE: This is a placeholder. Will be implemented when version history fields are added.

        Args:
            dataset: Base Dataset instance
            parent_version: Parent version Dataset (for version tree)
            version_hash: Version hash
            snapshot_metadata: Snapshot metadata JSON
            is_current: Whether this is the current version
            semantic_version: Semantic version string (e.g., "1.2.3")
            version_tags: List of version tags
            **kwargs: Additional fields

        Returns:
            Dataset instance with version history (when fields exist)
        """
        # Placeholder - will be implemented when version history fields are added
        raise NotImplementedError(
            "Dataset version history fields not yet added. "
            "This factory will be implemented in Phase 6."
        )


class SchemaVersionFactory:
    """
    Factory for creating SchemaVersion instances.

    NOTE: This is a placeholder factory. The actual SchemaVersion model
    will be created in Phase 6. This factory will be updated at that time.

    Expected model structure (from design.md):
    - id: UUID
    - dataset: ForeignKey to Dataset
    - version_number: int
    - schema_json: JSONField
    - compatibility_level: str (BREAKING, NON_BREAKING, ADDITIVE)
    - change_log: JSONField
    - created_at: DateTime
    """

    @staticmethod
    def create_schema_version(
        dataset: Dataset,
        version_number: int = 1,
        schema_json: dict[str, Any] | None = None,
        compatibility_level: str = "NON_BREAKING",
        change_log: dict[str, Any] | None = None,
        **kwargs,
    ):
        """
        Create a SchemaVersion instance.

        NOTE: This is a placeholder. Will be implemented when SchemaVersion model exists.

        Args:
            dataset: Dataset instance
            version_number: Schema version number
            schema_json: Schema JSON
            compatibility_level: Compatibility level (BREAKING, NON_BREAKING, ADDITIVE)
            change_log: Change log JSON
            **kwargs: Additional fields

        Returns:
            SchemaVersion instance (when model exists)
        """
        # Placeholder - will be implemented when model exists
        raise NotImplementedError(
            "SchemaVersion model not yet created. This factory will be implemented in Phase 6."
        )
