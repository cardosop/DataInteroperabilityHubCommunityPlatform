"""TDD pins for the U4 observability artifacts (openspec
add-databricks-uc-write task 2.8) — approval-pipeline alerts +
dashboard (the 1.10 convention: REAL artifact files, drift pins against
the metrics module's registered names)."""

import json
from pathlib import Path

import yaml
from django.test import TestCase

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


class UcApprovalAlertsTests(TestCase):
    def setUp(self):
        self.alerts_file = (
            PROJECT_ROOT / "monitoring" / "prometheus" / "alerts" / "databricks-uc-approvals.yml"
        )

    def test_alerts_file_exists_and_parses(self):
        assert self.alerts_file.is_file(), "databricks-uc-approvals.yml must exist"
        config = yaml.safe_load(self.alerts_file.read_text())
        group = next(g for g in config["groups"] if g["name"] == "databricks_uc_approvals")
        assert len(group["rules"]) == 2

    def test_backlog_alert_uses_the_pending_gauge(self):
        config = yaml.safe_load(self.alerts_file.read_text())
        rule = next(
            r
            for g in config["groups"]
            for r in g["rules"]
            if r["alert"] == "DatabricksUCApprovalBacklog"
        )
        assert "databricks_uc_change_pending_approvals" in rule["expr"]

    def test_stale_alert_uses_the_oldest_pending_gauge(self):
        config = yaml.safe_load(self.alerts_file.read_text())
        rule = next(
            r
            for g in config["groups"]
            for r in g["rules"]
            if r["alert"] == "DatabricksUCApprovalStale"
        )
        assert "databricks_uc_change_oldest_pending_seconds" in rule["expr"]


class UcApprovalDashboardTests(TestCase):
    def setUp(self):
        self.dashboard_file = (
            PROJECT_ROOT / "monitoring" / "grafana" / "dashboards" / "databricks-uc-approvals.json"
        )

    def test_dashboard_exists_and_parses(self):
        assert self.dashboard_file.is_file(), "databricks-uc-approvals.json must exist"
        payload = json.loads(self.dashboard_file.read_text())
        assert payload["dashboard"]["uid"] == "databricks-uc-approvals"
        assert len(payload["dashboard"]["panels"]) >= 4

    def test_dashboard_metric_names_match_the_emitter(self):
        from hub.apps.databricks_admin import metrics

        emitted = {
            metrics.databricks_uc_change_requests_total._name,
            metrics.databricks_uc_approval_duration_seconds._name,
            metrics.databricks_uc_change_pending_approvals._name,
            metrics.databricks_uc_change_oldest_pending_seconds._name,
        }
        artifact_text = (
            self.dashboard_file.read_text()
            + (
                PROJECT_ROOT
                / "monitoring"
                / "prometheus"
                / "alerts"
                / "databricks-uc-approvals.yml"
            ).read_text()
        )
        for name in emitted:
            assert name in artifact_text, (
                f"metric {name} is emitted but absent from the 2.8 artifacts"
            )
