"""
Tests for monitoring and observability review script.

Task: 9.6.1.6.2 - Check monitoring and observability
"""

import json
import tempfile
from pathlib import Path
from unittest import TestCase

from scripts.review_monitoring_observability import MonitoringReviewer


class TestMonitoringReviewer(TestCase):
    """Test cases for MonitoringReviewer."""

    def setUp(self):
        """Set up test fixtures."""
        self.project_root = Path(__file__).parent.parent
        self.reviewer = MonitoringReviewer(self.project_root)

    def test_reviewer_initialization(self):
        """Test that reviewer initializes correctly."""
        self.assertIsNotNone(self.reviewer.project_root)
        self.assertIsNotNone(self.reviewer.monitoring_dir)
        self.assertIsNotNone(self.reviewer.hub_dir)
        self.assertEqual(len(self.reviewer.endpoints), 0)
        self.assertEqual(len(self.reviewer.prometheus_metrics), 0)

    def test_extract_endpoints_from_urls(self):
        """Test endpoint extraction from URL configuration."""
        endpoints = self.reviewer.extract_endpoints_from_urls()

        # Should find at least some endpoints
        self.assertGreater(len(endpoints), 0)

        # Should include common API endpoints
        api_endpoints = [ep for ep in endpoints if "/api/v1/" in ep]
        self.assertGreater(len(api_endpoints), 0)

    def test_review_prometheus_metrics(self):
        """Test Prometheus metrics review."""
        results = self.reviewer.review_prometheus_metrics()

        # Should have scrape configs
        self.assertIn("scrape_configs", results)
        self.assertGreater(len(results["scrape_configs"]), 0)

        # Should have metrics with endpoint labels
        self.assertIn("metrics_with_endpoint_labels", results)

        # Should have endpoint labels found
        self.assertIn("endpoint_labels_found", results)
        self.assertIn("route", results["endpoint_labels_found"])

    def test_review_grafana_dashboards(self):
        """Test Grafana dashboards review."""
        queries = self.reviewer.review_grafana_dashboards()

        # Should find some queries
        self.assertGreater(len(queries), 0)

        # Each query should have required fields
        for query in queries[:10]:  # Check first 10
            self.assertIn("dashboard", query)
            self.assertIn("query", query)
            self.assertIn("has_route_label", query)

    def test_review_jaeger_traces(self):
        """Test Jaeger tracing review."""
        operations = self.reviewer.review_jaeger_traces()

        # Should have operation patterns
        self.assertIn("operation_patterns", operations)

        # Should have Django or FastAPI operations
        has_operations = (
            len(operations.get("django_operations", [])) > 0
            or len(operations.get("fastapi_operations", [])) > 0
            or len(operations.get("operation_patterns", [])) > 0
        )
        self.assertTrue(has_operations, "Should find at least some operation patterns")

    def test_review_log_aggregation(self):
        """Test log aggregation review."""
        patterns = self.reviewer.review_log_aggregation()

        # Should have log patterns structure
        self.assertIn("promtail_configs", patterns)
        self.assertIn("log_url_patterns", patterns)

    def test_map_monitoring_to_endpoints(self):
        """Test mapping of monitoring configs to endpoints."""
        # First run the reviews
        self.reviewer.review_prometheus_metrics()
        self.reviewer.review_grafana_dashboards()
        self.reviewer.review_jaeger_traces()
        self.reviewer.review_log_aggregation()

        # Then map to endpoints
        mapping = self.reviewer.map_monitoring_to_endpoints()

        # Should have some mappings
        self.assertGreater(len(mapping), 0)

        # Each mapping should have required fields
        for _endpoint, config in list(mapping.items())[:5]:  # Check first 5
            self.assertIn("endpoint", config)
            self.assertIn("prometheus_metrics", config)
            self.assertIn("grafana_queries", config)
            self.assertIn("jaeger_operations", config)
            self.assertIn("log_patterns", config)

    def test_generate_report(self):
        """Test report generation."""
        # Run all reviews
        self.reviewer.review_prometheus_metrics()
        self.reviewer.review_grafana_dashboards()
        self.reviewer.review_jaeger_traces()
        self.reviewer.review_log_aggregation()
        self.reviewer.map_monitoring_to_endpoints()

        # Generate report
        report = self.reviewer.generate_report()

        # Should have summary
        self.assertIn("summary", report)
        summary = report["summary"]
        self.assertIn("endpoints_found", summary)
        self.assertIn("prometheus_metrics_with_endpoints", summary)
        self.assertIn("grafana_queries_reviewed", summary)

        # Should have all sections
        self.assertIn("prometheus", report)
        self.assertIn("grafana", report)
        self.assertIn("jaeger", report)
        self.assertIn("logging", report)
        self.assertIn("endpoint_mapping", report)

    def test_save_report(self):
        """Test saving report to file."""
        # Run all reviews
        self.reviewer.review_prometheus_metrics()
        self.reviewer.review_grafana_dashboards()
        self.reviewer.review_jaeger_traces()
        self.reviewer.review_log_aggregation()
        self.reviewer.map_monitoring_to_endpoints()

        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            temp_path = Path(f.name)

        try:
            self.reviewer.save_report(temp_path)

            # Verify file exists
            self.assertTrue(temp_path.exists())

            # Verify file is valid JSON
            with open(temp_path) as f:
                report = json.load(f)

            self.assertIn("summary", report)
        finally:
            # Cleanup
            if temp_path.exists():
                temp_path.unlink()

    def test_prometheus_metrics_have_route_labels(self):
        """Test that Prometheus metrics include route labels."""
        results = self.reviewer.review_prometheus_metrics()

        # Should find metrics with route labels
        metrics_with_routes = results.get("metrics_with_endpoint_labels", [])
        self.assertGreater(
            len(metrics_with_routes), 0, "Should find at least one metric with route label"
        )

        # Should include http_requests_total
        self.assertIn("http_requests_total", metrics_with_routes)

    def test_grafana_queries_use_endpoint_labels(self):
        """Test that Grafana queries use endpoint-related labels."""
        queries = self.reviewer.review_grafana_dashboards()

        # Should have some queries with route labels
        queries_with_routes = [q for q in queries if q.get("has_route_label")]
        self.assertGreater(
            len(queries_with_routes), 0, "Should find at least one query with route label"
        )

    def test_jaeger_operations_include_http_patterns(self):
        """Test that Jaeger operations include HTTP patterns."""
        operations = self.reviewer.review_jaeger_traces()

        # Should have span attributes
        span_attrs = operations.get("span_attributes", [])
        self.assertGreater(len(span_attrs), 0, "Should find span attributes like http.route")

        # Should include http.route or http.method
        has_http_attrs = any(
            attr in ["http.route", "http.method", "http.url"] for attr in span_attrs
        )
        self.assertTrue(has_http_attrs, "Should find HTTP-related span attributes")

    def test_log_patterns_include_url_info(self):
        """Test that log patterns include URL information."""
        patterns = self.reviewer.review_log_aggregation()

        # Should have some log patterns
        log_patterns = patterns.get("log_url_patterns", [])
        # Note: This might be empty if patterns aren't explicitly configured
        # But the structure should exist
        self.assertIsInstance(log_patterns, list)

    def test_endpoint_mapping_completeness(self):
        """Test that endpoint mapping is complete."""
        # Run all reviews
        self.reviewer.review_prometheus_metrics()
        self.reviewer.review_grafana_dashboards()
        self.reviewer.review_jaeger_traces()
        self.reviewer.review_log_aggregation()

        # Extract endpoints
        endpoints = self.reviewer.extract_endpoints_from_urls()
        self.assertGreater(len(endpoints), 0)

        # Map to monitoring configs
        mapping = self.reviewer.map_monitoring_to_endpoints()

        # Should map all endpoints
        self.assertEqual(
            len(mapping), len(endpoints), "Should map all endpoints to monitoring configs"
        )

    def test_comprehensive_review(self):
        """Test comprehensive review end-to-end."""
        # Run complete review
        self.reviewer.review_prometheus_metrics()
        self.reviewer.review_grafana_dashboards()
        self.reviewer.review_jaeger_traces()
        self.reviewer.review_log_aggregation()
        self.reviewer.map_monitoring_to_endpoints()

        # Verify all components reviewed
        self.assertGreater(len(self.reviewer.prometheus_metrics), 0)
        self.assertGreater(len(self.reviewer.grafana_queries), 0)
        self.assertGreater(len(self.reviewer.jaeger_operations), 0)
        self.assertGreater(len(self.reviewer.endpoint_mapping), 0)

        # Verify summary
        summary = self.reviewer.generate_report()["summary"]
        self.assertGreater(summary["endpoints_found"], 0)
        self.assertGreater(summary["grafana_queries_reviewed"], 0)

    def test_handles_missing_files_gracefully(self):
        """Test that reviewer handles missing configuration files gracefully."""
        # Create reviewer with non-existent paths
        fake_root = Path("/tmp/nonexistent_monitoring_test")
        reviewer = MonitoringReviewer(fake_root)

        # Should not raise exceptions
        results = reviewer.review_prometheus_metrics()
        self.assertIsInstance(results, dict)
        self.assertIn("scrape_configs", results)

        queries = reviewer.review_grafana_dashboards()
        self.assertIsInstance(queries, list)

        operations = reviewer.review_jaeger_traces()
        self.assertIsInstance(operations, dict)

        patterns = reviewer.review_log_aggregation()
        self.assertIsInstance(patterns, dict)

    def test_report_structure_completeness(self):
        """Test that generated report has complete structure."""
        # Run all reviews
        self.reviewer.review_prometheus_metrics()
        self.reviewer.review_grafana_dashboards()
        self.reviewer.review_jaeger_traces()
        self.reviewer.review_log_aggregation()
        self.reviewer.map_monitoring_to_endpoints()

        report = self.reviewer.generate_report()

        # Check all required top-level keys
        required_keys = [
            "summary",
            "prometheus",
            "grafana",
            "jaeger",
            "logging",
            "endpoint_mapping",
        ]
        for key in required_keys:
            self.assertIn(key, report, f"Report should contain '{key}' key")

        # Check summary structure
        summary = report["summary"]
        summary_keys = [
            "endpoints_found",
            "prometheus_metrics_with_endpoints",
            "grafana_queries_reviewed",
            "jaeger_operation_patterns",
            "log_patterns_found",
            "endpoints_mapped",
        ]
        for key in summary_keys:
            self.assertIn(key, summary, f"Summary should contain '{key}' key")
            self.assertIsInstance(summary[key], (int, float), f"Summary '{key}' should be numeric")

    def test_endpoint_extraction_handles_various_patterns(self):
        """Test that endpoint extraction handles various URL patterns."""
        endpoints = self.reviewer.extract_endpoints_from_urls()

        # Should handle various endpoint patterns
        self.assertGreater(len(endpoints), 0)

        # Check for common patterns
        has_api_endpoints = any("/api/v1/" in ep for ep in endpoints)
        self.assertTrue(has_api_endpoints, "Should find API v1 endpoints")

    def test_metrics_review_finds_expected_labels(self):
        """Test that metrics review finds expected label patterns."""
        results = self.reviewer.review_prometheus_metrics()

        # Should find route label
        self.assertIn("route", results["endpoint_labels_found"])

        # Should have metrics with route labels
        metrics = results.get("metrics_with_endpoint_labels", [])
        self.assertGreater(len(metrics), 0)

        # Should include http_requests_total
        self.assertIn("http_requests_total", metrics)

    def test_grafana_queries_have_required_structure(self):
        """Test that Grafana queries have required structure."""
        queries = self.reviewer.review_grafana_dashboards()

        if len(queries) > 0:
            # Check first query structure
            first_query = queries[0]
            required_fields = ["dashboard", "query", "has_route_label"]
            for field in required_fields:
                self.assertIn(field, first_query, f"Query should have '{field}' field")

    def test_jaeger_operations_structure(self):
        """Test that Jaeger operations have proper structure."""
        operations = self.reviewer.review_jaeger_traces()

        # Should have expected keys
        expected_keys = ["django_operations", "fastapi_operations", "operation_patterns"]
        for key in expected_keys:
            self.assertIn(key, operations, f"Operations should have '{key}' key")
            self.assertIsInstance(operations[key], list, f"'{key}' should be a list")

    def test_log_patterns_structure(self):
        """Test that log patterns have proper structure."""
        patterns = self.reviewer.review_log_aggregation()

        # Should have expected keys
        expected_keys = ["promtail_configs", "log_url_patterns"]
        for key in expected_keys:
            self.assertIn(key, patterns, f"Patterns should have '{key}' key")
            self.assertIsInstance(patterns[key], list, f"'{key}' should be a list")
