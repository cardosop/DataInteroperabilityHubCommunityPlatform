"""
Tests for infrastructure impact report generator.

Task: 9.6.1.6.5 - Generate infrastructure impact report
"""

import json
import tempfile
from pathlib import Path
from unittest import TestCase

from scripts.generate_infrastructure_impact_report import InfrastructureImpactReporter


class TestInfrastructureImpactReporter(TestCase):
    """Test cases for InfrastructureImpactReporter."""

    def setUp(self):
        """Set up test fixtures."""
        self.project_root = Path(__file__).parent.parent
        self.reporter = InfrastructureImpactReporter(self.project_root)

    def test_reporter_initialization(self):
        """Test that reporter initializes correctly."""
        self.assertIsNotNone(self.reporter.project_root)
        self.assertIsNotNone(self.reporter.docker_compose_file)
        self.assertIsNotNone(self.reporter.k8s_dir)
        self.assertIsNotNone(self.reporter.docs_dir)

    def test_extract_docker_compose_services(self):
        """Test Docker Compose service extraction."""
        services = self.reporter.extract_docker_compose_services()

        # Should have service categories
        self.assertIn("infrastructure", services)
        self.assertIn("application", services)
        self.assertIn("monitoring", services)
        self.assertIn("gateway", services)
        self.assertIn("orchestration", services)
        self.assertIn("total_count", services)

        # Should have some services
        self.assertGreater(services["total_count"], 0)

        # Should have infrastructure services
        self.assertGreater(len(services["infrastructure"]), 0)

    def test_extract_kubernetes_components(self):
        """Test Kubernetes component extraction."""
        components = self.reporter.extract_kubernetes_components()

        # Should have component types
        self.assertIn("services", components)
        self.assertIn("deployments", components)
        self.assertIn("statefulsets", components)
        self.assertIn("configmaps", components)
        self.assertIn("secrets", components)
        self.assertIn("persistent_volume_claims", components)
        self.assertIn("ingresses", components)
        self.assertIn("namespaces", components)
        self.assertIn("network_policies", components)
        self.assertIn("total_count", components)

        # Should have some components
        self.assertGreater(components["total_count"], 0)

    def test_load_review_reports(self):
        """Test loading review reports."""
        reports = self.reporter.load_review_reports()

        # Should have report types
        self.assertIn("cicd", reports)
        self.assertIn("monitoring", reports)
        self.assertIn("rate_limiting", reports)
        self.assertIn("gateway", reports)

    def test_compile_infrastructure_components_list(self):
        """Test compiling infrastructure components list."""
        # First extract components
        self.reporter.extract_docker_compose_services()
        self.reporter.extract_kubernetes_components()
        self.reporter.load_review_reports()

        # Then compile list
        components_list = self.reporter.compile_infrastructure_components_list()

        # Should have component categories
        self.assertIn("infrastructure_services", components_list)
        self.assertIn("application_services", components_list)
        self.assertIn("monitoring_services", components_list)
        self.assertIn("gateway_services", components_list)
        self.assertIn("orchestration_services", components_list)
        self.assertIn("kubernetes_resources", components_list)
        self.assertIn("configuration_references", components_list)

        # Should have some services
        self.assertGreater(len(components_list["infrastructure_services"]), 0)
        self.assertGreater(len(components_list["application_services"]), 0)

    def test_generate_report(self):
        """Test report generation."""
        # Extract components
        self.reporter.extract_docker_compose_services()
        self.reporter.extract_kubernetes_components()
        self.reporter.load_review_reports()

        # Generate report
        report = self.reporter.generate_report()

        # Should have required sections
        self.assertIn("generated_at", report)
        self.assertIn("summary", report)
        self.assertIn("docker_compose", report)
        self.assertIn("kubernetes", report)
        self.assertIn("monitoring", report)
        self.assertIn("gateway", report)
        self.assertIn("rate_limiting", report)
        self.assertIn("cicd", report)
        self.assertIn("components_list", report)

        # Summary should have statistics
        summary = report["summary"]
        self.assertIn("docker_compose_services", summary)
        self.assertIn("kubernetes_components", summary)
        self.assertGreater(summary["docker_compose_services"], 0)

    def test_save_markdown_report(self):
        """Test saving Markdown report."""
        # Extract components
        self.reporter.extract_docker_compose_services()
        self.reporter.extract_kubernetes_components()
        self.reporter.load_review_reports()

        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
            temp_path = Path(f.name)

        try:
            self.reporter.save_markdown_report(temp_path)

            # Verify file exists
            self.assertTrue(temp_path.exists())

            # Verify file content
            content = temp_path.read_text()
            self.assertIn("# Infrastructure Impact Analysis", content)
            self.assertIn("Docker Compose Infrastructure", content)
            self.assertIn("Kubernetes Infrastructure", content)
        finally:
            # Cleanup
            if temp_path.exists():
                temp_path.unlink()

    def test_save_json_report(self):
        """Test saving JSON report."""
        # Extract components
        self.reporter.extract_docker_compose_services()
        self.reporter.extract_kubernetes_components()
        self.reporter.load_review_reports()

        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = Path(f.name)

        try:
            self.reporter.save_json_report(temp_path)

            # Verify file exists
            self.assertTrue(temp_path.exists())

            # Verify file is valid JSON
            with open(temp_path, 'r') as f:
                report = json.load(f)

            self.assertIn("summary", report)
        finally:
            # Cleanup
            if temp_path.exists():
                temp_path.unlink()

    def test_docker_compose_services_structure(self):
        """Test Docker Compose services have proper structure."""
        services = self.reporter.extract_docker_compose_services()

        # Check service structure
        if services.get("infrastructure"):
            first_service = services["infrastructure"][0]
            self.assertIn("name", first_service)
            self.assertIn("image", first_service)
            self.assertIsInstance(first_service.get("ports", []), list)
            self.assertIsInstance(first_service.get("volumes", []), list)

    def test_kubernetes_components_structure(self):
        """Test Kubernetes components have proper structure."""
        components = self.reporter.extract_kubernetes_components()

        # Check component structure
        if components.get("services"):
            first_service = components["services"][0]
            self.assertIn("name", first_service)
            self.assertIn("namespace", first_service)
            self.assertIn("file", first_service)

    def test_report_completeness(self):
        """Test that report is complete."""
        # Extract all components
        self.reporter.extract_docker_compose_services()
        self.reporter.extract_kubernetes_components()
        self.reporter.load_review_reports()

        # Generate report
        report = self.reporter.generate_report()

        # Verify all sections present
        required_sections = [
            "generated_at",
            "summary",
            "docker_compose",
            "kubernetes",
            "monitoring",
            "gateway",
            "rate_limiting",
            "cicd",
            "components_list"
        ]

        for section in required_sections:
            self.assertIn(section, report, f"Report should contain '{section}' section")

        # Verify summary completeness
        summary = report["summary"]
        summary_keys = [
            "docker_compose_services",
            "kubernetes_components",
            "infrastructure_services",
            "application_services",
            "monitoring_services",
            "gateway_services",
            "orchestration_services"
        ]

        for key in summary_keys:
            self.assertIn(key, summary, f"Summary should contain '{key}' key")
            self.assertIsInstance(summary[key], (int, float), f"Summary '{key}' should be numeric")

    def test_components_list_completeness(self):
        """Test that components list is complete."""
        # Extract components
        self.reporter.extract_docker_compose_services()
        self.reporter.extract_kubernetes_components()
        self.reporter.load_review_reports()

        # Compile list
        components_list = self.reporter.compile_infrastructure_components_list()

        # Verify structure
        self.assertIsInstance(components_list["infrastructure_services"], list)
        self.assertIsInstance(components_list["application_services"], list)
        self.assertIsInstance(components_list["monitoring_services"], list)
        self.assertIsInstance(components_list["gateway_services"], list)
        self.assertIsInstance(components_list["orchestration_services"], list)
        self.assertIsInstance(components_list["kubernetes_resources"], dict)
        self.assertIsInstance(components_list["configuration_references"], dict)

    def test_handles_missing_files_gracefully(self):
        """Test that reporter handles missing files gracefully."""
        # Create reporter with non-existent paths
        fake_root = Path("/tmp/nonexistent_infrastructure_test")
        reporter = InfrastructureImpactReporter(fake_root)

        # Should not raise exceptions
        services = reporter.extract_docker_compose_services()
        self.assertIsInstance(services, dict)

        components = reporter.extract_kubernetes_components()
        self.assertIsInstance(components, dict)

        reports = reporter.load_review_reports()
        self.assertIsInstance(reports, dict)

    def test_infrastructure_services_categorization(self):
        """Test that infrastructure services are properly categorized."""
        services = self.reporter.extract_docker_compose_services()

        # Should have infrastructure services
        infrastructure_names = [s["name"] for s in services.get("infrastructure", [])]
        self.assertIn("postgres", infrastructure_names)
        self.assertIn("redis", infrastructure_names)
        self.assertIn("minio", infrastructure_names)

        # Should have monitoring services
        monitoring_names = [s["name"] for s in services.get("monitoring", [])]
        self.assertIn("prometheus", monitoring_names)
        self.assertIn("grafana", monitoring_names)

    def test_kubernetes_resource_counts(self):
        """Test that Kubernetes resource counts are accurate."""
        components = self.reporter.extract_kubernetes_components()

        # Total count should equal sum of individual counts
        total = components["total_count"]
        sum_of_counts = (
            len(components["services"]) +
            len(components["deployments"]) +
            len(components["statefulsets"]) +
            len(components["configmaps"]) +
            len(components["secrets"]) +
            len(components["persistent_volume_claims"]) +
            len(components["ingresses"]) +
            len(components["namespaces"]) +
            len(components["network_policies"])
        )

        self.assertEqual(total, sum_of_counts, "Total count should equal sum of individual counts")

    def test_report_verification_completeness(self):
        """Test that report verification covers all required aspects."""
        # Extract components
        self.reporter.extract_docker_compose_services()
        self.reporter.extract_kubernetes_components()
        self.reporter.load_review_reports()

        # Generate report
        report = self.reporter.generate_report()

        # Verify report has all required data
        self.assertIsNotNone(report.get("generated_at"))
        self.assertIsNotNone(report.get("summary"))

        # Verify Docker Compose data
        docker_compose = report.get("docker_compose", {})
        self.assertGreater(docker_compose.get("total_count", 0), 0)
        self.assertGreater(len(docker_compose.get("infrastructure", [])), 0)
        self.assertGreater(len(docker_compose.get("application", [])), 0)

        # Verify Kubernetes data
        kubernetes = report.get("kubernetes", {})
        self.assertGreater(kubernetes.get("total_count", 0), 0)

        # Verify components list
        components_list = report.get("components_list", {})
        self.assertGreater(len(components_list.get("infrastructure_services", [])), 0)
        self.assertGreater(len(components_list.get("application_services", [])), 0)

    def test_markdown_report_content_validation(self):
        """Test that Markdown report contains all required sections."""
        # Extract components
        self.reporter.extract_docker_compose_services()
        self.reporter.extract_kubernetes_components()
        self.reporter.load_review_reports()

        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
            temp_path = Path(f.name)

        try:
            self.reporter.save_markdown_report(temp_path)

            # Verify file exists and has content
            self.assertTrue(temp_path.exists())
            content = temp_path.read_text()
            self.assertGreater(len(content), 0)

            # Verify required sections
            required_sections = [
                "# Infrastructure Impact Analysis",
                "## Executive Summary",
                "## Docker Compose Infrastructure",
                "## Kubernetes Infrastructure",
                "## Monitoring and Observability",
                "## API Gateway",
                "## Rate Limiting",
                "## CI/CD Infrastructure",
                "## Infrastructure Components List"
            ]

            for section in required_sections:
                self.assertIn(section, content, f"Markdown should contain '{section}' section")
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_json_report_structure_validation(self):
        """Test that JSON report has correct structure."""
        # Extract components
        self.reporter.extract_docker_compose_services()
        self.reporter.extract_kubernetes_components()
        self.reporter.load_review_reports()

        # Generate report
        report = self.reporter.generate_report()

        # Verify structure depth and types
        self.assertIsInstance(report, dict)
        self.assertIsInstance(report.get("summary"), dict)
        self.assertIsInstance(report.get("docker_compose"), dict)
        self.assertIsInstance(report.get("kubernetes"), dict)
        self.assertIsInstance(report.get("components_list"), dict)

        # Verify summary values are numeric
        summary = report["summary"]
        for key, value in summary.items():
            self.assertIsInstance(value, (int, float), f"Summary '{key}' should be numeric, got {type(value)}")

    def test_infrastructure_components_list_accuracy(self):
        """Test that infrastructure components list matches extracted data."""
        # Extract components
        docker_services = self.reporter.extract_docker_compose_services()
        k8s_components = self.reporter.extract_kubernetes_components()
        self.reporter.load_review_reports()

        # Compile list
        components_list = self.reporter.compile_infrastructure_components_list()

        # Verify Docker Compose services match
        self.assertEqual(
            len(components_list["infrastructure_services"]),
            len(docker_services.get("infrastructure", [])),
            "Infrastructure services count should match"
        )

        self.assertEqual(
            len(components_list["application_services"]),
            len(docker_services.get("application", [])),
            "Application services count should match"
        )

        # Verify Kubernetes resources match
        k8s_resources = components_list["kubernetes_resources"]
        self.assertEqual(
            k8s_resources["services"],
            len(k8s_components.get("services", [])),
            "Kubernetes services count should match"
        )

    def test_report_generation_idempotency(self):
        """Test that report generation is idempotent."""
        # Extract components
        self.reporter.extract_docker_compose_services()
        self.reporter.extract_kubernetes_components()
        self.reporter.load_review_reports()

        # Generate report twice
        report1 = self.reporter.generate_report()
        report2 = self.reporter.generate_report()

        # Should have same structure (ignoring generated_at timestamp)
        self.assertEqual(set(report1.keys()), set(report2.keys()))
        self.assertEqual(
            report1["summary"]["docker_compose_services"],
            report2["summary"]["docker_compose_services"]
        )
        self.assertEqual(
            report1["summary"]["kubernetes_components"],
            report2["summary"]["kubernetes_components"]
        )

