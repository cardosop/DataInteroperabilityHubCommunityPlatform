"""Phase 109.5 — Prometheus alert rules validation.

Validates alert rule structure, uniqueness, and required annotations.
Uses YAML parsing — does NOT require promtool.
"""
import os
import pytest
import yaml

ALERTS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "monitoring", "prometheus", "alerts.yml"
)


@pytest.fixture
def alerts_config():
    """Load and parse alerts.yml."""
    assert os.path.exists(ALERTS_FILE), f"alerts.yml not found at {ALERTS_FILE}"
    with open(ALERTS_FILE) as f:
        return yaml.safe_load(f)


@pytest.fixture
def all_rules(alerts_config):
    """Extract all alert rules from config."""
    rules = []
    for group in alerts_config.get("groups", []):
        for rule in group.get("rules", []):
            if "alert" in rule:
                rules.append(rule)
    return rules


class TestAlertRuleStructure:
    """Validate alert rule YAML structure."""

    def test_alerts_file_is_valid_yaml(self, alerts_config):
        assert alerts_config is not None
        assert "groups" in alerts_config

    def test_at_least_one_group(self, alerts_config):
        assert len(alerts_config["groups"]) >= 1

    def test_all_rules_have_alert_name(self, all_rules):
        for rule in all_rules:
            assert "alert" in rule, f"Rule missing alert name: {rule}"

    def test_alert_names_are_unique(self, all_rules):
        names = [r["alert"] for r in all_rules]
        duplicates = [n for n in names if names.count(n) > 1]
        assert len(set(duplicates)) == 0, f"Duplicate alert names: {set(duplicates)}"

    def test_all_rules_have_expr(self, all_rules):
        for rule in all_rules:
            assert "expr" in rule, f"Alert {rule['alert']} missing expr"

    def test_all_rules_have_labels(self, all_rules):
        for rule in all_rules:
            assert "labels" in rule, f"Alert {rule['alert']} missing labels"

    def test_all_rules_have_severity(self, all_rules):
        for rule in all_rules:
            severity = rule.get("labels", {}).get("severity")
            assert severity in ("critical", "warning", "info"), \
                f"Alert {rule['alert']} has invalid severity: {severity}"

    def test_critical_alerts_have_annotations(self, all_rules):
        """Critical alerts must have summary and description."""
        for rule in all_rules:
            if rule.get("labels", {}).get("severity") == "critical":
                annotations = rule.get("annotations", {})
                assert "summary" in annotations, \
                    f"Critical alert {rule['alert']} missing summary"
                assert "description" in annotations, \
                    f"Critical alert {rule['alert']} missing description"

    def test_at_least_10_alert_rules(self, all_rules):
        assert len(all_rules) >= 10, f"Only {len(all_rules)} alert rules defined"

    def test_service_down_alert_exists(self, all_rules):
        names = [r["alert"] for r in all_rules]
        assert "ServiceDown" in names, "Missing ServiceDown alert"

    def test_high_error_rate_alert_exists(self, all_rules):
        names = [r["alert"] for r in all_rules]
        assert "HighErrorRate" in names, "Missing HighErrorRate alert"
