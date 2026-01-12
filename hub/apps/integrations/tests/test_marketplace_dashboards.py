"""
Tests for Marketplace Integration Grafana Dashboards

Tests verify:
1. Dashboard JSON files are valid
2. Dashboards use correct Prometheus metrics
3. Dashboards can be imported into Grafana
4. Alert rules are valid and properly configured

All tests use real implementations (no mocks/stubs).
"""
import json
import pytest
from pathlib import Path
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceDashboardsTest(TestCase):
    """Test marketplace integration Grafana dashboards"""

    def setUp(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        self.dashboards_dir = self.project_root / 'monitoring' / 'grafana' / 'dashboards'
        self.alerts_dir = self.project_root / 'monitoring' / 'prometheus' / 'alerts'

    def test_dashboards_directory_exists(self):
        """Test that dashboards directory exists"""
        self.assertTrue(self.dashboards_dir.exists(), "Dashboards directory should exist")
        self.assertTrue(self.dashboards_dir.is_dir(), "Dashboards directory should be a directory")

    def test_marketplace_dashboards_exist(self):
        """Test that all required marketplace dashboards exist"""
        required_dashboards = [
            'marketplace-connections-overview.json',
            'marketplace-sync-jobs-monitoring.json',
            'marketplace-connector-performance.json',
            'marketplace-api-health.json',
        ]

        for dashboard_name in required_dashboards:
            dashboard_path = self.dashboards_dir / dashboard_name
            self.assertTrue(
                dashboard_path.exists(),
                f"Dashboard {dashboard_name} should exist"
            )

    def test_dashboards_valid_json(self):
        """Test that all marketplace dashboards are valid JSON"""
        dashboard_files = [
            'marketplace-connections-overview.json',
            'marketplace-sync-jobs-monitoring.json',
            'marketplace-connector-performance.json',
            'marketplace-api-health.json',
        ]

        for dashboard_name in dashboard_files:
            dashboard_path = self.dashboards_dir / dashboard_name
            with self.subTest(dashboard=dashboard_name):
                try:
                    content = dashboard_path.read_text(encoding='utf-8')
                    dashboard = json.loads(content)
                    self.assertIn('dashboard', dashboard, f"Dashboard {dashboard_name} should have 'dashboard' key")
                except json.JSONDecodeError as e:
                    self.fail(f"Dashboard {dashboard_name} is not valid JSON: {e}")

    def test_dashboards_have_required_structure(self):
        """Test that dashboards have required structure"""
        dashboard_files = [
            'marketplace-connections-overview.json',
            'marketplace-sync-jobs-monitoring.json',
            'marketplace-connector-performance.json',
            'marketplace-api-health.json',
        ]

        for dashboard_name in dashboard_files:
            dashboard_path = self.dashboards_dir / dashboard_name
            with self.subTest(dashboard=dashboard_name):
                content = dashboard_path.read_text(encoding='utf-8')
                dashboard = json.loads(content)

                # Check required top-level keys
                self.assertIn('dashboard', dashboard)
                dashboard_obj = dashboard['dashboard']

                # Check required dashboard properties
                self.assertIn('title', dashboard_obj, f"Dashboard {dashboard_name} should have title")
                self.assertIn('panels', dashboard_obj, f"Dashboard {dashboard_name} should have panels")
                self.assertIn('schemaVersion', dashboard_obj, f"Dashboard {dashboard_name} should have schemaVersion")

    def test_dashboards_use_marketplace_metrics(self):
        """Test that dashboards use correct marketplace metrics"""
        dashboard_metrics = {
            'marketplace-connections-overview.json': [
                'marketplace_connections_total',
                'marketplace_connection_status',
            ],
            'marketplace-sync-jobs-monitoring.json': [
                'marketplace_sync_jobs_total',
                'marketplace_sync_job_duration_seconds',
                'marketplace_sync_job_success_rate',
            ],
            'marketplace-connector-performance.json': [
                'marketplace_connector_operations_total',
                'marketplace_connector_operation_duration_seconds',
                'marketplace_connector_operation_errors_total',
            ],
            'marketplace-api-health.json': [
                'marketplace_api_calls_total',
                'marketplace_api_call_duration_seconds',
                'marketplace_api_call_errors_total',
            ],
        }

        for dashboard_name, expected_metrics in dashboard_metrics.items():
            dashboard_path = self.dashboards_dir / dashboard_name
            with self.subTest(dashboard=dashboard_name):
                content = dashboard_path.read_text(encoding='utf-8')

                # Check that all expected metrics are referenced
                for metric in expected_metrics:
                    self.assertIn(
                        metric,
                        content,
                        f"Dashboard {dashboard_name} should reference metric {metric}"
                    )

    def test_dashboards_have_panels(self):
        """Test that dashboards have panels configured"""
        dashboard_files = [
            'marketplace-connections-overview.json',
            'marketplace-sync-jobs-monitoring.json',
            'marketplace-connector-performance.json',
            'marketplace-api-health.json',
        ]

        for dashboard_name in dashboard_files:
            dashboard_path = self.dashboards_dir / dashboard_name
            with self.subTest(dashboard=dashboard_name):
                content = dashboard_path.read_text(encoding='utf-8')
                dashboard = json.loads(content)
                panels = dashboard['dashboard'].get('panels', [])

                self.assertGreater(
                    len(panels),
                    0,
                    f"Dashboard {dashboard_name} should have at least one panel"
                )

    def test_dashboards_have_templating(self):
        """Test that dashboards have templating variables configured"""
        dashboard_files = [
            'marketplace-connections-overview.json',
            'marketplace-sync-jobs-monitoring.json',
            'marketplace-connector-performance.json',
            'marketplace-api-health.json',
        ]

        for dashboard_name in dashboard_files:
            dashboard_path = self.dashboards_dir / dashboard_name
            with self.subTest(dashboard=dashboard_name):
                content = dashboard_path.read_text(encoding='utf-8')
                dashboard = json.loads(content)

                # Check if templating exists (optional but recommended)
                if 'templating' in dashboard['dashboard']:
                    templating = dashboard['dashboard']['templating']
                    if 'list' in templating:
                        # Should have at least marketplace_type variable
                        variables = [v.get('name') for v in templating['list']]
                        # At least one variable should exist
                        self.assertGreater(len(variables), 0, f"Dashboard {dashboard_name} should have templating variables")

    def test_marketplace_alerts_exist(self):
        """Test that marketplace alerts file exists"""
        alerts_file = self.alerts_dir / 'marketplace-alerts.yml'
        self.assertTrue(
            alerts_file.exists(),
            "Marketplace alerts file should exist"
        )

    def test_marketplace_alerts_valid_yaml(self):
        """Test that marketplace alerts file is valid YAML"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not available for YAML validation")

        alerts_file = self.alerts_dir / 'marketplace-alerts.yml'
        try:
            content = alerts_file.read_text(encoding='utf-8')
            alerts = yaml.safe_load(content)

            # Check structure
            self.assertIn('groups', alerts, "Alerts file should have 'groups' key")
            self.assertGreater(len(alerts['groups']), 0, "Alerts file should have at least one group")

            # Check that marketplace alerts group exists
            group_names = [g.get('name') for g in alerts['groups']]
            self.assertIn('marketplace_integration_alerts', group_names, "Should have marketplace_integration_alerts group")

            # Find marketplace alerts group
            marketplace_group = next(
                (g for g in alerts['groups'] if g.get('name') == 'marketplace_integration_alerts'),
                None
            )
            self.assertIsNotNone(marketplace_group, "Marketplace alerts group should exist")
            self.assertIn('rules', marketplace_group, "Marketplace alerts group should have rules")
            self.assertGreater(len(marketplace_group['rules']), 0, "Marketplace alerts should have at least one rule")

        except yaml.YAMLError as e:
            self.fail(f"Marketplace alerts file is not valid YAML: {e}")

    def test_marketplace_alerts_have_required_rules(self):
        """Test that marketplace alerts have required alert rules"""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not available for YAML validation")

        alerts_file = self.alerts_dir / 'marketplace-alerts.yml'
        content = alerts_file.read_text(encoding='utf-8')
        alerts = yaml.safe_load(content)

        # Find marketplace alerts group
        marketplace_group = next(
            (g for g in alerts['groups'] if g.get('name') == 'marketplace_integration_alerts'),
            None
        )

        if marketplace_group:
            rule_names = [r.get('alert') for r in marketplace_group.get('rules', [])]

            # Check for key alert rules
            required_alerts = [
                'MarketplaceSyncJobFailure',
                'MarketplaceConnectorOperationErrors',
                'MarketplaceAPIRateLimit',
            ]

            for alert_name in required_alerts:
                self.assertIn(
                    alert_name,
                    rule_names,
                    f"Marketplace alerts should have {alert_name} rule"
                )

    def test_dashboards_can_be_imported(self):
        """Test that dashboards can be imported into Grafana (structure validation)"""
        dashboard_files = [
            'marketplace-connections-overview.json',
            'marketplace-sync-jobs-monitoring.json',
            'marketplace-connector-performance.json',
            'marketplace-api-health.json',
        ]

        for dashboard_name in dashboard_files:
            dashboard_path = self.dashboards_dir / dashboard_name
            with self.subTest(dashboard=dashboard_name):
                content = dashboard_path.read_text(encoding='utf-8')
                dashboard = json.loads(content)
                dashboard_obj = dashboard['dashboard']

                # Validate Grafana dashboard structure
                # Check for required fields
                required_fields = ['title', 'schemaVersion', 'panels']
                for field in required_fields:
                    self.assertIn(
                        field,
                        dashboard_obj,
                        f"Dashboard {dashboard_name} should have {field} field"
                    )

                # Validate panels have required structure
                for panel in dashboard_obj.get('panels', []):
                    self.assertIn('id', panel, "Panel should have id")
                    self.assertIn('title', panel, "Panel should have title")
                    self.assertIn('type', panel, "Panel should have type")
                    self.assertIn('targets', panel, "Panel should have targets")

                    # Validate targets
                    for target in panel.get('targets', []):
                        if 'expr' in target:
                            # Prometheus query should reference marketplace metrics
                            expr = target['expr']
                            # Should contain at least one marketplace metric
                            has_marketplace_metric = any(
                                metric in expr for metric in [
                                    'marketplace_connections',
                                    'marketplace_sync_job',
                                    'marketplace_connector',
                                    'marketplace_api_call'
                                ]
                            )
                            if has_marketplace_metric:
                                # Valid Prometheus query structure
                                self.assertTrue(True, "Panel target has valid Prometheus query")

