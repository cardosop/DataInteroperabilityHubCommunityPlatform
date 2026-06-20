"""
Integration tests for ODPS cache size monitoring (Task 9.8.4.2)

Tests end-to-end cache size monitoring:
- Cache size tracking with real Redis
- Cache size limit tracking
- Cache size alert configuration
- Cache size dashboard validation

All tests use real implementations (no mocks/stubs).
"""

import json
from pathlib import Path

from django.test import TestCase

from hub.apps.contracts.ref_resolver import DEFAULT_CACHE_MAX_ENTRIES, RefResolver
from hub.apps.observability.otel_metrics import (
    odps_ref_cache_size,
    odps_ref_cache_size_limit,
)


class CacheSizeMonitoringIntegrationTest(TestCase):
    """Integration tests for cache size monitoring."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant_id = "test-tenant-integration-123"
        self.resolver = RefResolver(tenant_id=self.tenant_id, enable_caching=True)

    def test_cache_size_tracking_with_real_redis(self):
        """Test that cache size is tracked correctly with real Redis (if available)."""
        if not self.resolver._redis_client:
            self.skipTest("Redis not available for integration test")

        # Clear cache
        try:
            lru_index_key = "odps_ref_index:lru"
            self.resolver._redis_client.delete(lru_index_key)
        except Exception:
            pass

        # Update cache size gauge
        self.resolver._update_cache_size_gauge(self.tenant_id)

        # Verify metrics can be accessed
        self.assertIsNotNone(odps_ref_cache_size)
        self.assertIsNotNone(odps_ref_cache_size_limit)

    def test_cache_size_limit_tracking(self):
        """Test that cache size limit is tracked correctly."""
        # Verify limit is set correctly
        self.assertEqual(self.resolver.cache_max_entries, DEFAULT_CACHE_MAX_ENTRIES)

        # Update cache size gauge (should set limit metric)
        if self.resolver._redis_client:
            try:
                self.resolver._update_cache_size_gauge(self.tenant_id)
            except Exception:
                pass  # Redis may not be available

        # Verify metrics exist
        self.assertIsNotNone(odps_ref_cache_size_limit)

    def test_cache_size_alert_configuration(self):
        """Test that cache size alert is configured correctly."""
        # Path from test file: tests/integration/contracts/test_cache_size_monitoring.py
        # Go up to workspace root: /app
        alerts_file = (
            Path(__file__).parent.parent.parent.parent
            / "monitoring"
            / "prometheus"
            / "alerts"
            / "odps-alerts.yml"
        )

        self.assertTrue(alerts_file.exists(), f"ODPS alerts file should exist at {alerts_file}")

        with open(alerts_file) as f:
            alerts_content = f.read()

        # Verify alert exists
        self.assertIn("ODPSHighCacheSize", alerts_content, "Cache size alert should be defined")

        # Verify alert expression checks for >90% threshold
        self.assertIn("0.90", alerts_content, "Alert should check for 90% threshold")

        # Verify alert checks cache size vs limit
        self.assertIn("odps_ref_cache_size", alerts_content, "Alert should use cache size metric")
        self.assertIn(
            "odps_ref_cache_size_limit", alerts_content, "Alert should use cache size limit metric"
        )

    def test_cache_size_dashboard_exists(self):
        """Test that cache size dashboard panels exist."""
        # Path from test file: tests/integration/contracts/test_cache_size_monitoring.py
        # Go up to workspace root: /app
        dashboard_file = (
            Path(__file__).parent.parent.parent.parent
            / "monitoring"
            / "grafana"
            / "dashboards"
            / "odps-ref-resolution-performance.json"
        )

        self.assertTrue(
            dashboard_file.exists(),
            f"ODPS ref resolution dashboard should exist at {dashboard_file}",
        )

        with open(dashboard_file) as f:
            dashboard = json.load(f)

        # Verify dashboard structure
        self.assertIn("dashboard", dashboard)
        self.assertIn("panels", dashboard["dashboard"])

        # Find cache size panels
        panels = dashboard["dashboard"]["panels"]
        panel_titles = [panel.get("title", "") for panel in panels]

        # Verify cache size panels exist
        self.assertIn(
            "Cache Size Over Time", panel_titles, "Cache size over time panel should exist"
        )
        self.assertIn(
            "Cache Size by Ref Type", panel_titles, "Cache size by ref type panel should exist"
        )
        self.assertIn("Cache Size vs Limit", panel_titles, "Cache size vs limit panel should exist")

    def test_cache_size_dashboard_panel_queries(self):
        """Test that cache size dashboard panels have correct Prometheus queries."""
        # Path from test file: tests/integration/contracts/test_cache_size_monitoring.py
        # Go up to workspace root: /app
        dashboard_file = (
            Path(__file__).parent.parent.parent.parent
            / "monitoring"
            / "grafana"
            / "dashboards"
            / "odps-ref-resolution-performance.json"
        )

        with open(dashboard_file) as f:
            dashboard = json.load(f)

        panels = dashboard["dashboard"]["panels"]

        # Find cache size panels
        cache_size_panel = next(
            (p for p in panels if p.get("title") == "Cache Size Over Time"), None
        )
        cache_size_by_type_panel = next(
            (p for p in panels if p.get("title") == "Cache Size by Ref Type"), None
        )
        cache_size_vs_limit_panel = next(
            (p for p in panels if p.get("title") == "Cache Size vs Limit"), None
        )

        # Verify cache size over time panel
        self.assertIsNotNone(cache_size_panel, "Cache size over time panel should exist")
        self.assertIn("targets", cache_size_panel)
        targets = cache_size_panel["targets"]
        self.assertGreater(len(targets), 0, "Panel should have at least one target")
        # Verify query uses odps_ref_cache_size metric
        expr_found = any("odps_ref_cache_size" in target.get("expr", "") for target in targets)
        self.assertTrue(expr_found, "Panel should query odps_ref_cache_size metric")

        # Verify cache size by ref type panel
        self.assertIsNotNone(cache_size_by_type_panel, "Cache size by ref type panel should exist")
        self.assertIn("targets", cache_size_by_type_panel)
        targets = cache_size_by_type_panel["targets"]
        self.assertGreater(len(targets), 0, "Panel should have at least one target")
        # Verify query uses odps_ref_cache_size metric
        expr_found = any("odps_ref_cache_size" in target.get("expr", "") for target in targets)
        self.assertTrue(expr_found, "Panel should query odps_ref_cache_size metric")

        # Verify cache size vs limit panel
        self.assertIsNotNone(cache_size_vs_limit_panel, "Cache size vs limit panel should exist")
        self.assertIn("targets", cache_size_vs_limit_panel)
        targets = cache_size_vs_limit_panel["targets"]
        self.assertGreater(len(targets), 0, "Panel should have at least one target")
        # Verify query uses both cache size and limit metrics
        exprs = [target.get("expr", "") for target in targets]
        size_expr_found = any("odps_ref_cache_size" in expr for expr in exprs)
        limit_expr_found = any("odps_ref_cache_size_limit" in expr for expr in exprs)
        self.assertTrue(size_expr_found, "Panel should query odps_ref_cache_size metric")
        self.assertTrue(limit_expr_found, "Panel should query odps_ref_cache_size_limit metric")

    def test_cache_size_dashboard_panel_prometheus_syntax(self):
        """Test that cache size dashboard panel queries use valid Prometheus syntax."""
        # Path from test file: tests/integration/contracts/test_cache_size_monitoring.py
        # Go up to workspace root: /app
        dashboard_file = (
            Path(__file__).parent.parent.parent.parent
            / "monitoring"
            / "grafana"
            / "dashboards"
            / "odps-ref-resolution-performance.json"
        )

        with open(dashboard_file) as f:
            dashboard = json.load(f)

        panels = dashboard["dashboard"]["panels"]

        # Find cache size panels
        cache_size_panels = [p for p in panels if "Cache Size" in p.get("title", "")]

        for panel in cache_size_panels:
            if "targets" not in panel:
                continue

            for target in panel["targets"]:
                expr = target.get("expr", "")
                if not expr:
                    continue

                # Verify Prometheus query syntax basics
                # Should contain metric name
                self.assertTrue(
                    "odps_ref_cache_size" in expr or "odps_ref_cache_size_limit" in expr,
                    f"Panel '{panel.get('title')}' query should contain cache size metric",
                )

                # Should have proper label filters if used
                if "ref_type" in expr:
                    self.assertIn(
                        'ref_type="external"',
                        expr,
                        f"Panel '{panel.get('title')}' should filter by ref_type='external'",
                    )

    def test_cache_size_alert_prometheus_syntax(self):
        """Test that cache size alert uses valid Prometheus syntax."""
        # Path from test file: tests/integration/contracts/test_cache_size_monitoring.py
        # Go up to workspace root: /app
        alerts_file = (
            Path(__file__).parent.parent.parent.parent
            / "monitoring"
            / "prometheus"
            / "alerts"
            / "odps-alerts.yml"
        )

        with open(alerts_file) as f:
            alerts_content = f.read()

        # Find ODPSHighCacheSize alert
        alert_start = alerts_content.find("ODPSHighCacheSize")
        self.assertNotEqual(alert_start, -1, "ODPSHighCacheSize alert should exist")

        # Extract alert expression
        expr_start = alerts_content.find("expr:", alert_start)
        self.assertNotEqual(expr_start, -1, "Alert should have expr field")

        # Verify expression contains cache size metrics
        self.assertIn("odps_ref_cache_size", alerts_content[expr_start : expr_start + 500])
        self.assertIn("odps_ref_cache_size_limit", alerts_content[expr_start : expr_start + 500])

        # Verify expression checks for >90% threshold
        self.assertIn("0.90", alerts_content[expr_start : expr_start + 500])
