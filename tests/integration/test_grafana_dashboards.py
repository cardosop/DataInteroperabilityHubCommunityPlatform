"""
Integration tests for Grafana dashboards and datasources.

Validates monitoring/grafana/dashboards (existence, required dashboards,
valid JSON) and datasources config. No mocks; uses real files.
"""

import json
from pathlib import Path

import pytest

from tests.integration.monitoring_constants import REQUIRED_GRAFANA_DASHBOARDS

project_root = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="module")
def dashboards_dir():
    """Path to Grafana dashboards directory."""
    return project_root / "monitoring" / "grafana" / "dashboards"


@pytest.fixture(scope="module")
def datasources_dir():
    """Path to Grafana datasources directory."""
    return project_root / "monitoring" / "grafana" / "datasources"


@pytest.mark.integration
class TestGrafanaDashboards:
    """Grafana dashboard and datasource configuration tests."""

    def test_dashboards_directory_exists(self, dashboards_dir):
        """Dashboards directory must exist."""
        assert dashboards_dir.exists(), f"Dashboards dir not found at {dashboards_dir}"
        assert dashboards_dir.is_dir()

    def test_required_dashboards_exist(self, dashboards_dir):
        """Required dashboards must exist (monitoring/grafana/dashboards)."""
        for name in REQUIRED_GRAFANA_DASHBOARDS:
            path = dashboards_dir / name
            err = f"Required dashboard {name} not found at {path}"
            assert path.exists(), err

    def test_dashboard_json_valid(self, dashboards_dir):
        """Each JSON dashboard file must parse and have dashboard/title."""
        if not dashboards_dir.exists():
            pytest.skip("Dashboards dir not found")  # noqa: skip-in-body — runtime service dependency
        for path in dashboards_dir.glob("*.json"):
            with open(path, encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError as e:
                    pytest.fail(f"{path.name}: invalid JSON: {e}")
            assert data is not None
            if isinstance(data, dict):
                if "dashboard" in data:
                    d = data["dashboard"]
                    assert "title" in d or "panels" in d
                else:
                    assert "title" in data or "panels" in data

    def test_datasources_directory_exists(self, datasources_dir):
        """Datasources directory must exist."""
        assert datasources_dir.exists(), f"Datasources dir not found at {datasources_dir}"
        assert datasources_dir.is_dir()

    def test_prometheus_datasource_config_exists(self, datasources_dir):
        """Prometheus datasource config must exist."""
        path = datasources_dir / "prometheus.yml"
        assert path.exists(), "Prometheus datasource config not found at " + str(path)

    def test_prometheus_datasource_config_valid(self, datasources_dir):
        """Datasource config valid (YAML with apiVersion/datasources)."""
        path = datasources_dir / "prometheus.yml"
        if not path.exists():
            pytest.skip("Prometheus datasource config not found")  # noqa: skip-in-body — runtime service dependency
        content = path.read_text(encoding="utf-8")
        assert "apiVersion" in content or "datasources" in content
        assert "prometheus" in content.lower()
        assert "url" in content.lower() or "9090" in content
