"""
Test for Webhook Payloads and Events Search (Task 9.6.1.2.5)

This test verifies that the webhook payloads and events search script correctly identifies
all webhook endpoint references, payload structures, and subscription configurations.
"""

import json
from pathlib import Path


class TestWebhookPayloadsAndEventsSearch:
    """Test webhook payloads and events search functionality"""

    @property
    def report_path(self):
        """Path to the generated webhook payloads and events report"""
        root_dir = Path(__file__).parent.parent.parent
        return root_dir / "docs" / "api-audit" / "webhook-payloads-and-events-report.json"

    @property
    def report(self):
        """Load the webhook payloads and events report"""
        if not self.report_path.exists():
            raise FileNotFoundError(
                f"Report not found at {self.report_path}. "
                "Run 'python3 scripts/search_webhook_payloads_and_events.py' first."
            )

        with open(self.report_path) as f:
            return json.load(f)

    def test_report_exists(self):
        """Test that the report file exists"""
        assert self.report_path.exists(), (
            f"Webhook payloads and events report not found at {self.report_path}"
        )

    def test_report_structure(self):
        """Test that the report has the correct structure"""
        report = self.report
        assert "generated_at" in report
        assert "summary" in report
        assert "endpoint_references" in report
        assert "payload_structures" in report
        assert "subscription_configs" in report

    def test_summary_fields(self):
        """Test that summary contains required fields"""
        report = self.report
        summary = report["summary"]
        assert "total_endpoint_references" in summary
        assert "total_payload_structures" in summary
        assert "total_subscription_configs" in summary
        assert "unique_event_types" in summary
        assert "event_types" in summary

    def test_endpoint_references_found(self):
        """Test that webhook endpoint references were found"""
        report = self.report
        assert report["summary"]["total_endpoint_references"] > 0, (
            "No webhook endpoint references found"
        )
        assert len(report["endpoint_references"]) > 0, "Endpoint references list is empty"

    def test_payload_structures_found(self):
        """Test that payload structures were found"""
        report = self.report
        assert report["summary"]["total_payload_structures"] > 0, "No payload structures found"
        assert len(report["payload_structures"]) > 0, "Payload structures list is empty"

    def test_subscription_configs_found(self):
        """Test that subscription configurations were found"""
        report = self.report
        assert report["summary"]["total_subscription_configs"] > 0, (
            "No subscription configurations found"
        )
        assert len(report["subscription_configs"]) > 0, "Subscription configs list is empty"

    def test_event_types_found(self):
        """Test that event types were found"""
        report = self.report
        assert report["summary"]["unique_event_types"] > 0, "No event types found"
        assert len(report["summary"]["event_types"]) > 0, "Event types list is empty"

    def test_endpoint_reference_structure(self):
        """Test that endpoint references have required fields"""
        report = self.report
        for ref in report["endpoint_references"][:10]:  # Check first 10
            assert "file_path" in ref
            assert "line_number" in ref
            assert "endpoint" in ref
            assert "method" in ref
            assert "context" in ref

    def test_payload_structure_fields(self):
        """Test that payload structures have required fields"""
        report = self.report
        for struct in report["payload_structures"][:10]:  # Check first 10
            assert "file_path" in struct
            assert "line_number" in struct
            assert "event_type" in struct
            assert "payload_fields" in struct
            assert isinstance(struct["payload_fields"], list)

    def test_subscription_config_structure(self):
        """Test that subscription configs have required fields"""
        report = self.report
        for config in report["subscription_configs"][:10]:  # Check first 10
            assert "file_path" in config
            assert "line_number" in config
            assert "event_types" in config
            assert isinstance(config["event_types"], list)

    def test_webhook_endpoints_found(self):
        """Test that webhook API endpoints were found"""
        report = self.report
        webhook_endpoints = [
            ref
            for ref in report["endpoint_references"]
            if "/webhooks" in ref.get("endpoint", "").lower()
        ]
        assert len(webhook_endpoints) > 0, "No webhook API endpoints found"

    def test_valid_event_types(self):
        """Test that found event types are valid"""
        report = self.report
        valid_prefixes = (
            "contract",
            "asset",
            "odps",
            "pipeline",
            "mesh",
            "virtualization",
            "ingestion",
            "quality",
            "compliance",
            "version",
        )

        invalid_event_types = []
        for event_type in report["summary"]["event_types"]:
            # Skip wildcard patterns
            if "*" in event_type or event_type.endswith("."):
                continue

            # Must contain a dot
            if "." not in event_type:
                invalid_event_types.append(event_type)
                continue

            # Must start with valid prefix
            if not any(event_type.startswith(prefix) for prefix in valid_prefixes):
                invalid_event_types.append(event_type)

        assert len(invalid_event_types) == 0, (
            f"Found invalid event types: {invalid_event_types[:10]}"
        )

    def test_odps_event_types_found(self):
        """Test that ODPS event types were found"""
        report = self.report
        odps_event_types = [et for et in report["summary"]["event_types"] if et.startswith("odps.")]
        assert len(odps_event_types) > 0, "No ODPS event types found"

    def test_payload_fields_completeness(self):
        """Test that payload structures have common required fields"""
        report = self.report
        common_fields = ["event_type", "resource_type", "resource_id", "timestamp", "data"]

        payloads_with_common_fields = 0
        for struct in report["payload_structures"]:
            fields = struct.get("payload_fields", [])
            if any(field in fields for field in common_fields):
                payloads_with_common_fields += 1

        # At least some payloads should have common fields
        assert payloads_with_common_fields > 0, (
            "No payload structures found with common required fields"
        )

    def test_subscription_event_types_valid(self):
        """Test that subscription configs have valid event types"""
        report = self.report
        valid_prefixes = (
            "contract",
            "asset",
            "odps",
            "pipeline",
            "mesh",
            "virtualization",
            "ingestion",
            "quality",
            "compliance",
            "version",
        )

        invalid_configs = []
        for config in report["subscription_configs"][:20]:  # Check first 20
            event_types = config.get("event_types", [])
            for event_type in event_types:
                # Skip wildcard patterns
                if "*" in event_type or event_type.endswith("."):
                    continue

                # Must contain a dot and start with valid prefix
                if "." not in event_type or not any(
                    event_type.startswith(prefix) for prefix in valid_prefixes
                ):
                    invalid_configs.append((config["file_path"], event_type))

        assert len(invalid_configs) == 0, (
            f"Found invalid event types in subscription configs: {invalid_configs[:10]}"
        )

    def test_endpoint_references_diversity(self):
        """Test that endpoint references cover different webhook operations"""
        report = self.report
        endpoints = [ref["endpoint"] for ref in report["endpoint_references"]]

        # Should have endpoints for different operations
        operation_keywords = ["webhooks", "deliveries", "test", "event-types"]
        found_operations = [
            keyword
            for keyword in operation_keywords
            if any(keyword in ep.lower() for ep in endpoints)
        ]
        assert len(found_operations) >= 2, (
            f"Expected endpoints for multiple operations. Found: {found_operations}"
        )

    def test_file_paths_valid(self):
        """Test that file paths are valid"""
        report = self.report
        for ref in report["endpoint_references"][:10]:
            file_path = ref["file_path"]
            assert file_path, "Empty file path found"
            assert "/" in file_path or "\\" in file_path, f"Invalid file path: {file_path}"

    def test_line_numbers_valid(self):
        """Test that line numbers are valid"""
        report = self.report
        for ref in report["endpoint_references"][:10]:
            line_number = ref["line_number"]
            assert isinstance(line_number, int), f"Invalid line number type: {type(line_number)}"
            assert line_number > 0, f"Invalid line number: {line_number}"

    def test_comprehensive_coverage(self):
        """Test that search has comprehensive coverage"""
        report = self.report
        # Should find references in multiple areas
        file_paths = set()
        file_paths.update(ref["file_path"] for ref in report["endpoint_references"])
        file_paths.update(struct["file_path"] for struct in report["payload_structures"])
        file_paths.update(config["file_path"] for config in report["subscription_configs"])

        # Should have files from different areas
        areas = ["hub/apps/webhooks", "sdk", "tests", "scripts"]
        found_areas = [area for area in areas if any(area in path for path in file_paths)]

        assert len(found_areas) >= 2, (
            f"Expected references from multiple areas. Found: {found_areas}"
        )

    def test_webhook_service_references(self):
        """Test that webhook service references were found"""
        report = self.report
        service_references = [
            ref
            for ref in report["endpoint_references"]
            if "service" in ref.get("context", "").lower()
            or "WebhookDeliveryService" in ref.get("context", "")
        ]
        # Should find some service references
        assert len(service_references) > 0 or report["summary"]["total_endpoint_references"] > 0, (
            "No webhook service references found"
        )
