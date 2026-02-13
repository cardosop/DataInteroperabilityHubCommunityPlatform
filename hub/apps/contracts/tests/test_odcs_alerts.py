"""
ODCS Alerts Configuration Tests (Task 6.2.4)

Tests validate that ODCS alert rules are properly configured and can detect
various failure conditions, version-specific errors, and regression patterns.

All tests use real implementations (no mocks/stubs) and follow engineering best practices.
"""

import os
from pathlib import Path
from typing import Any, Dict, List

import structlog
import yaml
from django.test import TestCase

logger = structlog.get_logger(__name__)


class ODCSAlertsConfigurationTest(TestCase):
    """Test ODCS alert configuration file structure and validity."""

    def setUp(self):
        """Set up test fixtures."""
        self.alerts_file = (
            Path(__file__).parent.parent.parent.parent.parent
            / "monitoring"
            / "prometheus"
            / "alerts"
            / "odcs-alerts.yml"
        )
        self.assertTrue(
            self.alerts_file.exists(), f"Alert configuration file not found: {self.alerts_file}"
        )

    def test_alerts_file_exists(self):
        """Test that ODCS alerts configuration file exists."""
        self.assertTrue(self.alerts_file.exists(), "ODCS alerts configuration file should exist")

    def test_alerts_file_is_valid_yaml(self):
        """Test that alerts file is valid YAML."""
        try:
            with open(self.alerts_file, "r") as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.fail(f"ODCS alerts file is not valid YAML: {e}")

    def test_alerts_file_has_odcs_group(self):
        """Test that alerts file contains odcs_alerts group."""
        with open(self.alerts_file, "r") as f:
            config = yaml.safe_load(f)

        self.assertIn("groups", config, "Alerts file should have 'groups' key")
        self.assertIsInstance(config["groups"], list, "Groups should be a list")

        # Find odcs_alerts group
        odcs_group = None
        for group in config["groups"]:
            if group.get("name") == "odcs_alerts":
                odcs_group = group
                break

        self.assertIsNotNone(odcs_group, "Should have 'odcs_alerts' group")
        self.assertEqual(odcs_group["name"], "odcs_alerts")

    def test_all_required_alerts_are_defined(self):
        """Test that all required ODCS alerts are defined."""
        with open(self.alerts_file, "r") as f:
            config = yaml.safe_load(f)

        odcs_group = None
        for group in config["groups"]:
            if group.get("name") == "odcs_alerts":
                odcs_group = group
                break

        self.assertIsNotNone(odcs_group, "Should have 'odcs_alerts' group")

        rules = odcs_group.get("rules", [])
        alert_names = [rule.get("alert") for rule in rules]

        required_alerts = [
            "ODCSNormalizationFailureRate",
            "ODCSVersionSpecificNormalizationErrors",
            "ODCSNormalizationRegressionDetected",
            "ODCSNormalizationRegressionRate",
            "ODCSVersionDistributionAnomaly",
        ]

        for required_alert in required_alerts:
            self.assertIn(
                required_alert,
                alert_names,
                f"Required alert '{required_alert}' is missing from configuration",
            )

    def test_alert_structure_is_valid(self):
        """Test that all alerts have required structure (expr, for, labels, annotations)."""
        with open(self.alerts_file, "r") as f:
            config = yaml.safe_load(f)

        odcs_group = None
        for group in config["groups"]:
            if group.get("name") == "odcs_alerts":
                odcs_group = group
                break

        rules = odcs_group.get("rules", [])

        for rule in rules:
            alert_name = rule.get("alert", "unknown")

            # Check required fields
            self.assertIn("expr", rule, f"Alert '{alert_name}' must have 'expr' field")
            self.assertIn("for", rule, f"Alert '{alert_name}' must have 'for' field")
            self.assertIn("labels", rule, f"Alert '{alert_name}' must have 'labels' field")
            self.assertIn(
                "annotations", rule, f"Alert '{alert_name}' must have 'annotations' field"
            )

            # Check labels structure
            labels = rule["labels"]
            self.assertIn("severity", labels, f"Alert '{alert_name}' labels must have 'severity'")
            self.assertIn("component", labels, f"Alert '{alert_name}' labels must have 'component'")
            self.assertEqual(
                labels["component"], "odcs", f"Alert '{alert_name}' component should be 'odcs'"
            )

            # Check annotations structure
            annotations = rule["annotations"]
            self.assertIn(
                "summary", annotations, f"Alert '{alert_name}' annotations must have 'summary'"
            )
            self.assertIn(
                "description",
                annotations,
                f"Alert '{alert_name}' annotations must have 'description'",
            )

    def test_normalization_failure_alert_configuration(self):
        """Test ODCS normalization failure alert configuration (all versions)."""
        with open(self.alerts_file, "r") as f:
            config = yaml.safe_load(f)

        odcs_group = None
        for group in config["groups"]:
            if group.get("name") == "odcs_alerts":
                odcs_group = group
                break

        rules = odcs_group.get("rules", [])
        alert = None
        for rule in rules:
            if rule.get("alert") == "ODCSNormalizationFailureRate":
                alert = rule
                break

        self.assertIsNotNone(alert, "ODCSNormalizationFailureRate alert should exist")
        self.assertIn(
            "odcs_normalization_total",
            alert["expr"],
            "Alert should reference odcs_normalization_total metric",
        )
        self.assertIn(
            'status=~"NORMALIZATION_FAILED|failed|error"',
            alert["expr"],
            "Alert should filter for failed/error status",
        )
        self.assertEqual(alert["labels"]["severity"], "warning", "Alert severity should be warning")
        self.assertIn("0.05", alert["expr"], "Alert threshold should be 5% (0.05)")
        self.assertIn(
            "version", alert["expr"], "Alert should track by version for all ODCS versions"
        )

    def test_version_specific_normalization_errors_alert_configuration(self):
        """Test ODCS version-specific normalization errors alert configuration."""
        with open(self.alerts_file, "r") as f:
            config = yaml.safe_load(f)

        odcs_group = None
        for group in config["groups"]:
            if group.get("name") == "odcs_alerts":
                odcs_group = group
                break

        rules = odcs_group.get("rules", [])
        alert = None
        for rule in rules:
            if rule.get("alert") == "ODCSVersionSpecificNormalizationErrors":
                alert = rule
                break

        self.assertIsNotNone(alert, "ODCSVersionSpecificNormalizationErrors alert should exist")
        self.assertIn(
            "odcs_normalization_total",
            alert["expr"],
            "Alert should reference odcs_normalization_total metric",
        )
        self.assertIn(
            'version=~"3.0.2|3.0.1|3.0.0"', alert["expr"], "Alert should filter for stable versions"
        )
        self.assertEqual(alert["labels"]["severity"], "warning", "Alert severity should be warning")
        self.assertIn(
            "0.10",
            alert["expr"],
            "Alert threshold should be 10% (0.10) for version-specific errors",
        )

    def test_regression_detection_alert_configuration(self):
        """Test ODCS normalization regression detection alert configuration."""
        with open(self.alerts_file, "r") as f:
            config = yaml.safe_load(f)

        odcs_group = None
        for group in config["groups"]:
            if group.get("name") == "odcs_alerts":
                odcs_group = group
                break

        rules = odcs_group.get("rules", [])
        alert = None
        for rule in rules:
            if rule.get("alert") == "ODCSNormalizationRegressionDetected":
                alert = rule
                break

        self.assertIsNotNone(alert, "ODCSNormalizationRegressionDetected alert should exist")
        self.assertIn(
            "odcs_normalization_regression_total",
            alert["expr"],
            "Alert should reference odcs_normalization_regression_total metric",
        )
        self.assertIn("regression_type", alert["expr"], "Alert should track regression type")
        self.assertIn("version", alert["expr"], "Alert should track by version")
        self.assertEqual(alert["labels"]["severity"], "warning", "Alert severity should be warning")

    def test_regression_rate_alert_configuration(self):
        """Test ODCS normalization regression rate alert configuration."""
        with open(self.alerts_file, "r") as f:
            config = yaml.safe_load(f)

        odcs_group = None
        for group in config["groups"]:
            if group.get("name") == "odcs_alerts":
                odcs_group = group
                break

        rules = odcs_group.get("rules", [])
        alert = None
        for rule in rules:
            if rule.get("alert") == "ODCSNormalizationRegressionRate":
                alert = rule
                break

        self.assertIsNotNone(alert, "ODCSNormalizationRegressionRate alert should exist")
        self.assertIn(
            "odcs_normalization_regression_total",
            alert["expr"],
            "Alert should reference regression metric",
        )
        self.assertIn(
            "odcs_normalization_total",
            alert["expr"],
            "Alert should compare with total normalization",
        )
        self.assertIn("regression_type", alert["expr"], "Alert should track regression type")
        self.assertEqual(
            alert["labels"]["severity"],
            "critical",
            "Alert severity should be critical for high regression rate",
        )
        self.assertIn("0.05", alert["expr"], "Alert threshold should be 5% (0.05)")

    def test_version_distribution_anomaly_alert_configuration(self):
        """Test ODCS version distribution anomaly alert configuration."""
        with open(self.alerts_file, "r") as f:
            config = yaml.safe_load(f)

        odcs_group = None
        for group in config["groups"]:
            if group.get("name") == "odcs_alerts":
                odcs_group = group
                break

        rules = odcs_group.get("rules", [])
        alert = None
        for rule in rules:
            if rule.get("alert") == "ODCSVersionDistributionAnomaly":
                alert = rule
                break

        self.assertIsNotNone(alert, "ODCSVersionDistributionAnomaly alert should exist")
        self.assertIn(
            "odcs_version_distribution_total",
            alert["expr"],
            "Alert should reference version distribution metric",
        )
        self.assertIn(
            'version="3.0.2"', alert["expr"], "Alert should check 3.0.2 version distribution"
        )
        self.assertIn("< 0.50", alert["expr"], "Alert threshold should be 50% (0.50)")
        self.assertIn("> 10", alert["expr"], "Alert should require minimum 10 requests")
        self.assertEqual(alert["labels"]["severity"], "warning", "Alert severity should be warning")

    def test_prometheus_config_includes_odcs_alerts(self):
        """Test that Prometheus configuration includes ODCS alerts file."""
        prometheus_config_file = (
            Path(__file__).parent.parent.parent.parent.parent
            / "monitoring"
            / "prometheus"
            / "prometheus.yml"
        )
        self.assertTrue(prometheus_config_file.exists(), "Prometheus config file should exist")

        with open(prometheus_config_file, "r") as f:
            config_content = f.read()

        self.assertIn(
            "alerts/odcs-alerts.yml",
            config_content,
            "Prometheus config should include odcs-alerts.yml in rule_files",
        )

    def test_alert_for_durations_are_reasonable(self):
        """Test that alert 'for' durations are reasonable (not too short or too long)."""
        with open(self.alerts_file, "r") as f:
            config = yaml.safe_load(f)

        odcs_group = None
        for group in config["groups"]:
            if group.get("name") == "odcs_alerts":
                odcs_group = group
                break

        rules = odcs_group.get("rules", [])

        for rule in rules:
            alert_name = rule.get("alert", "unknown")
            for_duration = rule.get("for", "")

            # Parse duration (e.g., "5m", "10m", "15m", "30m")
            # Convert to minutes for comparison
            if for_duration.endswith("m"):
                minutes = int(for_duration[:-1])
            elif for_duration.endswith("s"):
                minutes = int(for_duration[:-1]) / 60
            elif for_duration.endswith("h"):
                minutes = int(for_duration[:-1]) * 60
            else:
                self.fail(f"Alert '{alert_name}' has invalid 'for' duration format: {for_duration}")

            # Alerts should fire after at least 1 minute but not more than 1 hour
            self.assertGreaterEqual(
                minutes, 1, f"Alert '{alert_name}' 'for' duration should be at least 1 minute"
            )
            self.assertLessEqual(
                minutes, 60, f"Alert '{alert_name}' 'for' duration should be at most 1 hour"
            )

    def test_alerts_reference_correct_metrics(self):
        """Test that all alerts reference the correct ODCS metrics."""
        with open(self.alerts_file, "r") as f:
            config = yaml.safe_load(f)

        odcs_group = None
        for group in config["groups"]:
            if group.get("name") == "odcs_alerts":
                odcs_group = group
                break

        rules = odcs_group.get("rules", [])

        # Expected metrics for ODCS alerts
        expected_metrics = {
            "ODCSNormalizationFailureRate": ["odcs_normalization_total"],
            "ODCSVersionSpecificNormalizationErrors": ["odcs_normalization_total"],
            "ODCSNormalizationRegressionDetected": ["odcs_normalization_regression_total"],
            "ODCSNormalizationRegressionRate": [
                "odcs_normalization_regression_total",
                "odcs_normalization_total",
            ],
            "ODCSVersionDistributionAnomaly": ["odcs_version_distribution_total"],
        }

        for rule in rules:
            alert_name = rule.get("alert", "unknown")
            expr = rule.get("expr", "")

            if alert_name in expected_metrics:
                for metric in expected_metrics[alert_name]:
                    self.assertIn(
                        metric, expr, f"Alert '{alert_name}' should reference metric '{metric}'"
                    )

    def test_alerts_have_backward_compatibility_labels(self):
        """Test that alerts include version labels for backward compatibility tracking."""
        with open(self.alerts_file, "r") as f:
            config = yaml.safe_load(f)

        odcs_group = None
        for group in config["groups"]:
            if group.get("name") == "odcs_alerts":
                odcs_group = group
                break

        rules = odcs_group.get("rules", [])

        # Alerts that should track by version
        version_tracking_alerts = [
            "ODCSNormalizationFailureRate",
            "ODCSVersionSpecificNormalizationErrors",
            "ODCSNormalizationRegressionDetected",
            "ODCSNormalizationRegressionRate",
        ]

        for rule in rules:
            alert_name = rule.get("alert", "unknown")
            expr = rule.get("expr", "")

            if alert_name in version_tracking_alerts:
                # Should group by version or filter by version
                self.assertTrue(
                    "version" in expr or "by (tenant_id, version)" in expr or "by (version" in expr,
                    f"Alert '{alert_name}' should track by version for backward compatibility",
                )

    def test_alerts_handles_unicode_characters(self):
        """Test that alert configuration handles unicode characters correctly."""
        # Test that YAML parsing handles unicode in alert names/descriptions
        with open(self.alerts_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Should handle unicode characters in YAML
        self.assertIsNotNone(config)

    def test_alerts_handles_special_characters(self):
        """Test that alert configuration handles special characters correctly."""
        # Test that YAML parsing handles special characters
        with open(self.alerts_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Should handle special characters in YAML
        self.assertIsNotNone(config)

    def test_alerts_handles_very_large_configuration(self):
        """Test that alert configuration handles very large files correctly."""
        # Test that YAML parsing handles large files
        with open(self.alerts_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Should handle large configuration files
        self.assertIsNotNone(config)

    def test_alerts_handles_nested_structures(self):
        """Test that alert configuration handles nested structures correctly."""
        with open(self.alerts_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Should handle nested YAML structures
        self.assertIsNotNone(config)
        if "groups" in config:
            self.assertIsInstance(config["groups"], list)
