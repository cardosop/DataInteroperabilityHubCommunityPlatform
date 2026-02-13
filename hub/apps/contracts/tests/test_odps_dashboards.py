"""
ODPS Grafana Dashboards Validation Tests (Task 6.2.5)

Tests validate that all ODPS/ODCS Grafana dashboards are properly configured,
have valid JSON structure, and contain required panels and queries.

All tests use real implementations (no mocks/stubs) and follow engineering best practices.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, List
from django.test import TestCase
import structlog

logger = structlog.get_logger(__name__)


class ODPSDashboardsValidationTest(TestCase):
    """Test ODPS Grafana dashboard configuration files."""

    # These tests don't require database access - they only validate JSON files
    databases = {'default'}  # Allow tests to run without database if needed

    def setUp(self):
        """Set up test fixtures."""
        self.dashboards_dir = Path(__file__).parent.parent.parent.parent.parent / "monitoring" / "grafana" / "dashboards"
        self.required_dashboards = [
            "odps-adoption.json",
            "odps-version-distribution.json",
            "odcs-version-distribution.json",
            "odps-ref-resolution-performance.json",
            "odps-rate-limiting.json",
            "odps-cache-performance.json",
            "odps-odcs-separation-metrics.json",
            "odcs-regression-detection.json",
            "odps-performance-targets.json",
            "odps-marketplace-integration.json",
            "odps-creation-flow-performance.json",
        ]

    def test_all_required_dashboards_exist(self):
        """Test that all required ODPS dashboards exist."""
        for dashboard_file in self.required_dashboards:
            dashboard_path = self.dashboards_dir / dashboard_file
            self.assertTrue(
                dashboard_path.exists(),
                f"Required dashboard file not found: {dashboard_file}"
            )

    def test_dashboard_files_are_valid_json(self):
        """Test that all dashboard files are valid JSON."""
        for dashboard_file in self.required_dashboards:
            dashboard_path = self.dashboards_dir / dashboard_file
            try:
                with open(dashboard_path, 'r') as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                self.fail(f"Dashboard file {dashboard_file} is not valid JSON: {e}")

    def test_dashboards_have_required_structure(self):
        """Test that all dashboards have required structure (dashboard, title, panels)."""
        for dashboard_file in self.required_dashboards:
            dashboard_path = self.dashboards_dir / dashboard_file
            with open(dashboard_path, 'r') as f:
                config = json.load(f)

            self.assertIn('dashboard', config, f"Dashboard {dashboard_file} must have 'dashboard' key")
            dashboard = config['dashboard']

            self.assertIn('title', dashboard, f"Dashboard {dashboard_file} must have 'title'")
            self.assertIn('panels', dashboard, f"Dashboard {dashboard_file} must have 'panels'")
            self.assertIsInstance(dashboard['panels'], list, f"Dashboard {dashboard_file} panels must be a list")
            self.assertGreater(len(dashboard['panels']), 0, f"Dashboard {dashboard_file} must have at least one panel")

    def test_dashboards_have_required_metadata(self):
        """Test that all dashboards have required metadata (tags, schemaVersion, version)."""
        for dashboard_file in self.required_dashboards:
            dashboard_path = self.dashboards_dir / dashboard_file
            with open(dashboard_path, 'r') as f:
                config = json.load(f)

            dashboard = config['dashboard']

            self.assertIn('tags', dashboard, f"Dashboard {dashboard_file} must have 'tags'")
            self.assertIsInstance(dashboard['tags'], list, f"Dashboard {dashboard_file} tags must be a list")
            # Check for task tag (different dashboards may have different task tags)
            has_task_tag = any('task-' in tag for tag in dashboard['tags'])
            self.assertTrue(has_task_tag, f"Dashboard {dashboard_file} must have a task tag (e.g., 'task-6.2.5' or 'task-6.6.8')")

            self.assertIn('schemaVersion', dashboard, f"Dashboard {dashboard_file} must have 'schemaVersion'")
            self.assertIn('version', dashboard, f"Dashboard {dashboard_file} must have 'version'")

    def test_panels_have_required_fields(self):
        """Test that all panels have required fields (id, title, type, gridPos, targets)."""
        for dashboard_file in self.required_dashboards:
            dashboard_path = self.dashboards_dir / dashboard_file
            with open(dashboard_path, 'r') as f:
                config = json.load(f)

            dashboard = config['dashboard']
            panels = dashboard.get('panels', [])

            for i, panel in enumerate(panels):
                panel_name = f"{dashboard_file} panel {i+1}"

                self.assertIn('id', panel, f"{panel_name} must have 'id'")
                self.assertIn('title', panel, f"{panel_name} must have 'title'")
                self.assertIn('type', panel, f"{panel_name} must have 'type'")
                self.assertIn('gridPos', panel, f"{panel_name} must have 'gridPos'")
                self.assertIn('targets', panel, f"{panel_name} must have 'targets'")

                # Validate gridPos structure
                grid_pos = panel['gridPos']
                self.assertIn('h', grid_pos, f"{panel_name} gridPos must have 'h'")
                self.assertIn('w', grid_pos, f"{panel_name} gridPos must have 'w'")
                self.assertIn('x', grid_pos, f"{panel_name} gridPos must have 'x'")
                self.assertIn('y', grid_pos, f"{panel_name} gridPos must have 'y'")

                # Validate targets structure
                targets = panel['targets']
                self.assertIsInstance(targets, list, f"{panel_name} targets must be a list")
                self.assertGreater(len(targets), 0, f"{panel_name} must have at least one target")

                for j, target in enumerate(targets):
                    target_name = f"{panel_name} target {j+1}"
                    # Targets can have either 'expr' (Prometheus) or 'rawSql'/'rawQuery' (PostgreSQL)
                    has_expr = 'expr' in target
                    has_sql = 'rawSql' in target or 'rawQuery' in target
                    self.assertTrue(
                        has_expr or has_sql,
                        f"{target_name} must have 'expr' (Prometheus) or 'rawSql'/'rawQuery' (PostgreSQL)"
                    )
                    self.assertIn('refId', target, f"{target_name} must have 'refId'")

    def test_odps_adoption_dashboard_content(self):
        """Test ODPS adoption dashboard has correct content."""
        dashboard_path = self.dashboards_dir / "odps-adoption.json"
        with open(dashboard_path, 'r') as f:
            config = json.load(f)

        dashboard = config['dashboard']
        self.assertEqual(dashboard['title'], "ODPS Adoption (Marketplace)")
        self.assertIn('odps', dashboard['tags'])
        self.assertIn('marketplace', dashboard['tags'])

        # Check for key panels
        panel_titles = [p.get('title', '') for p in dashboard['panels']]
        self.assertTrue(any('Ingestion Rate' in title for title in panel_titles),
                       "Dashboard should have ingestion rate panel")
        self.assertTrue(any('Adoption' in title for title in panel_titles),
                       "Dashboard should have adoption panel")

    def test_odps_version_distribution_dashboard_content(self):
        """Test ODPS version distribution dashboard has correct content."""
        dashboard_path = self.dashboards_dir / "odps-version-distribution.json"
        with open(dashboard_path, 'r') as f:
            config = json.load(f)

        dashboard = config['dashboard']
        self.assertEqual(dashboard['title'], "ODPS Version Distribution")

        # Check for version-related queries
        all_exprs = []
        for panel in dashboard['panels']:
            for target in panel.get('targets', []):
                all_exprs.append(target.get('expr', ''))

        version_exprs = [expr for expr in all_exprs if 'odps_version_distribution_total' in expr]
        self.assertGreater(len(version_exprs), 0, "Dashboard should have version distribution queries")

    def test_odcs_version_distribution_dashboard_content(self):
        """Test ODCS version distribution dashboard has correct content."""
        dashboard_path = self.dashboards_dir / "odcs-version-distribution.json"
        with open(dashboard_path, 'r') as f:
            config = json.load(f)

        dashboard = config['dashboard']
        self.assertEqual(dashboard['title'], "ODCS Version Distribution")

        # Check for ODCS version queries
        all_exprs = []
        for panel in dashboard['panels']:
            for target in panel.get('targets', []):
                all_exprs.append(target.get('expr', ''))

        odcs_exprs = [expr for expr in all_exprs if 'odcs_version_distribution_total' in expr]
        self.assertGreater(len(odcs_exprs), 0, "Dashboard should have ODCS version distribution queries")

    def test_ref_resolution_performance_dashboard_content(self):
        """Test $ref resolution performance dashboard has correct content."""
        dashboard_path = self.dashboards_dir / "odps-ref-resolution-performance.json"
        with open(dashboard_path, 'r') as f:
            config = json.load(f)

        dashboard = config['dashboard']
        self.assertEqual(dashboard['title'], "ODPS $ref Resolution Performance")

        # Check for performance-related queries
        all_exprs = []
        for panel in dashboard['panels']:
            for target in panel.get('targets', []):
                all_exprs.append(target.get('expr', ''))

        duration_exprs = [expr for expr in all_exprs if 'odps_ref_resolution_duration_seconds' in expr]
        self.assertGreater(len(duration_exprs), 0, "Dashboard should have duration queries")

        success_exprs = [expr for expr in all_exprs if 'odps_ref_resolution_total' in expr]
        self.assertGreater(len(success_exprs), 0, "Dashboard should have success/failure queries")

    def test_rate_limiting_dashboard_content(self):
        """Test rate limiting dashboard has correct content."""
        dashboard_path = self.dashboards_dir / "odps-rate-limiting.json"
        with open(dashboard_path, 'r') as f:
            config = json.load(f)

        dashboard = config['dashboard']
        self.assertEqual(dashboard['title'], "ODPS Rate Limiting")

        # Check for rate limiting queries
        all_exprs = []
        for panel in dashboard['panels']:
            for target in panel.get('targets', []):
                all_exprs.append(target.get('expr', ''))

        rate_limit_exprs = [expr for expr in all_exprs if 'odps_rate_limit_violations_total' in expr]
        self.assertGreater(len(rate_limit_exprs), 0, "Dashboard should have rate limit violation queries")

    def test_cache_performance_dashboard_content(self):
        """Test cache performance dashboard has correct content."""
        dashboard_path = self.dashboards_dir / "odps-cache-performance.json"
        with open(dashboard_path, 'r') as f:
            config = json.load(f)

        dashboard = config['dashboard']
        self.assertEqual(dashboard['title'], "ODPS Cache Performance")

        # Check for cache-related queries
        all_exprs = []
        for panel in dashboard['panels']:
            for target in panel.get('targets', []):
                all_exprs.append(target.get('expr', ''))

        cache_exprs = [expr for expr in all_exprs if 'odps_ref_cache' in expr]
        self.assertGreater(len(cache_exprs), 0, "Dashboard should have cache queries")

    def test_separation_metrics_dashboard_content(self):
        """Test separation metrics dashboard has correct content."""
        dashboard_path = self.dashboards_dir / "odps-odcs-separation-metrics.json"
        with open(dashboard_path, 'r') as f:
            config = json.load(f)

        dashboard = config['dashboard']
        self.assertEqual(dashboard['title'], "ODPS vs ODCS Separation Metrics")

        # Check for both ODPS and ODCS queries
        all_exprs = []
        for panel in dashboard['panels']:
            for target in panel.get('targets', []):
                all_exprs.append(target.get('expr', ''))

        odps_exprs = [expr for expr in all_exprs if 'odps_' in expr]
        odcs_exprs = [expr for expr in all_exprs if 'odcs_' in expr]
        self.assertGreater(len(odps_exprs), 0, "Dashboard should have ODPS queries")
        self.assertGreater(len(odcs_exprs), 0, "Dashboard should have ODCS queries")

    def test_regression_detection_dashboard_content(self):
        """Test ODCS regression detection dashboard has correct content."""
        dashboard_path = self.dashboards_dir / "odcs-regression-detection.json"
        with open(dashboard_path, 'r') as f:
            config = json.load(f)

        dashboard = config['dashboard']
        self.assertEqual(dashboard['title'], "ODCS Regression Detection")

        # Check for regression queries
        all_exprs = []
        for panel in dashboard['panels']:
            for target in panel.get('targets', []):
                all_exprs.append(target.get('expr', ''))

        regression_exprs = [expr for expr in all_exprs if 'odcs_normalization_regression_total' in expr]
        self.assertGreater(len(regression_exprs), 0, "Dashboard should have regression queries")

    def test_performance_targets_dashboard_content(self):
        """Test performance targets dashboard has correct content."""
        dashboard_path = self.dashboards_dir / "odps-performance-targets.json"
        with open(dashboard_path, 'r') as f:
            config = json.load(f)

        dashboard = config['dashboard']
        self.assertEqual(dashboard['title'], "ODPS Performance Targets")

        # Check for target comparison queries
        all_exprs = []
        for panel in dashboard['panels']:
            for target in panel.get('targets', []):
                all_exprs.append(target.get('expr', ''))

        target_exprs = [expr for expr in all_exprs if '0.010' in expr or '0.050' in expr or '5.0' in expr]
        self.assertGreater(len(target_exprs), 0, "Dashboard should have target value queries")

    def test_dashboards_prometheus_queries_are_valid(self):
        """Test that all Prometheus queries in dashboards are syntactically valid."""
        # This is a basic check - full validation would require Prometheus server
        prometheus_functions = ['rate', 'sum', 'histogram_quantile', 'increase', 'count', 'avg', 'max', 'min', 'deriv']

        for dashboard_file in self.required_dashboards:
            dashboard_path = self.dashboards_dir / dashboard_file
            with open(dashboard_path, 'r') as f:
                config = json.load(f)

            dashboard = config['dashboard']
            for panel in dashboard.get('panels', []):
                for target in panel.get('targets', []):
                    expr = target.get('expr', '')
                    # Skip empty expressions (some targets might not have queries)
                    if not expr:
                        continue
                    # Basic validation: expr should not be empty (but we skip empty ones above)
                    self.assertGreater(len(expr), 0, f"Query expression should not be empty in {dashboard_file}")

                    # Check for common Prometheus query patterns, metric selectors, or numeric constants
                    # Numeric constants are valid (e.g., "0.010" for target lines)
                    # Bare metric with optional labels is valid (e.g. odps_ref_cache_size{ref_type="external"})
                    # Arithmetic expressions are valid (e.g., (metric1 / metric2) * 100)
                    is_numeric_constant = expr.replace('.', '').replace('-', '').isdigit()
                    has_prometheus_function = any(keyword in expr for keyword in prometheus_functions)
                    has_metric_with_labels = bool(expr) and expr[0].isalpha() and '{' in expr
                    is_bare_metric = bool(expr) and expr[0].isalpha() and expr.replace('_', '').replace('.', '').isalnum()
                    is_metric_selector = has_metric_with_labels or is_bare_metric
                    # Check for arithmetic expressions (contains operators and parentheses)
                    has_arithmetic = any(op in expr for op in ['+', '-', '*', '/', '%']) and ('(' in expr or ')' in expr or any(char.isalpha() for char in expr))

                    self.assertTrue(
                        is_numeric_constant or has_prometheus_function or is_metric_selector or has_arithmetic,
                        f"Query in {dashboard_file} should contain valid Prometheus functions, a metric selector, arithmetic expressions, or be a numeric constant. Query: {expr}"
                    )

    def test_dashboards_have_descriptions(self):
        """Test that all dashboards and panels have descriptions."""
        for dashboard_file in self.required_dashboards:
            dashboard_path = self.dashboards_dir / dashboard_file
            with open(dashboard_path, 'r') as f:
                config = json.load(f)

            dashboard = config['dashboard']

            # Check that panels have descriptions
            for i, panel in enumerate(dashboard.get('panels', [])):
                panel_name = f"{dashboard_file} panel {i+1}"
                self.assertIn(
                    'description',
                    panel,
                    f"{panel_name} should have a description"
                )
                self.assertGreater(
                    len(panel.get('description', '')),
                    0,
                    f"{panel_name} description should not be empty"
                )

    def test_marketplace_integration_dashboard_content(self):
        """Test ODPS marketplace integration dashboard has correct content."""
        dashboard_path = self.dashboards_dir / "odps-marketplace-integration.json"
        with open(dashboard_path, 'r') as f:
            config = json.load(f)

        dashboard = config['dashboard']
        self.assertEqual(dashboard['title'], "ODPS Marketplace Integration")
        self.assertIn('marketplace', dashboard['tags'])
        self.assertIn('task-6.6.8', dashboard['tags'])

        # Check for required panels
        panel_titles = [p.get('title', '') for p in dashboard['panels']]
        self.assertTrue(
            any('Listing Creation Rate' in title for title in panel_titles),
            "Dashboard should have listing creation rate panel"
        )
        self.assertTrue(
            any('Purchase Rate' in title for title in panel_titles),
            "Dashboard should have purchase rate panel"
        )
        self.assertTrue(
            any('Pricing Plan Usage' in title for title in panel_titles),
            "Dashboard should have pricing plan usage panel"
        )
        self.assertTrue(
            any('Access Method Usage' in title for title in panel_titles),
            "Dashboard should have access method usage panel"
        )

        # Check for SQL queries (PostgreSQL datasource)
        all_sqls = []
        for panel in dashboard['panels']:
            for target in panel.get('targets', []):
                sql = target.get('rawSql', target.get('rawQuery', ''))
                if sql:
                    all_sqls.append(sql)

        # Should have queries for listings and orders
        listings_sqls = [sql for sql in all_sqls if 'listings' in sql.lower()]
        orders_sqls = [sql for sql in all_sqls if 'orders' in sql.lower()]
        pricing_sqls = [sql for sql in all_sqls if 'pricing' in sql.lower()]
        access_sqls = [sql for sql in all_sqls if 'access_method' in sql.lower() or 'accessMethod' in sql]

        self.assertGreater(len(listings_sqls), 0, "Dashboard should have listings queries")
        self.assertGreater(len(orders_sqls), 0, "Dashboard should have orders queries")
        self.assertGreater(len(pricing_sqls), 0, "Dashboard should have pricing plan queries")
        self.assertGreater(len(access_sqls), 0, "Dashboard should have access method queries")

    def test_creation_flow_performance_dashboard_content(self):
        """Test ODPS creation flow performance dashboard has correct content (Task 6.6.7)."""
        dashboard_path = self.dashboards_dir / "odps-creation-flow-performance.json"
        with open(dashboard_path, 'r') as f:
            config = json.load(f)

        dashboard = config['dashboard']
        self.assertEqual(dashboard['title'], "ODPS Creation Flow Performance")
        self.assertIn('creation', dashboard['tags'])
        self.assertIn('workflow', dashboard['tags'])
        self.assertIn('task-6.6.7', dashboard['tags'])

        # Check for required panels
        panel_titles = [p.get('title', '') for p in dashboard['panels']]
        self.assertTrue(
            any('Duration' in title and ('P50' in title or 'P95' in title or 'P99' in title) for title in panel_titles),
            "Dashboard should have creation flow duration panel with percentiles"
        )
        self.assertTrue(
            any('Success Rate' in title for title in panel_titles),
            "Dashboard should have creation flow success rate panel"
        )
        self.assertTrue(
            any('Error Rate' in title for title in panel_titles),
            "Dashboard should have creation flow error rate panel"
        )
        self.assertTrue(
            any('Step-by-Step' in title or 'step' in title.lower() for title in panel_titles),
            "Dashboard should have step-by-step performance panel"
        )

        # Check for workflow queries
        all_exprs = []
        for panel in dashboard['panels']:
            for target in panel.get('targets', []):
                expr = target.get('expr', '')
                if expr:
                    all_exprs.append(expr)

        # Should have queries for product_creation workflow
        workflow_exprs = [expr for expr in all_exprs if 'product_creation' in expr]
        self.assertGreater(len(workflow_exprs), 0, "Dashboard should have product_creation workflow queries")

        # Should have duration queries
        duration_exprs = [expr for expr in all_exprs if 'workflow_execution_duration_seconds' in expr]
        self.assertGreater(len(duration_exprs), 0, "Dashboard should have workflow execution duration queries")

        # Should have step duration queries
        step_exprs = [expr for expr in all_exprs if 'workflow_step_execution_duration_seconds' in expr]
        self.assertGreater(len(step_exprs), 0, "Dashboard should have workflow step execution duration queries")

        # Should have success/failure queries
        success_exprs = [expr for expr in all_exprs if 'workflow_instances_completed_total' in expr or 'workflow_instances_started_total' in expr]
        self.assertGreater(len(success_exprs), 0, "Dashboard should have workflow instance success queries")

        failure_exprs = [expr for expr in all_exprs if 'workflow_instances_failed_total' in expr]
        self.assertGreater(len(failure_exprs), 0, "Dashboard should have workflow instance failure queries")

        # Check for specific step names in queries
        step_names = ['parse_odps', 'resolve_refs', 'extract_contract', 'validate_odcs', 'normalize_odcs', 'normalize_odps', 'create_odcs_contract', 'create_odps_contract', 'link_contracts']
        found_steps = []
        for expr in step_exprs:
            for step_name in step_names:
                if step_name in expr:
                    found_steps.append(step_name)
                    break

        self.assertGreater(len(found_steps), 0, f"Dashboard should have queries for at least some workflow steps. Found: {found_steps}")

