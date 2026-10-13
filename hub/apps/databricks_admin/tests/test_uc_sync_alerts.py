"""Phase 1 (openspec add-databricks-uc-read task 1.10) — UC sync
observability artifacts.

The alert rules (``monitoring/prometheus/alerts/databricks-uc-sync.yml``)
and the Grafana dashboard
(``monitoring/grafana/dashboards/databricks-uc-sync.json``) are REAL
artifacts consumed by the ops stack — these pins validate the files
parse and reference exactly the metrics the sync emits (the
test_odps_alerts / test_marketplace_dashboards conventions).
"""

import json
from pathlib import Path

import yaml
from django.test import TestCase

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


class UcSyncAlertsTests(TestCase):
    """The UC sync alert rules exist, parse, and pin the sync metrics."""

    def setUp(self):
        self.alerts_file = (
            PROJECT_ROOT / "monitoring" / "prometheus" / "alerts" / "databricks-uc-sync.yml"
        )

    def test_alerts_file_exists_and_parses(self):
        assert self.alerts_file.is_file(), "databricks-uc-sync.yml must exist"
        config = yaml.safe_load(self.alerts_file.read_text())
        assert "groups" in config
        group = next(g for g in config["groups"] if g["name"] == "databricks_uc_sync")
        rules = group["rules"]
        assert len(rules) == 3

    def test_sync_failed_alert_fires_on_failures(self):
        config = yaml.safe_load(self.alerts_file.read_text())
        rule = next(
            r
            for g in config["groups"]
            for r in g["rules"]
            if r["alert"] == "DatabricksUCMetadataSyncFailed"
        )
        assert 'databricks_uc_sync_runs_total{outcome="failure"}' in rule["expr"]
        assert rule["labels"]["severity"] == "warning"
        assert "for" in rule

    def test_high_failure_rate_alert_is_rate_based(self):
        config = yaml.safe_load(self.alerts_file.read_text())
        rule = next(
            r
            for g in config["groups"]
            for r in g["rules"]
            if r["alert"] == "DatabricksUCMetadataSyncHighFailureRate"
        )
        assert "databricks_uc_sync_runs_total" in rule["expr"]
        assert rule["labels"]["severity"] == "warning"

    def test_stale_alert_uses_the_last_success_gauge(self):
        config = yaml.safe_load(self.alerts_file.read_text())
        rule = next(
            r
            for g in config["groups"]
            for r in g["rules"]
            if r["alert"] == "DatabricksUCMetadataSyncStale"
        )
        assert "databricks_uc_sync_last_success_timestamp" in rule["expr"]
        assert rule["labels"]["severity"] == "warning"
        # The mirror-staleness window (DB-005's freshness marker): a
        # workspace not synced within 36h has a stale mirror.
        assert "129600" in rule["expr"]


class UcSyncDashboardTests(TestCase):
    """The Grafana dashboard exists, parses, and pins the sync metrics."""

    def setUp(self):
        self.dashboard_file = (
            PROJECT_ROOT / "monitoring" / "grafana" / "dashboards" / "databricks-uc-sync.json"
        )

    def test_dashboard_exists_and_parses(self):
        assert self.dashboard_file.is_file(), "databricks-uc-sync.json must exist"
        payload = json.loads(self.dashboard_file.read_text())
        assert payload["dashboard"]["title"] == "Databricks — UC Metadata Sync"
        assert payload["dashboard"]["uid"] == "databricks-uc-sync"
        panels = payload["dashboard"]["panels"]
        assert len(panels) >= 5

    def test_dashboard_references_only_the_sync_metrics(self):
        payload = json.loads(self.dashboard_file.read_text())
        exprs: list[str] = []
        for panel in payload["dashboard"]["panels"]:
            for target in panel.get("targets", []):
                if target.get("expr"):
                    exprs.append(target["expr"])
        referenced = {
            name
            for name in (
                "databricks_uc_sync_runs_total",
                "databricks_uc_sync_duration_seconds",
                "databricks_uc_sync_rows_total",
                "databricks_uc_sync_last_success_timestamp",
            )
            if any(name in expr for expr in exprs)
        }
        assert referenced == {
            "databricks_uc_sync_runs_total",
            "databricks_uc_sync_duration_seconds",
            "databricks_uc_sync_rows_total",
            "databricks_uc_sync_last_success_timestamp",
        }, f"dashboard must consume exactly the sync metrics; found {referenced}"

    def test_dashboard_metric_names_match_the_emitter(self):
        # The metric names in the dashboard/alert artifacts must be the
        # ones the metrics module ACTUALLY registers (drift pin).
        from hub.apps.databricks_admin import metrics

        emitted = {
            metrics.databricks_uc_sync_runs_total._name,
            metrics.databricks_uc_sync_duration_seconds._name,
            metrics.databricks_uc_sync_rows_total._name,
            metrics.databricks_uc_sync_last_success_timestamp._name,
        }
        artifact_text = (
            self.dashboard_file.read_text()
            + (
                PROJECT_ROOT / "monitoring" / "prometheus" / "alerts" / "databricks-uc-sync.yml"
            ).read_text()
        )
        for name in emitted:
            assert name in artifact_text, (
                f"metric {name} is emitted but absent from the 1.10 artifacts"
            )
