"""
Integration tests for Prometheus metrics configuration.

Validates monitoring/prometheus/prometheus.yml and rule files: structure,
scrape_configs, alerting, rule_files existence. No mocks; uses real files.
"""

from pathlib import Path

import pytest
import yaml

project_root = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="module")
def prometheus_config_path():
    """Path to prometheus.yml."""
    return project_root / "monitoring" / "prometheus" / "prometheus.yml"


@pytest.fixture(scope="module")
def prometheus_config(prometheus_config_path):
    """Loaded Prometheus config YAML."""
    if not prometheus_config_path.exists():
        return None
    with open(prometheus_config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def prometheus_alerts_dir():
    """Path to prometheus alerts directory."""
    return project_root / "monitoring" / "prometheus" / "alerts"


@pytest.mark.integration
class TestPrometheusMetrics:
    """Prometheus config and scrape configuration tests."""

    def test_prometheus_config_file_exists(self, prometheus_config_path):
        """Prometheus config file must exist."""
        assert (
            prometheus_config_path.exists()
        ), f"Prometheus config not found at {prometheus_config_path}"

    def test_prometheus_config_valid_yaml(self, prometheus_config):
        """Prometheus config must be valid YAML with required top-level keys."""
        assert prometheus_config is not None
        assert "scrape_configs" in prometheus_config
        assert "global" in prometheus_config or "scrape_interval" in str(prometheus_config)

    def test_prometheus_global_config(self, prometheus_config):
        """Global scrape_interval should be set."""
        if not prometheus_config:
            pytest.skip("Prometheus config not loaded")
        global_ = prometheus_config.get("global", {})
        assert isinstance(global_, dict)
        assert "scrape_interval" in global_ or "evaluation_interval" in global_

    def test_prometheus_scrape_configs_exist(self, prometheus_config):
        """Scrape configs must be present and non-empty."""
        if not prometheus_config:
            pytest.skip("Prometheus config not loaded")
        scrape_configs = prometheus_config.get("scrape_configs", [])
        assert isinstance(scrape_configs, list)
        assert len(scrape_configs) >= 1

    def test_prometheus_scrape_configs_core_services(self, prometheus_config):
        """Scrape configs must include core application services."""
        if not prometheus_config:
            pytest.skip("Prometheus config not loaded")
        scrape_configs = prometheus_config.get("scrape_configs", [])
        job_names = [c.get("job_name") for c in scrape_configs if isinstance(c, dict)]
        required_jobs = [
            "api-service",
            "worker-service",
            "event-bus-health-service",
            "workflow-engine-service",
            "workflow-registry-service",
            "event-schema-registry-service",
        ]
        for job in required_jobs:
            assert job in job_names, f"Prometheus scrape_configs must include job {job}"

    def test_prometheus_scrape_targets_format(self, prometheus_config):
        """Each scrape config should have static_configs with targets."""
        if not prometheus_config:
            pytest.skip("Prometheus config not loaded")
        scrape_configs = prometheus_config.get("scrape_configs", [])
        for cfg in scrape_configs:
            if not isinstance(cfg, dict):
                continue
            static = cfg.get("static_configs", [])
            assert isinstance(static, list)
            for sc in static:
                targets = sc.get("targets", [])
                assert isinstance(targets, list)
                for t in targets:
                    assert ":" in str(t), f"Target should be host:port, got {t}"

    def test_prometheus_alerting_config(self, prometheus_config):
        """Alerting block should point to Alertmanager."""
        if not prometheus_config:
            pytest.skip("Prometheus config not loaded")
        alerting = prometheus_config.get("alerting", {})
        if not alerting:
            return
        am = alerting.get("alertmanagers", [])
        assert isinstance(am, list)

    def test_prometheus_rule_files_exist(self, prometheus_config, prometheus_config_path):
        """All rule_files in config must exist relative to config dir."""
        if not prometheus_config:
            pytest.skip("Prometheus config not loaded")
        rule_files = prometheus_config.get("rule_files", [])
        if not rule_files:
            return
        config_dir = prometheus_config_path.parent
        for rf in rule_files:
            path = config_dir / rf
            msg = f"Rule file {rf} must exist at {path}"
            assert path.exists(), msg

    def test_prometheus_alerts_yml_exists(self):
        """Main alerts.yml must exist."""
        alerts_path = project_root / "monitoring" / "prometheus" / "alerts.yml"
        assert alerts_path.exists(), f"alerts.yml not found at {alerts_path}"

    def test_prometheus_alerts_valid_yaml(self):
        """alerts.yml must be valid YAML with groups."""
        alerts_path = project_root / "monitoring" / "prometheus" / "alerts.yml"
        if not alerts_path.exists():
            pytest.skip("alerts.yml not found")
        with open(alerts_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data is not None
        assert "groups" in data
        assert isinstance(data["groups"], list)
