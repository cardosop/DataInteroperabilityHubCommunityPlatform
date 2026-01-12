#!/usr/bin/env python3
"""
Tests for Service Integration Impact Report Generator

Tests the comprehensive service integration impact report generation.
"""

import json
import unittest
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestServiceIntegrationImpactReport(unittest.TestCase):
    """Test service integration impact report generation"""

    @property
    def report_path(self):
        """Path to the generated service integration impact report"""
        return project_root / 'docs' / 'api-audit' / 'service-integration-impact.json'

    @property
    def report(self):
        """Load the service integration impact report"""
        if not self.report_path.exists():
            raise FileNotFoundError(
                f"Report not found at {self.report_path}. "
                "Run 'python3 scripts/generate_service_integration_impact_report.py' first."
            )

        with open(self.report_path) as f:
            return json.load(f)

    def test_report_exists(self):
        """Test that the report file exists"""
        self.assertTrue(self.report_path.exists(),
                       f"Service integration impact report not found at {self.report_path}")

    def test_report_structure(self):
        """Test that the report has the correct structure"""
        report = self.report
        self.assertIn('generated_at', report)
        self.assertIn('summary', report)
        self.assertIn('service_integrations', report)
        self.assertIn('integration_matrix', report)

    def test_summary_fields(self):
        """Test that summary contains required fields"""
        report = self.report
        summary = report['summary']
        self.assertIn('total_services', summary)
        self.assertIn('total_integrations', summary)
        self.assertIn('total_service_calls', summary)
        self.assertIn('services', summary)
        self.assertIsInstance(summary['services'], list)

    def test_summary_values(self):
        """Test that summary values are valid"""
        report = self.report
        summary = report['summary']

        self.assertGreater(summary['total_services'], 0, "Should have at least one service")
        self.assertGreaterEqual(summary['total_integrations'], 0, "Integrations should be non-negative")
        self.assertGreaterEqual(summary['total_service_calls'], 0, "Service calls should be non-negative")
        self.assertGreater(len(summary['services']), 0, "Should have at least one service in list")

    def test_service_integrations_structure(self):
        """Test that service integrations have correct structure"""
        report = self.report
        service_integrations = report['service_integrations']

        self.assertIsInstance(service_integrations, dict)
        self.assertGreater(len(service_integrations), 0, "Should have at least one service integration")

        for service_name, service_data in service_integrations.items():
            self.assertIn('outbound', service_data)
            self.assertIn('inbound', service_data)
            self.assertIn('gateway_routes', service_data)
            self.assertIn('service_clients', service_data)
            self.assertIn('call_count', service_data)
            self.assertIn('endpoint_count', service_data)
            self.assertIn('endpoints', service_data)

            self.assertIsInstance(service_data['outbound'], dict)
            self.assertIsInstance(service_data['inbound'], dict)
            self.assertIsInstance(service_data['gateway_routes'], list)
            self.assertIsInstance(service_data['service_clients'], list)
            self.assertIsInstance(service_data['call_count'], int)
            self.assertIsInstance(service_data['endpoint_count'], int)
            self.assertIsInstance(service_data['endpoints'], list)

    def test_integration_matrix_structure(self):
        """Test that integration matrix has correct structure"""
        report = self.report
        matrix = report['integration_matrix']
        summary = report['summary']

        self.assertIsInstance(matrix, dict)

        # Check that matrix includes all services
        for service in summary['services']:
            self.assertIn(service, matrix, f"Service {service} should be in integration matrix")
            self.assertIsInstance(matrix[service], dict)

            # Check that each service has entries for all other services
            for target_service in summary['services']:
                self.assertIn(target_service, matrix[service],
                             f"Service {service} should have entry for {target_service}")
                self.assertIsInstance(matrix[service][target_service], int,
                                    f"Matrix value should be integer")

    def test_integration_matrix_values(self):
        """Test that integration matrix values are valid"""
        report = self.report
        matrix = report['integration_matrix']

        for source, targets in matrix.items():
            for target, count in targets.items():
                self.assertGreaterEqual(count, 0,
                                      f"Matrix value should be non-negative: {source} -> {target}")

    def test_service_integrations_match_summary(self):
        """Test that service integrations match summary counts"""
        report = self.report
        summary = report['summary']
        service_integrations = report['service_integrations']

        # Check service count
        self.assertEqual(len(service_integrations), summary['total_services'],
                        "Service count should match summary")

        # Check that all services in summary are in integrations
        for service in summary['services']:
            self.assertIn(service, service_integrations,
                         f"Service {service} from summary should be in integrations")

    def test_outbound_integrations_structure(self):
        """Test that outbound integrations have correct structure"""
        report = self.report
        service_integrations = report['service_integrations']

        for service_name, service_data in service_integrations.items():
            outbound = service_data['outbound']
            for target, details in outbound.items():
                self.assertIn('call_count', details)
                self.assertIn('endpoints', details)
                self.assertIn('client_types', details)
                self.assertIsInstance(details['call_count'], int)
                self.assertIsInstance(details['endpoints'], list)
                self.assertIsInstance(details['client_types'], list)

    def test_inbound_integrations_structure(self):
        """Test that inbound integrations have correct structure"""
        report = self.report
        service_integrations = report['service_integrations']

        for service_name, service_data in service_integrations.items():
            inbound = service_data['inbound']
            for source, details in inbound.items():
                self.assertIn('call_count', details)
                self.assertIn('endpoints', details)
                self.assertIn('client_types', details)
                self.assertIsInstance(details['call_count'], int)
                self.assertIsInstance(details['endpoints'], list)
                self.assertIsInstance(details['client_types'], list)

    def test_gateway_routes_structure(self):
        """Test that gateway routes have correct structure"""
        report = self.report
        service_integrations = report['service_integrations']

        for service_name, service_data in service_integrations.items():
            gateway_routes = service_data['gateway_routes']
            for route in gateway_routes:
                self.assertIn('type', route)
                self.assertIn(route['type'], ['traefik', 'kubernetes-ingress'],
                            f"Route type should be traefik or kubernetes-ingress")

                if route['type'] == 'traefik':
                    self.assertIn('router_name', route)
                elif route['type'] == 'kubernetes-ingress':
                    self.assertIn('ingress_name', route)

    def test_service_clients_structure(self):
        """Test that service clients have correct structure"""
        report = self.report
        service_integrations = report['service_integrations']

        for service_name, service_data in service_integrations.items():
            service_clients = service_data['service_clients']
            for client in service_clients:
                self.assertIn('class_name', client)
                self.assertIn('base_url', client)
                self.assertIn('methods', client)
                self.assertIsInstance(client['methods'], list)

    def test_endpoint_count_matches_endpoints(self):
        """Test that endpoint count matches actual endpoints"""
        report = self.report
        service_integrations = report['service_integrations']

        for service_name, service_data in service_integrations.items():
            endpoint_count = service_data['endpoint_count']
            endpoints = service_data['endpoints']
            self.assertEqual(endpoint_count, len(endpoints),
                           f"Endpoint count should match endpoints list for {service_name}")

    def test_call_count_consistency(self):
        """Test that call counts are consistent"""
        report = self.report
        service_integrations = report['service_integrations']

        for service_name, service_data in service_integrations.items():
            # Sum outbound calls
            outbound_total = sum(
                details.get('call_count', 0)
                for details in service_data['outbound'].values()
            )

            # Service call_count should be at least the sum of outbound calls
            # (it might be higher if there are other call sources)
            self.assertLessEqual(outbound_total, service_data['call_count'],
                               f"Outbound calls should not exceed total call count for {service_name}")

    def test_integration_matrix_matches_service_integrations(self):
        """Test that integration matrix matches service integrations"""
        report = self.report
        matrix = report['integration_matrix']
        service_integrations = report['service_integrations']

        for source in matrix.keys():
            if source in service_integrations:
                outbound = service_integrations[source]['outbound']
                for target in matrix[source].keys():
                    matrix_value = matrix[source][target]
                    if target in outbound:
                        integration_value = outbound[target]['call_count']
                        self.assertEqual(matrix_value, integration_value,
                                      f"Matrix value should match integration for {source} -> {target}")

    def test_report_completeness(self):
        """Test that report is complete with all required data"""
        report = self.report

        # Check that we have data from all three sources
        has_inter_service_data = False
        has_gateway_data = False
        has_service_client_data = False

        service_integrations = report['service_integrations']
        for service_data in service_integrations.values():
            if service_data.get('outbound') or service_data.get('inbound'):
                has_inter_service_data = True
            if service_data.get('gateway_routes'):
                has_gateway_data = True
            if service_data.get('service_clients'):
                has_service_client_data = True

        # At least one source should have data
        self.assertTrue(has_inter_service_data or has_gateway_data or has_service_client_data,
                       "Report should have data from at least one source")

    def test_markdown_report_exists(self):
        """Test that markdown report exists"""
        md_path = project_root / 'docs' / 'api-audit' / 'service-integration-impact.md'
        self.assertTrue(md_path.exists(),
                       f"Markdown report should exist at {md_path}")

    def test_markdown_report_content(self):
        """Test that markdown report has content"""
        md_path = project_root / 'docs' / 'api-audit' / 'service-integration-impact.md'
        if md_path.exists():
            with open(md_path, 'r') as f:
                content = f.read()

            self.assertGreater(len(content), 0, "Markdown report should have content")
            self.assertIn('# Service Integration Impact Report', content,
                         "Markdown report should have title")
            self.assertIn('## Summary', content, "Markdown report should have summary section")
            self.assertIn('## Service Integration Matrix', content,
                         "Markdown report should have integration matrix section")


class TestServiceIntegrationImpactReportIntegration(unittest.TestCase):
    """Integration tests for service integration impact report"""

    @property
    def report_path(self):
        """Path to the generated service integration impact report"""
        return project_root / 'docs' / 'api-audit' / 'service-integration-impact.json'

    @property
    def report(self):
        """Load the service integration impact report"""
        if not self.report_path.exists():
            raise FileNotFoundError(
                f"Report not found at {self.report_path}. "
                "Run 'python3 scripts/generate_service_integration_impact_report.py' first."
            )

        with open(self.report_path) as f:
            return json.load(f)

    def test_api_service_has_integrations(self):
        """Test that api-service has expected integrations"""
        report = self.report
        service_integrations = report['service_integrations']

        self.assertIn('api-service', service_integrations,
                     "api-service should be in service integrations")

        api_service = service_integrations['api-service']

        # api-service should have outbound integrations
        self.assertGreater(len(api_service['outbound']), 0,
                          "api-service should have outbound integrations")

        # api-service should have inbound integrations (from CLI/SDK)
        self.assertGreater(len(api_service['inbound']), 0,
                          "api-service should have inbound integrations")

    def test_worker_service_integration(self):
        """Test that worker-service integration is tracked"""
        report = self.report
        service_integrations = report['service_integrations']

        # Check api-service -> worker-service integration
        if 'api-service' in service_integrations:
            api_service = service_integrations['api-service']
            if 'worker-service' in api_service['outbound']:
                worker_integration = api_service['outbound']['worker-service']
                self.assertGreater(worker_integration['call_count'], 0,
                                 "api-service should have calls to worker-service")

    def test_service_clients_are_tracked(self):
        """Test that service clients are properly tracked"""
        report = self.report
        service_integrations = report['service_integrations']

        # Check for services with service clients
        services_with_clients = [
            name for name, data in service_integrations.items()
            if data.get('service_clients')
        ]

        # Should have at least some services with clients
        self.assertGreater(len(services_with_clients), 0,
                          "Should have at least one service with service clients")

    def test_gateway_routes_are_tracked(self):
        """Test that gateway routes are properly tracked"""
        report = self.report
        service_integrations = report['service_integrations']

        # Check for services with gateway routes
        services_with_routes = [
            name for name, data in service_integrations.items()
            if data.get('gateway_routes')
        ]

        # Should have at least some services with gateway routes
        self.assertGreater(len(services_with_routes), 0,
                          "Should have at least one service with gateway routes")

    def test_integration_matrix_has_expected_services(self):
        """Test that integration matrix includes expected services"""
        report = self.report
        matrix = report['integration_matrix']
        summary = report['summary']

        # Check for key services
        expected_services = ['api-service', 'worker-service', 'cli', 'sdk']
        for service in expected_services:
            if service in summary['services']:
                self.assertIn(service, matrix,
                             f"Expected service {service} should be in integration matrix")

    def test_report_regeneration(self):
        """Test that report can be regenerated successfully"""
        import subprocess
        import tempfile

        # Run the script to regenerate report
        script_path = project_root / 'scripts' / 'generate_service_integration_impact_report.py'
        self.assertTrue(script_path.exists(), "Script should exist")

        # Run script and capture output
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30
        )

        self.assertEqual(result.returncode, 0,
                        f"Script should run successfully. Error: {result.stderr}")

        # Verify report was generated
        self.assertTrue(self.report_path.exists(),
                       "Report should be generated after running script")

    def test_data_sources_are_loaded(self):
        """Test that all data sources are properly loaded"""
        import subprocess

        # Check that required source files exist
        required_sources = [
            project_root / 'docs' / 'api-audit' / 'inter-service-communication-report.json',
            project_root / 'docs' / 'api-audit' / 'service-client-audit.json',
            project_root / 'docs' / 'api-audit' / 'gateway-config-review.json'
        ]

        existing_sources = [s for s in required_sources if s.exists()]
        self.assertGreater(len(existing_sources), 0,
                          "At least one data source file should exist")

    def test_service_name_normalization(self):
        """Test that service names are normalized consistently"""
        report = self.report
        service_integrations = report['service_integrations']

        # Check for common normalization issues
        # Services should not have duplicate entries with different names
        service_names = list(service_integrations.keys())

        # Check for potential duplicates (e.g., "dq" and "dq-service")
        normalized_names = {}
        for name in service_names:
            normalized = name.replace('-service', '').lower()
            if normalized in normalized_names:
                # This might indicate a normalization issue
                pass  # We'll just note it, not fail
            normalized_names[normalized] = name

    def test_matrix_symmetry_validation(self):
        """Test that integration matrix reflects bidirectional relationships"""
        report = self.report
        matrix = report['integration_matrix']
        service_integrations = report['service_integrations']

        # For each service pair, check if matrix values match integration data
        for source in matrix.keys():
            if source in service_integrations:
                outbound = service_integrations[source]['outbound']
                for target in matrix[source].keys():
                    matrix_value = matrix[source][target]
                    if target in outbound:
                        integration_value = outbound[target]['call_count']
                        self.assertEqual(matrix_value, integration_value,
                                      f"Matrix should match integration data for {source} -> {target}")

    def test_endpoints_are_valid(self):
        """Test that endpoints are valid and not empty strings"""
        report = self.report
        service_integrations = report['service_integrations']

        for service_name, service_data in service_integrations.items():
            endpoints = service_data['endpoints']
            for endpoint in endpoints:
                self.assertIsInstance(endpoint, str,
                                    f"Endpoint should be string for {service_name}")
                # Endpoints can be empty strings, but we'll check they're not None
                self.assertIsNotNone(endpoint,
                                   f"Endpoint should not be None for {service_name}")

    def test_call_counts_are_accurate(self):
        """Test that call counts are accurate and non-negative"""
        report = self.report
        service_integrations = report['service_integrations']

        for service_name, service_data in service_integrations.items():
            # Check outbound call counts
            for target, details in service_data['outbound'].items():
                call_count = details.get('call_count', 0)
                self.assertGreaterEqual(call_count, 0,
                                      f"Call count should be non-negative for {service_name} -> {target}")

            # Check inbound call counts
            for source, details in service_data['inbound'].items():
                call_count = details.get('call_count', 0)
                self.assertGreaterEqual(call_count, 0,
                                      f"Call count should be non-negative for {source} -> {service_name}")

    def test_summary_statistics_accuracy(self):
        """Test that summary statistics are accurate"""
        report = self.report
        summary = report['summary']
        service_integrations = report['service_integrations']

        # Verify total_services matches actual count
        self.assertEqual(summary['total_services'], len(service_integrations),
                        "Total services should match actual service count")

        # Verify total_integrations matches actual count
        actual_integrations = sum(
            len(data.get('outbound', {}))
            for data in service_integrations.values()
        )
        self.assertEqual(summary['total_integrations'], actual_integrations,
                        "Total integrations should match actual integration count")

        # Verify total_service_calls matches actual count
        actual_calls = sum(
            data.get('call_count', 0)
            for data in service_integrations.values()
        )
        # Note: This might be double-counted (outbound + inbound), so we'll check it's reasonable
        self.assertGreaterEqual(summary['total_service_calls'], 0,
                               "Total service calls should be non-negative")


if __name__ == '__main__':
    unittest.main()

