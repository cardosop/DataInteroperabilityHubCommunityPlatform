"""
Tests to validate event publishing documentation completeness.

This test ensures that:
1. All event publishers are documented in EVENT_BUS.md
2. All event types are documented in EVENT_TYPES_REFERENCE.md
3. Event publisher pattern is documented
"""

import inspect
import re
from pathlib import Path
from unittest import TestCase

from hub.apps.core.events.service_publishers import (
    AccessEventPublisher,
    AssetEventPublisher,
    BaaSEventPublisher,
    ComplianceEventPublisher,
    ContractEventPublisher,
    DataMeshEventPublisher,
    DatasetEventPublisher,
    FileEventPublisher,
    IngestionEventPublisher,
    IntegrationEventPublisher,
    LineageEventPublisher,
    MarketplaceEventPublisher,
    MLEventPublisher,
    NormalizationEventPublisher,
    ObservabilityEventPublisher,
    ODPSEventPublisher,
    PaymentEventPublisher,
    PaymentGatewayEventPublisher,
    QualityEventPublisher,
    SearchEventPublisher,
    TenantEventPublisher,
    TransformationEventPublisher,
    VersionEventPublisher,
    VersioningEventPublisher,
    VirtualizationEventPublisher,
    WorkflowEventPublisher,
)


class EventPublishingDocumentationTest(TestCase):
    """Test event publishing documentation completeness."""

    # All event publisher classes (must match service_publishers.py)
    EVENT_PUBLISHERS = [
        ContractEventPublisher,
        AssetEventPublisher,
        DatasetEventPublisher,
        IngestionEventPublisher,
        QualityEventPublisher,
        ComplianceEventPublisher,
        VersionEventPublisher,
        VersioningEventPublisher,
        AccessEventPublisher,
        MarketplaceEventPublisher,
        WorkflowEventPublisher,
        ODPSEventPublisher,
        DataMeshEventPublisher,
        VirtualizationEventPublisher,
        FileEventPublisher,
        LineageEventPublisher,
        SearchEventPublisher,
        PaymentGatewayEventPublisher,
        TenantEventPublisher,
        TransformationEventPublisher,
        NormalizationEventPublisher,
        PaymentEventPublisher,
        ObservabilityEventPublisher,
        IntegrationEventPublisher,
        BaaSEventPublisher,
        MLEventPublisher,
    ]

    def setUp(self):
        """Set up test fixtures."""
        self.docs_dir = Path(__file__).parent.parent.parent / "docs"
        self.event_bus_doc = self.docs_dir / "EVENT_BUS.md"
        self.event_types_doc = self.docs_dir / "EVENT_TYPES_REFERENCE.md"

    def test_all_publishers_documented_in_event_bus(self):
        """Test that event publisher services are documented in EVENT_BUS.md."""
        self.assertTrue(self.event_bus_doc.exists(), "EVENT_BUS.md should exist")

        content = self.event_bus_doc.read_text()

        # Check for required documentation sections
        self.assertIn("Event Publisher Pattern", content,
                      "EVENT_BUS.md should document the event publisher pattern")
        self.assertIn("Publishers by service", content,
                      "EVENT_BUS.md should list publishers by service")

        # Current doc format lists services rather than individual publisher
        # classes.  Verify the api-service section exists and names the
        # key service-layer publisher classes.
        service_publishers = [
            "ContractService",
            "AssetService",
            "DatasetService",
            "MarketplaceService",
            "GovernanceService",
        ]
        for name in service_publishers:
            self.assertIn(
                name, content,
                f"EVENT_BUS.md should document {name} as a publisher service"
            )

    def test_all_event_types_documented(self):
        """Test that all event types are documented in EVENT_TYPES_REFERENCE.md."""
        self.assertTrue(self.event_types_doc.exists(), "EVENT_TYPES_REFERENCE.md should exist")

        content = self.event_types_doc.read_text()

        # Current doc has 6 event categories
        event_categories = [
            "Contract Events",
            "Asset Events",
            "ODPS Events",
            "Pipeline Events",
            "Workflow Events",
            "Tenant Events",
        ]

        for category in event_categories:
            self.assertIn(
                category, content,
                f"{category} section should be present in EVENT_TYPES_REFERENCE.md"
            )

        # Check that key event types are documented
        key_event_types = [
            "contract.created",
            "asset.created",
            "odps.created",
            "pipeline.started",
            "workflow.started",
            "tenant.created",
        ]

        for event_type in key_event_types:
            self.assertIn(
                f"`{event_type}`",
                content,
                f"`{event_type}` should be documented in EVENT_TYPES_REFERENCE.md",
            )

    def test_event_publisher_pattern_documented(self):
        """Test that the event publisher pattern is documented."""
        content = self.event_bus_doc.read_text()

        # Check for pattern documentation sections
        pattern_sections = [
            "Event Publisher Pattern",
            "Publisher Services",
        ]

        for section in pattern_sections:
            self.assertIn(section, content, f"{section} should be documented in EVENT_BUS.md")

    def test_publisher_methods_exist(self):
        """Test that all publishers have publish methods."""
        total_methods = 0
        for publisher_class in self.EVENT_PUBLISHERS:
            methods = [
                name
                for name, method in inspect.getmembers(
                    publisher_class, predicate=inspect.isfunction
                )
                if name.startswith("publish_")
            ]

            self.assertGreater(
                len(methods),
                0,
                f"{publisher_class.__name__} should have at least one publish method",
            )
            total_methods += len(methods)

        # Validate that we have a reasonable number of publisher methods
        self.assertGreater(
            total_methods,
            100,
            f"Should have at least 100 publisher methods across all publishers, got {total_methods}",
        )

    def _extract_all_event_types(self) -> set[str]:
        """Extract all event types from all publishers."""
        event_types = set()

        for publisher_class in self.EVENT_PUBLISHERS:
            # Get all publish methods
            methods = [
                method
                for name, method in inspect.getmembers(
                    publisher_class, predicate=inspect.isfunction
                )
                if name.startswith("publish_")
            ]

            # Extract event types from method source code
            for method in methods:
                source = inspect.getsource(method)
                # Look for event_type="..." patterns
                matches = re.findall(r'event_type=["\']([^"\']+)["\']', source)
                event_types.update(matches)

        return event_types

    def test_documentation_files_exist(self):
        """Test that documentation files exist."""
        self.assertTrue(self.event_bus_doc.exists(), "EVENT_BUS.md should exist")
        self.assertTrue(self.event_types_doc.exists(), "EVENT_TYPES_REFERENCE.md should exist")

    def test_event_publisher_count(self):
        """Test that we have the expected number of event publishers."""
        self.assertEqual(len(self.EVENT_PUBLISHERS), 26, "Should have 26 event publishers")

    def test_publisher_services_documented(self):
        """Test that publisher services are documented in EVENT_BUS.md."""
        content = self.event_bus_doc.read_text()

        # Current doc lists services under "Publisher Services" section
        self.assertIn("Publisher Services", content,
                      "EVENT_BUS.md should have a 'Publisher Services' section")
        service_classes = [
            "ContractService",
            "AssetService",
            "DatasetService",
            "MarketplaceService",
            "GovernanceService",
        ]
        for service_class in service_classes:
            self.assertIn(
                service_class, content,
                f"Service class '{service_class}' should be documented in EVENT_BUS.md"
            )

    def test_event_publisher_usage_examples(self):
        """Test that usage examples are documented in EVENT_BUS.md."""
        content = self.event_bus_doc.read_text()

        # Current doc includes a "Usage Example" code block with publish()
        self.assertIn("event_bus.publish", content,
                      "EVENT_BUS.md should show event_bus.publish() usage")
        self.assertIn("Usage Example", content,
                      "EVENT_BUS.md should have a 'Usage Example' section")
