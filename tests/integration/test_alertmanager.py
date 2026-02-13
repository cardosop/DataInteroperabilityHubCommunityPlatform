"""
Integration tests for Alertmanager configuration.

Validates monitoring/alertmanager/alertmanager.yml: structure, route tree,
receivers, inhibit_rules. No mocks; uses real file.
"""

from pathlib import Path

import pytest
import yaml

project_root = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="module")
def alertmanager_config_path():
    """Path to alertmanager.yml."""
    return project_root / "monitoring" / "alertmanager" / "alertmanager.yml"


@pytest.fixture(scope="module")
def alertmanager_config(alertmanager_config_path):
    """Loaded Alertmanager config YAML."""
    if not alertmanager_config_path.exists():
        return None
    with open(alertmanager_config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.mark.integration
class TestAlertmanager:
    """Alertmanager configuration tests."""

    def test_alertmanager_config_file_exists(self, alertmanager_config_path):
        """Alertmanager config file must exist."""
        assert (
            alertmanager_config_path.exists()
        ), f"Alertmanager config not found at {alertmanager_config_path}"

    def test_alertmanager_config_valid_yaml(self, alertmanager_config):
        """Alertmanager config must be valid YAML."""
        assert alertmanager_config is not None
        assert isinstance(alertmanager_config, dict)

    def test_alertmanager_route_defined(self, alertmanager_config):
        """Route tree must be defined (receiver required; routes optional)."""
        if not alertmanager_config:
            pytest.skip("Alertmanager config not loaded")
        route = alertmanager_config.get("route", {})
        assert isinstance(route, dict)
        assert "receiver" in route
        if "routes" in route:
            assert isinstance(route["routes"], list), "route.routes must be a list when present"

    def test_alertmanager_receivers_defined(self, alertmanager_config):
        """Receivers list must be present and non-empty."""
        if not alertmanager_config:
            pytest.skip("Alertmanager config not loaded")
        receivers = alertmanager_config.get("receivers", [])
        assert isinstance(receivers, list)
        assert len(receivers) >= 1

    def test_alertmanager_route_receiver_exists(self, alertmanager_config):
        """Default route receiver must exist in receivers list."""
        if not alertmanager_config:
            pytest.skip("Alertmanager config not loaded")
        route = alertmanager_config.get("route", {})
        receivers = alertmanager_config.get("receivers", [])
        default_name = route.get("receiver")
        if not default_name:
            return
        names = [r.get("name") for r in receivers if isinstance(r, dict) and "name" in r]
        assert default_name in names, f"Route receiver '{default_name}' must exist in receivers"

    def test_alertmanager_inhibit_rules_optional(self, alertmanager_config):
        """If inhibit_rules present, must be list."""
        if not alertmanager_config:
            pytest.skip("Alertmanager config not loaded")
        rules = alertmanager_config.get("inhibit_rules", [])
        assert isinstance(rules, list)
