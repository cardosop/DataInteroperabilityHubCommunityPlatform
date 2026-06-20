"""
Event Schema Versioning

Manages event schema versions and provides migration utilities.
"""

from typing import Any

import structlog

from .event_types import CURRENT_EVENT_VERSION, EVENT_TYPE_SCHEMAS

logger = structlog.get_logger(__name__)


class EventSchemaVersionManager:
    """
    Manages event schema versions and migrations.

    Provides utilities for:
    - Schema version validation
    - Schema migration
    - Backward compatibility checks
    """

    def __init__(self):
        """Initialize version manager."""
        self.current_version = CURRENT_EVENT_VERSION
        self.supported_versions = ["1.0.0"]  # Add more versions as they're introduced

    def validate_version(self, event_version: str) -> tuple[bool, str | None]:
        """
        Validate event version is supported.

        Args:
            event_version: Event version to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if event_version not in self.supported_versions:
            return (
                False,
                f"Unsupported event version: {event_version}. Supported versions: {self.supported_versions}",
            )
        return True, None

    def migrate_event(self, event: dict[str, Any], target_version: str = None) -> dict[str, Any]:
        """
        Migrate event to target version.

        Args:
            event: Event dictionary
            target_version: Target version (defaults to current version)

        Returns:
            Migrated event dictionary
        """
        target_version = target_version or self.current_version
        event_version = event.get("event_version", "1.0.0")

        if event_version == target_version:
            return event

        # Migration logic would go here
        # For now, just update version if compatible
        migrated_event = event.copy()
        migrated_event["event_version"] = target_version

        logger.info(
            "event_migrated",
            event_id=event.get("event_id"),
            from_version=event_version,
            to_version=target_version,
        )

        return migrated_event

    def get_schema_for_version(self, event_type: str, version: str) -> dict[str, Any] | None:
        """
        Get schema for specific event type and version.

        Args:
            event_type: Event type
            version: Schema version

        Returns:
            Schema dictionary or None if not found
        """
        if version not in self.supported_versions:
            return None

        # For now, all versions use the same schema
        # In the future, this would return version-specific schemas
        return EVENT_TYPE_SCHEMAS.get(event_type)

    def is_backward_compatible(self, from_version: str, to_version: str) -> bool:
        """
        Check if migration from one version to another is backward compatible.

        Args:
            from_version: Source version
            to_version: Target version

        Returns:
            True if backward compatible
        """
        # Simple version comparison for now
        # In the future, this would check actual schema compatibility
        if from_version == to_version:
            return True

        # For now, assume all versions are backward compatible
        return True


# Global version manager instance
_version_manager = None


def get_version_manager() -> EventSchemaVersionManager:
    """Get global version manager instance."""
    global _version_manager
    if _version_manager is None:
        _version_manager = EventSchemaVersionManager()
    return _version_manager
