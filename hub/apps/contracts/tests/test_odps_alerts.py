"""
ODPS Alerts Configuration Tests (Task 6.2.3)

Tests validate that ODPS alert rules are properly configured and can detect
various failure conditions and performance issues.

All tests use real implementations (no mocks/stubs) and follow engineering best practices.
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, List
from django.test import TestCase
import structlog

logger = structlog.get_logger(__name__)


class ODPSAlertsConfigurationTest(TestCase):
    """Test ODPS alert configuration file structure and validity."""

    def setUp(self):
        """Set up test fixtures."""
        self.alerts_file = Path(__file__).parent.parent.parent.parent.parent / "monitoring" / "prometheus" / "alerts" / "odps-alerts.yml"
        self.assertTrue(self.alerts_file.exists(), f"Alert configuration file not found: {self.alerts_file}")

    def test_alerts_file_exists(self):
        """Test that ODPS alerts configuration file exists."""
        self.assertTrue(self.alerts_file.exists(), "ODPS alerts configuration file should exist")

    def test_alerts_file_is_valid_yaml(self):
        """Test that alerts file is valid YAML."""
        try:
            with open(self.alerts_file, 'r') as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.fail(f"ODPS alerts file is not valid YAML: {e}")

    def test_alerts_file_has_odps_group(self):
        """Test that alerts file contains odps_alerts group."""
        with open(self.alerts_file, 'r') as f:
            config = yaml.safe_load(f)

        self.assertIn('groups', config, "Alerts file should have 'groups' key")
        self.assertIsInstance(config['groups'], list, "Groups should be a list")

        # Find odps_alerts group
        odps_group = None
        for group in config['groups']:
            if group.get('name') == 'odps_alerts':
                odps_group = group
                break

        self.assertIsNotNone(odps_group, "Should have 'odps_alerts' group")
        self.assertEqual(odps_group['name'], 'odps_alerts')

    def test_all_required_alerts_are_defined(self):
        """Test that all required ODPS alerts are defined."""
        with open(self.alerts_file, 'r') as f:
            config = yaml.safe_load(f)

        odps_group = None
        for group in config['groups']:
            if group.get('name') == 'odps_alerts':
                odps_group = group
                break

        self.assertIsNotNone(odps_group, "Should have 'odps_alerts' group")

        rules = odps_group.get('rules', [])
        alert_names = [rule.get('alert') for rule in rules]

        required_alerts = [
            'ODPSNormalizationFailureRate',
            'ODPSRefResolutionErrorRate',
            'ODPSExternalFetchFailureRate',
            'ODPSExcessiveRateLimitViolations',
            'ODPSRefResolutionPerformanceDegradationInternal',
            'ODPSRefResolutionPerformanceDegradationLocal',
            'ODPSRefResolutionPerformanceDegradationExternal',
            'ODPSLowCacheHitRate',
            'ODPSExportFailureRate',
            'ODPSLinkingFailureRate',
            'ODPSSemanticMappingFailureRate',
        ]

        for required_alert in required_alerts:
            self.assertIn(
                required_alert,
                alert_names,
                f"Required alert '{required_alert}' is missing from configuration"
            )

    def test_alert_structure_is_valid(self):
        """Test that all alerts have required structure (expr, for, labels, annotations)."""
        with open(self.alerts_file, 'r') as f:
            config = yaml.safe_load(f)

        odps_group = None
        for group in config['groups']:
            if group.get('name') == 'odps_alerts':
                odps_group = group
                break

        rules = odps_group.get('rules', [])

        for rule in rules:
            alert_name = rule.get('alert', 'unknown')

            # Check required fields
            self.assertIn('expr', rule, f"Alert '{alert_name}' must have 'expr' field")
            self.assertIn('for', rule, f"Alert '{alert_name}' must have 'for' field")
            self.assertIn('labels', rule, f"Alert '{alert_name}' must have 'labels' field")
            self.assertIn('annotations', rule, f"Alert '{alert_name}' must have 'annotations' field")

            # Check labels structure
            labels = rule['labels']
            self.assertIn('severity', labels, f"Alert '{alert_name}' labels must have 'severity'")
            self.assertIn('component', labels, f"Alert '{alert_name}' labels must have 'component'")
            self.assertEqual(labels['component'], 'odps', f"Alert '{alert_name}' component should be 'odps'")

            # Check annotations structure
            annotations = rule['annotations']
            self.assertIn('summary', annotations, f"Alert '{alert_name}' annotations must have 'summary'")
            self.assertIn('description', annotations, f"Alert '{alert_name}' annotations must have 'description'")

    def test_normalization_failure_alert_configuration(self):
        """Test ODPS normalization failure alert configuration."""
        with open(self.alerts_file, 'r') as f:
            config = yaml.safe_load(f)

        odps_group = None
        for group in config['groups']:
            if group.get('name') == 'odps_alerts':
                odps_group = group
                break

        rules = odps_group.get('rules', [])
        alert = None
        for rule in rules:
            if rule.get('alert') == 'ODPSNormalizationFailureRate':
                alert = rule
                break

        self.assertIsNotNone(alert, "ODPSNormalizationFailureRate alert should exist")
        self.assertIn('odps_normalization_total', alert['expr'], "Alert should reference odps_normalization_total metric")
        self.assertIn('status=~"failed|error"', alert['expr'], "Alert should filter for failed/error status")
        self.assertEqual(alert['labels']['severity'], 'warning', "Alert severity should be warning")
        self.assertIn('0.05', alert['expr'], "Alert threshold should be 5% (0.05)")

    def test_ref_resolution_error_alert_configuration(self):
        """Test ODPS $ref resolution error alert configuration."""
        with open(self.alerts_file, 'r') as f:
            config = yaml.safe_load(f)

        odps_group = None
        for group in config['groups']:
            if group.get('name') == 'odps_alerts':
                odps_group = group
                break

        rules = odps_group.get('rules', [])
        alert = None
        for rule in rules:
            if rule.get('alert') == 'ODPSRefResolutionErrorRate':
                alert = rule
                break

        self.assertIsNotNone(alert, "ODPSRefResolutionErrorRate alert should exist")
        self.assertIn('odps_ref_resolution_total', alert['expr'], "Alert should reference odps_ref_resolution_total metric")
        self.assertIn('status="failure"', alert['expr'], "Alert should filter for failure status")
        self.assertEqual(alert['labels']['severity'], 'warning', "Alert severity should be warning")
        self.assertIn('0.10', alert['expr'], "Alert threshold should be 10% (0.10)")

    def test_external_fetch_failure_alert_configuration(self):
        """Test ODPS external fetch failure alert configuration."""
        with open(self.alerts_file, 'r') as f:
            config = yaml.safe_load(f)

        odps_group = None
        for group in config['groups']:
            if group.get('name') == 'odps_alerts':
                odps_group = group
                break

        rules = odps_group.get('rules', [])
        alert = None
        for rule in rules:
            if rule.get('alert') == 'ODPSExternalFetchFailureRate':
                alert = rule
                break

        self.assertIsNotNone(alert, "ODPSExternalFetchFailureRate alert should exist")
        self.assertIn('odps_external_fetch_failures_total', alert['expr'], "Alert should reference odps_external_fetch_failures_total metric")
        self.assertIn('odps_ref_resolution_total{ref_type="external"}', alert['expr'], "Alert should reference external ref resolution metric")
        self.assertEqual(alert['labels']['severity'], 'warning', "Alert severity should be warning")
        self.assertIn('0.20', alert['expr'], "Alert threshold should be 20% (0.20)")

    def test_rate_limit_violations_alert_configuration(self):
        """Test ODPS excessive rate limit violations alert configuration."""
        with open(self.alerts_file, 'r') as f:
            config = yaml.safe_load(f)

        odps_group = None
        for group in config['groups']:
            if group.get('name') == 'odps_alerts':
                odps_group = group
                break

        rules = odps_group.get('rules', [])
        alert = None
        for rule in rules:
            if rule.get('alert') == 'ODPSExcessiveRateLimitViolations':
                alert = rule
                break

        self.assertIsNotNone(alert, "ODPSExcessiveRateLimitViolations alert should exist")
        self.assertIn('odps_rate_limit_violations_total', alert['expr'], "Alert should reference odps_rate_limit_violations_total metric")
        self.assertIn('[1h]', alert['expr'], "Alert should use 1 hour rate window")
        self.assertEqual(alert['labels']['severity'], 'critical', "Alert severity should be critical")
        self.assertIn('> 50', alert['expr'], "Alert threshold should be 50 violations/hour")

    def test_performance_degradation_alerts_configuration(self):
        """Test ODPS performance degradation alerts configuration."""
        with open(self.alerts_file, 'r') as f:
            config = yaml.safe_load(f)

        odps_group = None
        for group in config['groups']:
            if group.get('name') == 'odps_alerts':
                odps_group = group
                break

        rules = odps_group.get('rules', [])

        # Check internal ref performance alert
        internal_alert = None
        for rule in rules:
            if rule.get('alert') == 'ODPSRefResolutionPerformanceDegradationInternal':
                internal_alert = rule
                break

        self.assertIsNotNone(internal_alert, "ODPSRefResolutionPerformanceDegradationInternal alert should exist")
        self.assertIn('odps_ref_resolution_duration_seconds_bucket{ref_type="internal"}', internal_alert['expr'],
                     "Alert should reference internal ref duration histogram")
        self.assertIn('histogram_quantile(0.95', internal_alert['expr'], "Alert should use P95 percentile")
        self.assertIn('> 0.020', internal_alert['expr'], "Alert threshold should be 20ms (0.020s)")

        # Check local ref performance alert
        local_alert = None
        for rule in rules:
            if rule.get('alert') == 'ODPSRefResolutionPerformanceDegradationLocal':
                local_alert = rule
                break

        self.assertIsNotNone(local_alert, "ODPSRefResolutionPerformanceDegradationLocal alert should exist")
        self.assertIn('odps_ref_resolution_duration_seconds_bucket{ref_type="local"}', local_alert['expr'],
                     "Alert should reference local ref duration histogram")
        self.assertIn('> 0.100', local_alert['expr'], "Alert threshold should be 100ms (0.100s)")

        # Check external ref performance alert
        external_alert = None
        for rule in rules:
            if rule.get('alert') == 'ODPSRefResolutionPerformanceDegradationExternal':
                external_alert = rule
                break

        self.assertIsNotNone(external_alert, "ODPSRefResolutionPerformanceDegradationExternal alert should exist")
        self.assertIn('odps_ref_resolution_duration_seconds_bucket{ref_type="external"}', external_alert['expr'],
                     "Alert should reference external ref duration histogram")
        self.assertIn('> 10.0', external_alert['expr'], "Alert threshold should be 10s (2x target of 5s)")

    def test_cache_hit_rate_alert_configuration(self):
        """Test ODPS low cache hit rate alert configuration."""
        with open(self.alerts_file, 'r') as f:
            config = yaml.safe_load(f)

        odps_group = None
        for group in config['groups']:
            if group.get('name') == 'odps_alerts':
                odps_group = group
                break

        rules = odps_group.get('rules', [])
        alert = None
        for rule in rules:
            if rule.get('alert') == 'ODPSLowCacheHitRate':
                alert = rule
                break

        self.assertIsNotNone(alert, "ODPSLowCacheHitRate alert should exist")
        self.assertIn('odps_ref_cache_hits_total', alert['expr'], "Alert should reference cache hits metric")
        self.assertIn('odps_ref_cache_misses_total', alert['expr'], "Alert should reference cache misses metric")
        self.assertIn('< 0.50', alert['expr'], "Alert threshold should be 50% (0.50)")
        self.assertIn('> 10', alert['expr'], "Alert should require minimum 10 requests")

    def test_prometheus_config_includes_odps_alerts(self):
        """Test that Prometheus configuration includes ODPS alerts file."""
        prometheus_config_file = Path(__file__).parent.parent.parent.parent.parent / "monitoring" / "prometheus" / "prometheus.yml"
        self.assertTrue(prometheus_config_file.exists(), "Prometheus config file should exist")

        with open(prometheus_config_file, 'r') as f:
            config_content = f.read()

        self.assertIn('alerts/odps-alerts.yml', config_content,
                     "Prometheus config should include odps-alerts.yml in rule_files")

    def test_export_failure_alert_configuration(self):
        """Test ODPS export failure alert configuration (Task 6.6.4)."""
        with open(self.alerts_file, 'r') as f:
            config = yaml.safe_load(f)

        odps_group = None
        for group in config['groups']:
            if group.get('name') == 'odps_alerts':
                odps_group = group
                break

        rules = odps_group.get('rules', [])
        alert = None
        for rule in rules:
            if rule.get('alert') == 'ODPSExportFailureRate':
                alert = rule
                break

        self.assertIsNotNone(alert, "ODPSExportFailureRate alert should exist")
        self.assertIn('odps_export_total', alert['expr'], "Alert should reference odps_export_total metric")
        self.assertIn('status="failure"', alert['expr'], "Alert should filter for failure status")
        self.assertEqual(alert['labels']['severity'], 'warning', "Alert severity should be warning")
        self.assertIn('0.05', alert['expr'], "Alert threshold should be 5% (0.05)")

    def test_linking_failure_alert_configuration(self):
        """Test ODPS linking failure alert configuration (Task 6.6.5)."""
        with open(self.alerts_file, 'r') as f:
            config = yaml.safe_load(f)

        odps_group = None
        for group in config['groups']:
            if group.get('name') == 'odps_alerts':
                odps_group = group
                break

        rules = odps_group.get('rules', [])
        alert = None
        for rule in rules:
            if rule.get('alert') == 'ODPSLinkingFailureRate':
                alert = rule
                break

        self.assertIsNotNone(alert, "ODPSLinkingFailureRate alert should exist")
        self.assertIn('odps_linking_failures_total', alert['expr'], "Alert should reference odps_linking_failures_total metric")
        self.assertIn('odps_linking_total', alert['expr'], "Alert should reference odps_linking_total metric")
        self.assertIn('direction', alert['expr'], "Alert should group by direction")
        self.assertEqual(alert['labels']['severity'], 'warning', "Alert severity should be warning")
        self.assertIn('0.05', alert['expr'], "Alert threshold should be 5% (0.05)")

    def test_semantic_mapping_failure_alert_configuration(self):
        """Test ODPS semantic mapping failure alert configuration (Task 6.6.6)."""
        with open(self.alerts_file, 'r') as f:
            config = yaml.safe_load(f)

        odps_group = None
        for group in config['groups']:
            if group.get('name') == 'odps_alerts':
                odps_group = group
                break

        rules = odps_group.get('rules', [])
        alert = None
        for rule in rules:
            if rule.get('alert') == 'ODPSSemanticMappingFailureRate':
                alert = rule
                break

        self.assertIsNotNone(alert, "ODPSSemanticMappingFailureRate alert should exist")
        self.assertIn('odps_semantic_mapping_total', alert['expr'], "Alert should reference odps_semantic_mapping_total metric")
        self.assertIn('status=~"failure|error"', alert['expr'], "Alert should filter for failure/error status")
        self.assertEqual(alert['labels']['severity'], 'warning', "Alert severity should be warning")
        self.assertEqual(alert['labels']['component'], 'odps', "Alert component should be odps")
        self.assertIn('0.05', alert['expr'], "Alert threshold should be 5% (0.05)")
        self.assertEqual(alert['for'], '5m', "Alert should fire after 5 minutes")
        
        # Verify annotations
        annotations = alert.get('annotations', {})
        self.assertIn('summary', annotations, "Alert should have summary annotation")
        self.assertIn('description', annotations, "Alert should have description annotation")
        self.assertIn('tenant_id', annotations['summary'], "Summary should include tenant_id")
        self.assertIn('threshold: 5%', annotations['description'], "Description should mention 5% threshold")

    def test_alert_for_durations_are_reasonable(self):
        """Test that alert 'for' durations are reasonable (not too short or too long)."""
        with open(self.alerts_file, 'r') as f:
            config = yaml.safe_load(f)

        odps_group = None
        for group in config['groups']:
            if group.get('name') == 'odps_alerts':
                odps_group = group
                break

        rules = odps_group.get('rules', [])

        for rule in rules:
            alert_name = rule.get('alert', 'unknown')
            for_duration = rule.get('for', '')

            # Parse duration (e.g., "5m", "10m", "15m")
            # Convert to minutes for comparison
            if for_duration.endswith('m'):
                minutes = int(for_duration[:-1])
            elif for_duration.endswith('s'):
                minutes = int(for_duration[:-1]) / 60
            elif for_duration.endswith('h'):
                minutes = int(for_duration[:-1]) * 60
            else:
                self.fail(f"Alert '{alert_name}' has invalid 'for' duration format: {for_duration}")

            # Alerts should fire after at least 1 minute but not more than 1 hour
            self.assertGreaterEqual(minutes, 1,
                                   f"Alert '{alert_name}' 'for' duration should be at least 1 minute")
            self.assertLessEqual(minutes, 60,
                                f"Alert '{alert_name}' 'for' duration should be at most 1 hour")

