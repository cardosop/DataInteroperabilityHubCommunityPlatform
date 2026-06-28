"""
Test for Inter-Service Communication Search (Task 9.6.1.3.2)

This test verifies that the inter-service communication search script correctly identifies
all inter-service calls and maps dependencies.
"""

import json
from pathlib import Path


class TestInterServiceCommunicationSearch:
    """Test inter-service communication search functionality"""

    @property
    def report_path(self):
        """Path to the generated inter-service communication report"""
        root_dir = Path(__file__).parent.parent.parent
        return root_dir / "docs" / "api-audit" / "inter-service-communication-report.json"

    @property
    def report(self):
        """Load the inter-service communication report"""
        if not self.report_path.exists():
            raise FileNotFoundError(
                f"Report not found at {self.report_path}. "
                "Run 'python3 scripts/search_inter_service_communication.py' first."
            )

        with open(self.report_path) as f:
            return json.load(f)

    def test_report_exists(self):
        """Test that the report file exists"""
        assert self.report_path.exists(), (
            f"Inter-service communication report not found at {self.report_path}"
        )

    def test_report_structure(self):
        """Test that the report has the correct structure"""
        report = self.report
        assert "generated_at" in report
        assert "summary" in report
        assert "service_calls" in report
        assert "dependencies" in report

    def test_summary_fields(self):
        """Test that summary contains required fields"""
        report = self.report
        summary = report["summary"]
        assert "total_service_calls" in summary
        assert "total_dependencies" in summary
        assert "worker_to_api_calls" in summary
        assert "external_to_api_calls" in summary
        assert "api_to_external_calls" in summary
        assert "services_involved" in summary

    def test_service_calls_found(self):
        """Test that service calls were found"""
        report = self.report
        assert report["summary"]["total_service_calls"] > 0, "No service calls found"
        assert len(report["service_calls"]) > 0, "Service calls list is empty"

    def test_dependencies_mapped(self):
        """Test that dependencies were mapped"""
        report = self.report
        assert report["summary"]["total_dependencies"] > 0, "No dependencies mapped"
        assert len(report["dependencies"]) > 0, "Dependencies dictionary is empty"

    def test_service_call_structure(self):
        """Test that service calls have required fields"""
        report = self.report
        for call in report["service_calls"][:10]:  # Check first 10
            assert "file_path" in call
            assert "line_number" in call
            assert "source_service" in call
            assert "target_service" in call
            assert "endpoint" in call
            assert "method" in call
            assert "client_type" in call
            assert "context" in call

    def test_api_to_external_calls_found(self):
        """Test that API → External calls were found"""
        report = self.report
        assert report["summary"]["api_to_external_calls"] > 0, "No API → External calls found"

    def test_external_to_api_calls_found(self):
        """Test that External → API calls were found"""
        report = self.report
        assert report["summary"]["external_to_api_calls"] > 0, "No External → API calls found"

    def test_services_involved(self):
        """Test that multiple services are involved"""
        report = self.report
        services = report["summary"]["services_involved"]
        assert len(services) > 0, "No services found"

        # Should have at least API service and some external services
        assert "api-service" in services, "API service not found"
        assert any(s in ["cli", "sdk"] for s in services), "External services (CLI/SDK) not found"

    def test_dependency_structure(self):
        """Test that dependencies have correct structure"""
        report = self.report
        for _dep_key, dep_data in list(report["dependencies"].items())[:10]:
            assert "source_service" in dep_data
            assert "target_service" in dep_data
            assert "call_count" in dep_data
            assert "endpoints" in dep_data
            assert "call_locations" in dep_data
            assert isinstance(dep_data["call_count"], int)
            assert dep_data["call_count"] > 0

    def test_api_service_dependencies(self):
        """Test that API service dependencies are found"""
        report = self.report
        api_deps = [
            dep
            for dep_key, dep in report["dependencies"].items()
            if dep["source_service"] == "api-service"
        ]
        assert len(api_deps) > 0, "No API service dependencies found"

        # Should have dependencies to external services
        external_services = [
            "dq-service",
            "compliance-service",
            "semantic-service",
            "datacontract-service",
        ]
        found_external = [
            dep["target_service"] for dep in api_deps if dep["target_service"] in external_services
        ]
        assert len(found_external) > 0, (
            f"Expected API dependencies to external services. Found: {found_external}"
        )

    def test_worker_service_dependencies(self):
        """Test that worker service dependencies are found"""
        report = self.report
        # Worker dependencies might be 0 if worker doesn't call API via HTTP (uses Redis queues)
        # But API → Worker should exist
        api_to_worker = [
            dep
            for dep_key, dep in report["dependencies"].items()
            if dep["source_service"] == "api-service" and dep["target_service"] == "worker-service"
        ]
        assert len(api_to_worker) > 0, (
            "Expected API → Worker communication dependency to be detected"
        )

    def test_service_client_types(self):
        """Test that service client types are identified"""
        report = self.report
        client_types = set(call["client_type"] for call in report["service_calls"])

        # Should have various client types
        expected_types = [
            "httpx",
            "requests",
            "ComplianceServiceClient",
            "DQServiceClient",
            "SemanticServiceClient",
        ]
        found_types = [
            ct for ct in expected_types if any(ct in client_type for client_type in client_types)
        ]
        assert len(found_types) > 0, (
            f"Expected service client types not found. Found: {list(client_types)}"
        )

    def test_endpoint_diversity(self):
        """Test that diverse endpoints are found"""
        report = self.report
        endpoints = set(
            call["endpoint"] for call in report["service_calls"] if call["endpoint"] != "unknown"
        )

        # Should have endpoints from different services
        endpoint_keywords = ["health", "scan", "run", "map", "validate", "normalize", "sparql"]
        found_keywords = [
            keyword
            for keyword in endpoint_keywords
            if any(keyword in ep.lower() for ep in endpoints)
        ]
        assert len(found_keywords) >= 2, (
            f"Expected endpoints from multiple services. Found keywords: {found_keywords}"
        )

    def test_file_paths_valid(self):
        """Test that file paths are valid"""
        report = self.report
        for call in report["service_calls"][:10]:
            file_path = call["file_path"]
            assert file_path, "Empty file path found"
            assert "/" in file_path or "\\" in file_path, f"Invalid file path: {file_path}"

    def test_line_numbers_valid(self):
        """Test that line numbers are valid"""
        report = self.report
        for call in report["service_calls"][:10]:
            line_number = call["line_number"]
            assert isinstance(line_number, int), f"Invalid line number type: {type(line_number)}"
            assert line_number > 0, f"Invalid line number: {line_number}"

    def test_comprehensive_coverage(self):
        """Test that search has comprehensive coverage"""
        report = self.report
        # Should find calls in multiple areas
        file_paths = set(call["file_path"] for call in report["service_calls"])

        # Should have files from different areas
        areas = ["hub/apps", "services", "cli", "sdk"]
        found_areas = [area for area in areas if any(area in path for path in file_paths)]

        assert len(found_areas) >= 2, (
            f"Expected service calls from multiple areas. Found: {found_areas}"
        )

    def test_dependency_call_counts(self):
        """Test that dependency call counts are reasonable"""
        report = self.report
        for dep_key, dep_data in report["dependencies"].items():
            call_count = dep_data["call_count"]
            assert call_count > 0, f"Dependency {dep_key} has zero call count"
            assert call_count <= report["summary"]["total_service_calls"], (
                f"Dependency {dep_key} call count ({call_count}) exceeds total service calls"
            )

    def test_service_communication_patterns(self):
        """Test that different communication patterns are found"""
        report = self.report
        # Should have both HTTP calls and queue-based communication
        http_calls = [c for c in report["service_calls"] if c["method"] != "ENQUEUE"]
        queue_calls = [
            c
            for c in report["service_calls"]
            if c["method"] == "ENQUEUE" or "queue" in c["endpoint"].lower()
        ]

        # Should have at least HTTP calls
        assert len(http_calls) > 0, "No HTTP service calls found"
        # Queue calls might be 0 if not detected, which is OK

    def test_external_service_communication(self):
        """Test that external service communication is found"""
        report = self.report
        external_calls = [
            call
            for call in report["service_calls"]
            if call["source_service"] in ["cli", "sdk"] or call["target_service"] in ["cli", "sdk"]
        ]
        assert len(external_calls) > 0, "No external service communication found"
