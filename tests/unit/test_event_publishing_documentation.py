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
from typing import List, Set

from unittest import TestCase

from hub.apps.core.events.service_publishers import (
    AccessEventPublisher,
    AssetEventPublisher,
    ComplianceEventPublisher,
    ContractEventPublisher,
    DataMeshEventPublisher,
    DatasetEventPublisher,
    FileEventPublisher,
    IngestionEventPublisher,
    LineageEventPublisher,
    MarketplaceEventPublisher,
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

    # All event publisher classes
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
        TransformationEventPublisher,
        DataMeshEventPublisher,
        VirtualizationEventPublisher,
        FileEventPublisher,
        LineageEventPublisher,
        SearchEventPublisher,
        PaymentGatewayEventPublisher,
        TenantEventPublisher,
        NormalizationEventPublisher,
        PaymentEventPublisher,
        ObservabilityEventPublisher,
    ]

    def setUp(self):
        """Set up test fixtures."""
        self.docs_dir = Path(__file__).parent.parent.parent / "docs"
        self.event_bus_doc = self.docs_dir / "EVENT_BUS.md"
        self.event_types_doc = self.docs_dir / "EVENT_TYPES_REFERENCE.md"

    def test_all_publishers_documented_in_event_bus(self):
        """Test that all event publishers are documented in EVENT_BUS.md."""
        self.assertTrue(
            self.event_bus_doc.exists(),
            "EVENT_BUS.md should exist"
        )

        content = self.event_bus_doc.read_text()

        # Check for event publisher pattern documentation
        self.assertIn(
            "Event Publisher Pattern",
            content,
            "EVENT_BUS.md should document the event publisher pattern"
        )

        # Check that all publishers are documented
        publisher_names = [
            "ContractEventPublisher",
            "AssetEventPublisher",
            "DatasetEventPublisher",
            "IngestionEventPublisher",
            "QualityEventPublisher",
            "ComplianceEventPublisher",
            "VersionEventPublisher",
            "VersioningEventPublisher",
            "AccessEventPublisher",
            "MarketplaceEventPublisher",
            "WorkflowEventPublisher",
            "ODPSEventPublisher",
            "TransformationEventPublisher",
            "DataMeshEventPublisher",
            "VirtualizationEventPublisher",
            "FileEventPublisher",
            "LineageEventPublisher",
            "SearchEventPublisher",
            "PaymentGatewayEventPublisher",
            "TenantEventPublisher",
            "NormalizationEventPublisher",
            "PaymentEventPublisher",
            "ObservabilityEventPublisher",
        ]

        for publisher_name in publisher_names:
            self.assertIn(
                publisher_name,
                content,
                f"{publisher_name} should be documented in EVENT_BUS.md"
            )

    def test_all_event_types_documented(self):
        """Test that all event types are documented in EVENT_TYPES_REFERENCE.md."""
        self.assertTrue(
            self.event_types_doc.exists(),
            "EVENT_TYPES_REFERENCE.md should exist"
        )

        content = self.event_types_doc.read_text()

        # Extract all event types from publishers
        all_event_types = self._extract_all_event_types()

        # Check that major event categories are documented
        event_categories = [
            "Contract Events",
            "Asset Events",
            "Dataset Events",
            "Ingestion Events",
            "Quality Events",
            "Compliance Events",
            "Version Events",
            "Access Events",
            "Marketplace Events",
            "Workflow Events",
            "ODPS Events",
            "Transformation Events",
            "Data Mesh Events",
            "Virtualization Events",
            "File Events",
            "Lineage Events",
            "Search Events",
            "Payment Gateway Events",
            "Tenant Events",
            "Normalization Events",
            "Payment Events",
            "Observability Events",
        ]

        for category in event_categories:
            self.assertIn(
                category,
                content,
                f"{category} should be documented in EVENT_TYPES_REFERENCE.md"
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
                f"{event_type} should be documented in EVENT_TYPES_REFERENCE.md"
            )

        # Validate that we extracted event types successfully
        self.assertGreater(
            len(all_event_types),
            50,
            f"Should extract at least 50 event types from publishers, got {len(all_event_types)}"
        )

    def test_event_publisher_pattern_documented(self):
        """Test that the event publisher pattern is documented."""
        content = self.event_bus_doc.read_text()

        # Check for pattern documentation sections
        pattern_sections = [
            "Event Publisher Pattern",
            "Pattern Components",
            "Pattern Implementation Steps",
            "Pattern Benefits",
            "Pattern Best Practices",
        ]

        for section in pattern_sections:
            self.assertIn(
                section,
                content,
                f"{section} should be documented in EVENT_BUS.md"
            )

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
                f"{publisher_class.__name__} should have at least one publish method"
            )
            total_methods += len(methods)

        # Validate that we have a reasonable number of publisher methods
        self.assertGreater(
            total_methods,
            100,
            f"Should have at least 100 publisher methods across all publishers, got {total_methods}"
        )

    def _extract_all_event_types(self) -> Set[str]:
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
        self.assertTrue(
            self.event_bus_doc.exists(),
            "EVENT_BUS.md should exist"
        )
        self.assertTrue(
            self.event_types_doc.exists(),
            "EVENT_TYPES_REFERENCE.md should exist"
        )

    def test_event_publisher_count(self):
        """Test that we have the expected number of event publishers."""
        self.assertEqual(
            len(self.EVENT_PUBLISHERS),
            23,
            "Should have 23 event publishers"
        )

    def test_publisher_services_documented(self):
        """Test that publisher services are documented in EVENT_BUS.md."""
        content = self.event_bus_doc.read_text()

        # Check that service class names are documented (they use class names, not service_name strings)
        service_classes = [
            "ContractService",
            "AssetService",
            "DataMeshService",
            "TransformationService",
            "VirtualizationService",
        ]

        for service_class in service_classes:
            self.assertIn(
                service_class,
                content,
                f"Service class '{service_class}' should be documented in EVENT_BUS.md"
            )

    def test_event_publisher_usage_examples(self):
        """Test that usage examples are documented."""
        content = self.event_bus_doc.read_text()

        # Check for usage examples
        usage_keywords = [
            "class MyService",
            "publish_",
            "EventPublisher",
            "service_name",
        ]

        for keyword in usage_keywords:
            self.assertIn(
                keyword,
                content,
                f"Usage example with '{keyword}' should be documented in EVENT_BUS.md"
            )

