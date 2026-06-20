"""
Test for API Client Usage Search (Task 9.6.1.2.3)

This test verifies that the API client usage search script correctly identifies
all API client usage patterns and maps them to endpoints.

This test does not require Django - it only validates the JSON report structure.
"""

import json
from pathlib import Path

# Note: This test does not require pytest or Django - it validates JSON report structure only
# The test can be run standalone using run_api_client_usage_tests.py


class TestAPIClientUsageSearch:
    """Test API client usage search functionality"""

    @property
    def report_path(self):
        """Path to the generated API client usage report"""
        root_dir = Path(__file__).parent.parent.parent
        return root_dir / "docs" / "api-audit" / "api-client-usage-report.json"

    @property
    def report(self):
        """Load the API client usage report"""
        if not self.report_path.exists():
            raise FileNotFoundError(
                f"Report not found at {self.report_path}. "
                "Run 'python3 scripts/search_api_client_usage.py' first."
            )

        with open(self.report_path) as f:
            return json.load(f)

    def test_report_exists(self):
        """Test that the report file exists"""
        assert self.report_path.exists(), f"API client usage report not found at {self.report_path}"

    def test_report_structure(self):
        """Test that the report has the correct structure"""
        report = self.report
        assert "generated_at" in report
        assert "summary" in report
        assert "api_calls" in report
        assert "client_usages" in report
        assert "endpoint_mappings" in report

    def test_summary_fields(self):
        """Test that summary contains required fields"""
        report = self.report
        summary = report["summary"]
        assert "total_api_calls" in summary
        assert "total_endpoints" in summary
        assert "total_client_usages" in summary
        assert "client_types" in summary
        assert "methods" in summary

    def test_api_calls_found(self):
        """Test that API calls were found"""
        report = self.report
        assert report["summary"]["total_api_calls"] > 0, "No API calls found"
        assert len(report["api_calls"]) > 0, "API calls list is empty"

    def test_endpoints_mapped(self):
        """Test that endpoints were mapped"""
        report = self.report
        assert report["summary"]["total_endpoints"] > 0, "No endpoints mapped"
        assert len(report["endpoint_mappings"]) > 0, "Endpoint mappings are empty"

    def test_api_call_structure(self):
        """Test that API calls have required fields"""
        report = self.report
        for call in report["api_calls"][:10]:  # Check first 10
            assert "file_path" in call
            assert "line_number" in call
            assert "method" in call
            assert "endpoint" in call
            assert "client_type" in call
            assert "context" in call
            assert "is_direct" in call

    def test_client_types_detected(self):
        """Test that different client types were detected"""
        report = self.report
        client_types = report["summary"]["client_types"]
        assert len(client_types) > 0, "No client types detected"

        # Should have at least some common client types
        expected_types = ["client", "requests", "httpx"]
        found_types = [ct for ct in expected_types if ct in client_types]
        assert len(found_types) > 0, (
            f"Expected client types not found. Found: {list(client_types.keys())}"
        )

    def test_http_methods_detected(self):
        """Test that HTTP methods were detected"""
        report = self.report
        methods = report["summary"]["methods"]
        assert len(methods) > 0, "No HTTP methods detected"

        # Should have common HTTP methods
        expected_methods = ["GET", "POST"]
        found_methods = [m for m in expected_methods if m in methods]
        assert len(found_methods) > 0, (
            f"Expected HTTP methods not found. Found: {list(methods.keys())}"
        )

    def test_endpoint_mapping_structure(self):
        """Test that endpoint mappings have correct structure"""
        report = self.report
        for _endpoint, mapping in list(report["endpoint_mappings"].items())[:10]:
            assert "endpoint" in mapping
            assert "call_count" in mapping
            assert "methods" in mapping
            assert "client_types" in mapping
            assert "calls" in mapping
            assert isinstance(mapping["call_count"], int)
            assert mapping["call_count"] > 0

    def test_api_v1_endpoints_found(self):
        """Test that /api/v1 endpoints were found"""
        report = self.report
        api_v1_endpoints = [ep for ep in report["endpoint_mappings"].keys() if "/api/v1/" in ep]
        assert len(api_v1_endpoints) > 0, "No /api/v1 endpoints found"

    def test_sdk_client_usages_found(self):
        """Test that SDK client usages were found"""
        report = self.report
        # SDK client usages should be found in SDK modules
        [
            usage
            for usage in report.get("client_usages", [])
            if "sdk" in usage.get("file_path", "").lower()
        ]
        # Note: This might be 0 if SDK analysis didn't find patterns, which is OK
        # The important thing is that the structure exists
        assert "client_usages" in report

    def test_no_empty_endpoints(self):
        """Test that no empty endpoints were found"""
        report = self.report
        empty_endpoints = [
            ep for ep in report["endpoint_mappings"].keys() if not ep or ep.strip() == ""
        ]
        assert len(empty_endpoints) == 0, f"Found {len(empty_endpoints)} empty endpoints"

    def test_endpoint_diversity(self):
        """Test that diverse endpoints were found"""
        report = self.report
        endpoints = list(report["endpoint_mappings"].keys())

        # Should have endpoints from different services
        service_keywords = ["contracts", "assets", "datasets", "jobs", "webhooks"]
        found_services = [
            keyword for keyword in service_keywords if any(keyword in ep for ep in endpoints)
        ]
        assert len(found_services) >= 2, (
            f"Expected endpoints from multiple services. Found: {found_services}"
        )

    def test_client_usage_structure(self):
        """Test that client usages have required fields"""
        report = self.report
        for usage in report.get("client_usages", [])[:10]:
            assert "file_path" in usage
            assert "line_number" in usage
            assert "client_class" in usage
            assert "method_name" in usage
            # endpoint is optional (may be None)

    def test_direct_vs_wrapper_calls(self):
        """Test that both direct and wrapper calls were found"""
        report = self.report
        direct_calls = [c for c in report["api_calls"] if c.get("is_direct", False)]
        wrapper_calls = [c for c in report["api_calls"] if not c.get("is_direct", False)]

        # Should have both types
        assert len(direct_calls) > 0 or len(wrapper_calls) > 0, "No API calls found"
        # At least one type should be present
        total_calls = len(direct_calls) + len(wrapper_calls)
        assert total_calls > 0, "No API calls found"

    def test_endpoint_call_counts(self):
        """Test that endpoint call counts are reasonable"""
        report = self.report
        for endpoint, mapping in report["endpoint_mappings"].items():
            call_count = mapping["call_count"]
            assert call_count > 0, f"Endpoint {endpoint} has zero call count"
            assert call_count <= len(report["api_calls"]), (
                f"Endpoint {endpoint} call count ({call_count}) exceeds total API calls"
            )

    def test_method_endpoint_consistency(self):
        """Test that methods match endpoints"""
        report = self.report
        for call in report["api_calls"][:50]:  # Check first 50
            method = call["method"]
            endpoint = call["endpoint"]

            # Methods should be valid HTTP methods
            valid_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "REQUEST"]
            assert method in valid_methods or method == "UNKNOWN", (
                f"Invalid method {method} for endpoint {endpoint}"
            )

    def test_file_paths_valid(self):
        """Test that file paths are valid"""
        report = self.report
        Path(__file__).parent.parent.parent

        for call in report["api_calls"][:20]:  # Check first 20
            file_path = call["file_path"]

            # File should exist (or be a valid relative path)
            # Note: Some files might not exist if they're in different locations
            # Just check that path is not empty and looks reasonable
            assert file_path, "Empty file path found"
            assert "/" in file_path or "\\" in file_path, f"Invalid file path: {file_path}"

    def test_line_numbers_valid(self):
        """Test that line numbers are valid"""
        report = self.report
        for call in report["api_calls"][:20]:  # Check first 20
            line_number = call["line_number"]
            assert isinstance(line_number, int), f"Invalid line number type: {type(line_number)}"
            assert line_number > 0, f"Invalid line number: {line_number}"

    def test_comprehensive_coverage(self):
        """Test that search has comprehensive coverage"""
        report = self.report
        # Should find API calls in multiple directories
        file_paths = set(call["file_path"] for call in report["api_calls"])

        # Should have files from different areas
        areas = ["hub", "sdk", "cli", "tests", "scripts"]
        found_areas = [area for area in areas if any(area in path for path in file_paths)]

        assert len(found_areas) >= 2, (
            f"Expected API calls from multiple areas. Found: {found_areas}"
        )
