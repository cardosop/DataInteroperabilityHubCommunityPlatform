"""
Job Queue Dashboards Integration Tests

Comprehensive tests to validate that job queue monitoring dashboards
(ODPS Job Queue and Job Worker Health) are properly configured with
valid JSON structure, required panels, and correct Prometheus queries.

All tests validate against real dashboard files - no mocks or stubs.
"""

import json
import re
from pathlib import Path

import structlog
from django.test import TestCase

logger = structlog.get_logger(__name__)


class JobQueueDashboardsTest(TestCase):
    """Test job queue Grafana dashboard configuration files"""

    def setUp(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).parent.parent.parent
        self.dashboards_dir = self.project_root / "monitoring" / "grafana" / "dashboards"
        self.odps_dashboard_path = self.dashboards_dir / "odps-job-queue.json"
        self.worker_health_dashboard_path = self.dashboards_dir / "job-worker-health.json"

    def test_odps_job_queue_dashboard_exists(self):
        """Test that ODPS job queue dashboard exists"""
        self.assertTrue(
            self.odps_dashboard_path.exists(),
            f"ODPS job queue dashboard not found at {self.odps_dashboard_path}",
        )

    def test_job_worker_health_dashboard_exists(self):
        """Test that job worker health dashboard exists"""
        self.assertTrue(
            self.worker_health_dashboard_path.exists(),
            f"Job worker health dashboard not found at {self.worker_health_dashboard_path}",
        )

    def test_odps_dashboard_valid_json(self):
        """Test that ODPS job queue dashboard is valid JSON"""
        try:
            content = self.odps_dashboard_path.read_text()
            dashboard = json.loads(content)
            self.assertIsInstance(dashboard, dict)
        except json.JSONDecodeError as e:
            self.fail(f"ODPS job queue dashboard is not valid JSON: {e}")

    def test_worker_health_dashboard_valid_json(self):
        """Test that job worker health dashboard is valid JSON"""
        try:
            content = self.worker_health_dashboard_path.read_text()
            dashboard = json.loads(content)
            self.assertIsInstance(dashboard, dict)
        except json.JSONDecodeError as e:
            self.fail(f"Job worker health dashboard is not valid JSON: {e}")

    def test_odps_dashboard_structure(self):
        """Test that ODPS dashboard has required structure"""
        content = self.odps_dashboard_path.read_text()
        dashboard = json.loads(content)

        self.assertIn("dashboard", dashboard, "Dashboard must have 'dashboard' key")
        dashboard_obj = dashboard["dashboard"]

        required_keys = ["title", "tags", "schemaVersion", "version", "panels"]
        for key in required_keys:
            self.assertIn(key, dashboard_obj, f"Dashboard must have '{key}' key")

        self.assertEqual(dashboard_obj["title"], "ODPS Job Queue")
        self.assertIn("odps", dashboard_obj["tags"])
        self.assertIsInstance(dashboard_obj["panels"], list)
        self.assertGreater(
            len(dashboard_obj["panels"]), 0, "Dashboard must have at least one panel"
        )

    def test_worker_health_dashboard_structure(self):
        """Test that worker health dashboard has required structure"""
        content = self.worker_health_dashboard_path.read_text()
        dashboard = json.loads(content)

        self.assertIn("dashboard", dashboard, "Dashboard must have 'dashboard' key")
        dashboard_obj = dashboard["dashboard"]

        required_keys = ["title", "tags", "schemaVersion", "version", "panels"]
        for key in required_keys:
            self.assertIn(key, dashboard_obj, f"Dashboard must have '{key}' key")

        self.assertEqual(dashboard_obj["title"], "Job Worker Health")
        self.assertIn("workers", dashboard_obj["tags"])
        self.assertIsInstance(dashboard_obj["panels"], list)
        self.assertGreater(
            len(dashboard_obj["panels"]), 0, "Dashboard must have at least one panel"
        )

    def test_odps_dashboard_panels_exist(self):
        """Test that ODPS dashboard has all required panels"""
        content = self.odps_dashboard_path.read_text()
        dashboard = json.loads(content)
        panels = dashboard["dashboard"]["panels"]

        required_panels = [
            "ODPS Job Queue Length by Job Type",
            "ODPS Job Execution Rate by Job Type",
            "ODPS Job Success/Failure Rate by Job Type",
            "ODPS Job Duration (p50, p95, p99) by Job Type",
            "ODPS Job Retry Count Distribution",
            "ODPS Job Timeout Rate",
            "ODPS Job Queue Depth Over Time",
            "ODPS Job Processing Rate Over Time",
        ]

        panel_titles = [panel.get("title", "") for panel in panels]
        for required_panel in required_panels:
            self.assertIn(
                required_panel,
                panel_titles,
                f"Required panel '{required_panel}' not found in ODPS dashboard",
            )

    def test_worker_health_dashboard_panels_exist(self):
        """Test that worker health dashboard has all required panels"""
        content = self.worker_health_dashboard_path.read_text()
        dashboard = json.loads(content)
        panels = dashboard["dashboard"]["panels"]

        required_panels = [
            "Active Worker Count",
            "Worker CPU Usage",
            "Worker Memory Usage",
            "Worker Error Rate",
            "Worker Throughput (Jobs/Second)",
            "Worker Health Status",
        ]

        panel_titles = [panel.get("title", "") for panel in panels]
        for required_panel in required_panels:
            self.assertIn(
                required_panel,
                panel_titles,
                f"Required panel '{required_panel}' not found in worker health dashboard",
            )

    def test_odps_dashboard_queries_use_correct_metrics(self):
        """Test that ODPS dashboard queries use correct Prometheus metrics"""
        content = self.odps_dashboard_path.read_text()
        dashboard = json.loads(content)
        panels = dashboard["dashboard"]["panels"]

        expected_metrics = [
            "job_queue_length",
            "jobs_completed_total",
            "job_duration_seconds",
            "job_retry_count",
            "job_timeout_rate",
            "job_queue_depth",
            "job_processing_rate",
        ]

        all_queries = []
        for panel in panels:
            if "targets" in panel:
                for target in panel["targets"]:
                    if "expr" in target:
                        all_queries.append(target["expr"])

        queries_str = " ".join(all_queries)
        for metric in expected_metrics:
            self.assertIn(metric, queries_str, f"ODPS dashboard should use metric '{metric}'")

    def test_odps_dashboard_filters_odps_jobs(self):
        """Test that ODPS dashboard filters for ODPS job types"""
        content = self.odps_dashboard_path.read_text()
        dashboard = json.loads(content)
        panels = dashboard["dashboard"]["panels"]

        # Check that at least one query filters for ODPS jobs
        has_odps_filter = False
        for panel in panels:
            if "targets" in panel:
                for target in panel["targets"]:
                    if "expr" in target:
                        expr = target["expr"]
                        if "ODPS_" in expr or 'job_type=~"ODPS_.*"' in expr:
                            has_odps_filter = True
                            break

        self.assertTrue(has_odps_filter, "ODPS dashboard should filter for ODPS job types")

    def test_worker_health_dashboard_queries_use_correct_metrics(self):
        """Test that worker health dashboard queries use correct Prometheus metrics"""
        content = self.worker_health_dashboard_path.read_text()
        dashboard = json.loads(content)
        panels = dashboard["dashboard"]["panels"]

        expected_metrics = [
            "job_worker_active",
            "job_worker_throughput",
            "jobs_failed_total",
        ]

        all_queries = []
        for panel in panels:
            if "targets" in panel:
                for target in panel["targets"]:
                    if "expr" in target:
                        all_queries.append(target["expr"])

        queries_str = " ".join(all_queries)
        for metric in expected_metrics:
            self.assertIn(
                metric, queries_str, f"Worker health dashboard should use metric '{metric}'"
            )

    def test_dashboards_prometheus_query_syntax(self):
        """Test that dashboard Prometheus queries have valid syntax"""
        dashboards = [
            self.odps_dashboard_path,
            self.worker_health_dashboard_path,
        ]

        for dashboard_path in dashboards:
            content = dashboard_path.read_text()
            dashboard = json.loads(content)
            panels = dashboard["dashboard"]["panels"]

            for panel in panels:
                if "targets" in panel:
                    for target in panel["targets"]:
                        if "expr" in target:
                            expr = target["expr"]
                            # Basic validation: should not be empty
                            self.assertGreater(
                                len(expr.strip()),
                                0,
                                f"Prometheus query in {dashboard_path.name} should not be empty",
                            )
                            # Should contain at least one metric name
                            self.assertTrue(
                                re.search(r"[a-z_]+(_total|_seconds|_count|_rate)?", expr),
                                f"Prometheus query '{expr}' in {dashboard_path.name} should contain a metric name",
                            )

    def test_dashboards_panel_grid_positions(self):
        """Test that dashboard panels have valid grid positions"""
        dashboards = [
            self.odps_dashboard_path,
            self.worker_health_dashboard_path,
        ]

        for dashboard_path in dashboards:
            content = dashboard_path.read_text()
            dashboard = json.loads(content)
            panels = dashboard["dashboard"]["panels"]

            for panel in panels:
                if "gridPos" in panel:
                    grid_pos = panel["gridPos"]
                    self.assertIn("h", grid_pos, "Panel gridPos should have 'h' (height)")
                    self.assertIn("w", grid_pos, "Panel gridPos should have 'w' (width)")
                    self.assertIn("x", grid_pos, "Panel gridPos should have 'x' (x position)")
                    self.assertIn("y", grid_pos, "Panel gridPos should have 'y' (y position)")
                    # Validate values are positive integers
                    self.assertGreater(grid_pos["h"], 0, "Panel height should be positive")
                    self.assertGreater(grid_pos["w"], 0, "Panel width should be positive")
                    self.assertGreaterEqual(
                        grid_pos["x"], 0, "Panel x position should be non-negative"
                    )
                    self.assertGreaterEqual(
                        grid_pos["y"], 0, "Panel y position should be non-negative"
                    )
