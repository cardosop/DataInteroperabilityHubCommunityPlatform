"""
Tests for event schema versioning.
"""

from django.test import TestCase

from hub.apps.core.events.versioning import (
    CURRENT_EVENT_VERSION,
    EventSchemaVersionManager,
    get_version_manager,
)


class EventSchemaVersioningTest(TestCase):
    """Test event schema versioning."""

    def setUp(self):
        """Set up test data."""
        self.version_manager = EventSchemaVersionManager()

    def test_validate_version_current(self):
        """Test validating current version."""
        is_valid, error = self.version_manager.validate_version(CURRENT_EVENT_VERSION)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_version_unsupported(self):
        """Test validating unsupported version."""
        is_valid, error = self.version_manager.validate_version("2.0.0")
        self.assertFalse(is_valid)
        self.assertIn("Unsupported", error)

    def test_migrate_event_same_version(self):
        """Test migrating event with same version."""
        event = {
            "event_id": "test-id",
            "event_version": CURRENT_EVENT_VERSION,
            "event_type": "contract.created",
            "data": {},
        }
        migrated = self.version_manager.migrate_event(event)
        self.assertEqual(migrated["event_version"], CURRENT_EVENT_VERSION)

    def test_migrate_event_different_version(self):
        """Test migrating event to different version."""
        event = {
            "event_id": "test-id",
            "event_version": "1.0.0",
            "event_type": "contract.created",
            "data": {},
        }
        migrated = self.version_manager.migrate_event(event, target_version=CURRENT_EVENT_VERSION)
        self.assertEqual(migrated["event_version"], CURRENT_EVENT_VERSION)

    def test_get_schema_for_version(self):
        """Test getting schema for specific version."""
        schema = self.version_manager.get_schema_for_version(
            "contract.created", CURRENT_EVENT_VERSION
        )
        self.assertIsNotNone(schema)

    def test_get_schema_for_version_unsupported(self):
        """Test getting schema for unsupported version."""
        schema = self.version_manager.get_schema_for_version("contract.created", "2.0.0")
        self.assertIsNone(schema)

    def test_is_backward_compatible_same_version(self):
        """Test backward compatibility check for same version."""
        compatible = self.version_manager.is_backward_compatible(
            CURRENT_EVENT_VERSION, CURRENT_EVENT_VERSION
        )
        self.assertTrue(compatible)

    def test_is_backward_compatible_different_versions(self):
        """Test backward compatibility check for different versions."""
        compatible = self.version_manager.is_backward_compatible("1.0.0", CURRENT_EVENT_VERSION)
        self.assertTrue(compatible)  # Currently all versions are compatible

    def test_get_version_manager_singleton(self):
        """Test that get_version_manager returns singleton."""
        manager1 = get_version_manager()
        manager2 = get_version_manager()
        self.assertIs(manager1, manager2)
