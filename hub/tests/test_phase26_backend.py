"""
Phase 26 Backend Tests — API & Service Layer Updates

Covers:
  26.8.1  spec_version query parameter + v3.1.0 acceptance
  26.8.2  Relationship target_contract URL ref resolution
  26.8.3  v3.1.0 normalization metrics + fallback alert metric
  26.17   Observability: alerts, dashboard, promtail, metric wiring
"""

from unittest import TestCase

# ======================================================================
# 26.8.1 — spec_version filter parameter
# ======================================================================


class SpecVersionFilterParameterTest(TestCase):
    """Verify the spec_version OpenAPI parameter is declared."""

    def test_spec_version_in_openapi_parameters(self):
        """The ContractViewSet list action should declare spec_version."""
        # The @extend_schema parameters are on the class; check the
        # schema_decorator attached by drf-spectacular
        import inspect

        from hub.apps.contracts.views import ContractViewSet

        inspect.getsource(ContractViewSet)
        # The parameter is on the parent extend_schema decorator,
        # so check the views.py source directly
        from hub.apps.contracts import views

        view_source = inspect.getsource(views)
        assert "spec_version" in view_source, (
            "spec_version parameter should be declared in views.py"
        )

    def test_spec_version_filter_in_queryset_logic(self):
        """The get_queryset method should filter by spec_version."""
        import inspect

        from hub.apps.contracts import views

        source = inspect.getsource(views)
        assert (
            "original_spec_version=spec_version" in source
            or "original_spec_version=spec_version" in source
        ), "get_queryset should filter by original_spec_version"


# ======================================================================
# 26.8.2 — Relationship target_contract URL resolution
# ======================================================================


class RelationshipRefResolverTest(TestCase):
    """Test resolve_relationship_target_refs method."""

    def test_method_exists_on_ref_resolver(self):
        from hub.apps.contracts.ref_resolver import RefResolver

        resolver = RefResolver(tenant_id="test", user_id="test")
        assert hasattr(resolver, "resolve_relationship_target_refs")

    def test_non_url_targets_untouched(self):
        """Plain string targets should not be modified."""
        from hub.apps.contracts.ref_resolver import RefResolver

        resolver = RefResolver(tenant_id="test", user_id="test")
        hub = {
            "models": [
                {
                    "name": "orders",
                    "fields": [],
                    "relationships": [
                        {
                            "type": "foreignKey",
                            "source": ["customer_id"],
                            "target_contract": "customers-contract",
                            "target_model": "customers",
                            "target_properties": ["id"],
                        }
                    ],
                }
            ],
            "schema": {"fields": []},
        }
        result, warnings = resolver.resolve_relationship_target_refs(hub)
        rel = result["models"][0]["relationships"][0]
        assert rel["target_contract"] == "customers-contract"
        assert "_resolved_target" not in rel
        assert len(warnings) == 0

    def test_uuid_targets_untouched(self):
        """UUID targets should not be treated as URLs."""
        from hub.apps.contracts.ref_resolver import RefResolver

        resolver = RefResolver(tenant_id="test", user_id="test")
        hub = {
            "models": [
                {
                    "name": "orders",
                    "fields": [],
                    "relationships": [
                        {
                            "type": "foreignKey",
                            "source": ["id"],
                            "target_contract": "550e8400-e29b-41d4-a716-446655440000",
                            "target_model": "customers",
                            "target_properties": ["id"],
                        }
                    ],
                }
            ],
            "schema": {"fields": []},
        }
        result, warnings = resolver.resolve_relationship_target_refs(hub)
        rel = result["models"][0]["relationships"][0]
        assert "_resolved_target" not in rel
        assert len(warnings) == 0

    def test_url_target_produces_warning_on_failure(self):
        """URL targets that can't be fetched produce a warning, not error."""
        from hub.apps.contracts.ref_resolver import RefResolver

        resolver = RefResolver(tenant_id="test", user_id="test")
        hub = {
            "models": [
                {
                    "name": "orders",
                    "fields": [],
                    "relationships": [
                        {
                            "type": "foreignKey",
                            "source": ["id"],
                            "target_contract": "https://nonexistent.example.com/contract.json",
                            "target_model": "customers",
                            "target_properties": ["id"],
                        }
                    ],
                }
            ],
            "schema": {"fields": []},
        }
        _result, warnings = resolver.resolve_relationship_target_refs(hub)
        # Should produce a warning, not raise
        assert len(warnings) >= 1
        assert "nonexistent.example.com" in warnings[0]

    def test_no_relationships_no_error(self):
        """Hub contract without relationships should not error."""
        from hub.apps.contracts.ref_resolver import RefResolver

        resolver = RefResolver(tenant_id="test", user_id="test")
        hub = {
            "models": [{"name": "m", "fields": []}],
            "schema": {"fields": []},
        }
        _result, warnings = resolver.resolve_relationship_target_refs(hub)
        assert len(warnings) == 0

    def test_schema_level_relationships_resolved(self):
        """Schema-level relationships should also be walked."""
        from hub.apps.contracts.ref_resolver import RefResolver

        resolver = RefResolver(tenant_id="test", user_id="test")
        hub = {
            "models": [],
            "schema": {
                "fields": [],
                "relationships": [
                    {
                        "type": "foreignKey",
                        "source": ["id"],
                        "target_contract": "plain-name",
                        "target_properties": ["id"],
                    }
                ],
            },
        }
        result, warnings = resolver.resolve_relationship_target_refs(hub)
        assert len(warnings) == 0
        rel = result["schema"]["relationships"][0]
        assert rel["target_contract"] == "plain-name"


# ======================================================================
# 26.8.3 — Normalization metrics
# ======================================================================


class NormalizationMetricsTest(TestCase):
    """Test v3.1.0-specific metric recording functions."""

    def test_record_v310_relationships_count(self):
        from hub.apps.contracts.normalization_metrics import (
            record_v310_relationships_count,
        )

        hub = {
            "models": [
                {
                    "name": "orders",
                    "relationships": [
                        {"type": "fk", "source": ["a"], "target_properties": ["b"]},
                        {"type": "fk", "source": ["c"], "target_properties": ["d"]},
                    ],
                },
            ],
            "schema": {
                "relationships": [
                    {"type": "fk", "source": ["e"], "target_properties": ["f"]},
                ],
            },
        }
        # Should not raise
        record_v310_relationships_count(hub, tenant_id="test")

    def test_record_v310_relationships_count_empty(self):
        from hub.apps.contracts.normalization_metrics import (
            record_v310_relationships_count,
        )

        # No relationships
        record_v310_relationships_count({"models": []}, tenant_id="test")

    def test_record_v310_fallback(self):
        from hub.apps.contracts.normalization_metrics import (
            record_v310_fallback,
        )

        # Should not raise
        record_v310_fallback("ODCSNormalizerV3_0_2", tenant_id="test")

    def test_metrics_constants_exist(self):
        """Verify the new metrics are importable."""
        from hub.apps.observability.otel_metrics import (
            odcs_v310_fallback_total,
            odcs_v310_relationships_count,
        )

        assert odcs_v310_relationships_count is not None
        assert odcs_v310_fallback_total is not None


class PrometheusAlertTest(TestCase):
    """Verify the v3.1.0 fallback alert exists in alerts.yml."""

    def test_alert_rule_exists(self):
        import os

        alerts_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "monitoring",
            "prometheus",
            "alerts.yml",
        )
        with open(alerts_path) as f:
            content = f.read()
        assert "ODCSv310NormalizationFallback" in content
        assert "odcs_v310_fallback_total" in content
        assert "severity: critical" in content


# ======================================================================
# 26.17 — Observability: Metrics, Alerts & Dashboards
# ======================================================================

import json
import os

import yaml


def _project_root():
    """Return the project root (two levels up from hub/tests/)."""
    return os.path.join(os.path.dirname(__file__), "..", "..")


def _load_alerts_yaml():
    path = os.path.join(_project_root(), "monitoring", "prometheus", "alerts.yml")
    with open(path) as f:
        return yaml.safe_load(f)


def _load_promtail_yaml():
    path = os.path.join(_project_root(), "monitoring", "promtail", "promtail.yaml")
    with open(path) as f:
        return yaml.safe_load(f)


def _load_dashboard_json():
    path = os.path.join(
        _project_root(),
        "monitoring",
        "grafana",
        "dashboards",
        "contract-normalization.json",
    )
    with open(path) as f:
        return json.load(f)


def _find_alert(alerts_data, alert_name):
    """Find an alert rule by name across all groups."""
    for group in alerts_data.get("groups", []):
        for rule in group.get("rules", []):
            if rule.get("alert") == alert_name:
                return rule, group["name"]
    return None, None


class AlertsHubContractGroupTest(TestCase):
    """26.17.1 — Verify hub_contract_alerts group and its 3 rules."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.alerts = _load_alerts_yaml()

    def test_hub_contract_alerts_group_exists(self):
        names = [g["name"] for g in self.alerts["groups"]]
        self.assertIn("hub_contract_alerts", names)

    def test_hub_contract_alerts_has_3_rules(self):
        for group in self.alerts["groups"]:
            if group["name"] == "hub_contract_alerts":
                self.assertEqual(len(group["rules"]), 3)
                break

    # -- ODCSv310NormalizationFallback --

    def test_fallback_alert_in_contract_group(self):
        rule, group = _find_alert(self.alerts, "ODCSv310NormalizationFallback")
        self.assertIsNotNone(rule)
        self.assertEqual(group, "hub_contract_alerts")

    def test_fallback_alert_uses_real_metric(self):
        """Must reference odcs_v310_fallback_total (not phantom metric)."""
        rule, _ = _find_alert(self.alerts, "ODCSv310NormalizationFallback")
        self.assertIn("odcs_v310_fallback_total", rule["expr"])

    def test_fallback_alert_does_not_reference_phantom(self):
        rule, _ = _find_alert(self.alerts, "ODCSv310NormalizationFallback")
        self.assertNotIn("normalization_operations_total", rule["expr"])

    def test_fallback_alert_severity_critical(self):
        rule, _ = _find_alert(self.alerts, "ODCSv310NormalizationFallback")
        self.assertEqual(rule["labels"]["severity"], "critical")
        self.assertEqual(rule["labels"]["priority"], "P1")

    # -- HubContractBackfillStalled --

    def test_backfill_alert_exists(self):
        rule, group = _find_alert(self.alerts, "HubContractBackfillStalled")
        self.assertIsNotNone(rule)
        self.assertEqual(group, "hub_contract_alerts")

    def test_backfill_alert_uses_real_metric(self):
        rule, _ = _find_alert(self.alerts, "HubContractBackfillStalled")
        self.assertIn("normalization_backfill_remaining", rule["expr"])

    def test_backfill_alert_for_2h(self):
        rule, _ = _find_alert(self.alerts, "HubContractBackfillStalled")
        self.assertEqual(rule["for"], "2h")

    def test_backfill_alert_severity_warning(self):
        rule, _ = _find_alert(self.alerts, "HubContractBackfillStalled")
        self.assertEqual(rule["labels"]["severity"], "warning")
        self.assertEqual(rule["labels"]["priority"], "P2")

    # -- ContractExportDowngradeRate --

    def test_downgrade_alert_exists(self):
        rule, group = _find_alert(self.alerts, "ContractExportDowngradeRate")
        self.assertIsNotNone(rule)
        self.assertEqual(group, "hub_contract_alerts")

    def test_downgrade_alert_uses_real_metric(self):
        rule, _ = _find_alert(self.alerts, "ContractExportDowngradeRate")
        self.assertIn("contract_export_total", rule["expr"])
        self.assertIn('downgrade="true"', rule["expr"])

    def test_downgrade_alert_severity_warning(self):
        rule, _ = _find_alert(self.alerts, "ContractExportDowngradeRate")
        self.assertEqual(rule["labels"]["severity"], "warning")
        self.assertEqual(rule["labels"]["priority"], "P3")

    # -- No duplicate in hub_service_alerts --

    def test_no_duplicate_fallback_in_service_alerts(self):
        """The old ODCSv310NormalizationFallback in hub_service_alerts must be removed."""
        for group in self.alerts["groups"]:
            if group["name"] == "hub_service_alerts":
                alert_names = [r.get("alert") for r in group["rules"]]
                self.assertNotIn(
                    "ODCSv310NormalizationFallback",
                    alert_names,
                    "Duplicate fallback alert still in hub_service_alerts",
                )
                break


class AlertMetricsExistTest(TestCase):
    """Verify that every metric referenced in hub_contract_alerts
    is defined in otel_metrics.py and can be imported."""

    def test_odcs_v310_fallback_total_importable(self):
        from hub.apps.observability.otel_metrics import odcs_v310_fallback_total

        self.assertIsNotNone(odcs_v310_fallback_total)

    def test_normalization_backfill_remaining_importable(self):
        from hub.apps.observability.otel_metrics import normalization_backfill_remaining

        self.assertIsNotNone(normalization_backfill_remaining)

    def test_contract_export_total_importable(self):
        from hub.apps.observability.otel_metrics import contract_export_total

        self.assertIsNotNone(contract_export_total)


class BackfillGaugeWiringTest(TestCase):
    """Verify tasks.py emits the normalization_backfill_remaining gauge."""

    def test_tasks_imports_backfill_metric(self):
        import inspect

        from hub.apps.contracts import tasks

        source = inspect.getsource(tasks)
        self.assertIn("normalization_backfill_remaining", source)

    def test_tasks_calls_set_backfill_remaining(self):
        import inspect

        from hub.apps.contracts import tasks

        source = inspect.getsource(tasks)
        self.assertIn("_set_backfill_remaining", source)

    def test_set_backfill_remaining_function_exists(self):
        from hub.apps.contracts.tasks import _set_backfill_remaining

        self.assertTrue(callable(_set_backfill_remaining))

    def test_set_backfill_remaining_no_error(self):
        """Calling with 0 remaining should not raise."""
        from hub.apps.contracts.tasks import _set_backfill_remaining

        _set_backfill_remaining(0, tenant_id="test")


class ExportMetricWiringTest(TestCase):
    """Verify views_export.py emits contract_export_total with downgrade label."""

    def test_views_export_imports_contract_export_total(self):
        import inspect

        from hub.apps.contracts import views_export

        source = inspect.getsource(views_export)
        self.assertIn("contract_export_total", source)

    def test_views_export_uses_downgrade_label(self):
        import inspect

        from hub.apps.contracts import views_export

        source = inspect.getsource(views_export)
        self.assertIn('downgrade="true"', source)
        self.assertIn('downgrade="false"', source)


class PromtailSpecVersionLabelTest(TestCase):
    """26.17.2 — Verify spec_version label extraction in promtail.yaml."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = _load_promtail_yaml()

    def _get_docker_stages(self):
        for sc in self.config.get("scrape_configs", []):
            if sc.get("job_name") in ("containers", "docker"):
                return sc.get("pipeline_stages", [])
        self.fail("containers/docker scrape config not found")

    def test_match_stage_exists(self):
        stages = self._get_docker_stages()
        match_stages = [s for s in stages if "match" in s]
        selectors = [s["match"]["selector"] for s in match_stages]
        found = any("hub-api" in sel or "worker" in sel for sel in selectors)
        self.assertTrue(found, f"No match stage for hub-api/worker. Selectors: {selectors}")

    def test_match_stage_has_regex_for_spec_version(self):
        stages = self._get_docker_stages()
        for stage in stages:
            if "match" not in stage:
                continue
            sel = stage["match"].get("selector", "")
            if "hub-api" in sel or "worker" in sel:
                inner = stage["match"].get("stages", [])
                regex_exprs = [s["regex"]["expression"] for s in inner if "regex" in s]
                self.assertTrue(
                    len(regex_exprs) > 0,
                    "match stage should contain a regex sub-stage",
                )
                combined = " ".join(regex_exprs)
                # YAML loads '3\\.1\\.0' as literal double-
                # backslash-dot.  Strip all backslashes for a
                # simple version presence check.
                stripped = combined.replace("\\", "")
                self.assertIn(
                    "3.1.0",
                    stripped,
                    f"3.1.0 not found in regex: {combined}",
                )
                self.assertIn(
                    "bitol-1.0.0",
                    stripped,
                    f"bitol-1.0.0 not found in regex: {combined}",
                )
                return
        self.fail("spec_version match stage not found")

    def test_match_stage_promotes_contract_spec_version_label(self):
        stages = self._get_docker_stages()
        for stage in stages:
            if "match" not in stage:
                continue
            sel = stage["match"].get("selector", "")
            if "hub-api" in sel or "worker" in sel:
                inner = stage["match"].get("stages", [])
                label_stages = [s for s in inner if "labels" in s]
                all_labels = {}
                for ls in label_stages:
                    all_labels.update(ls["labels"])
                self.assertIn("contract_spec_version", all_labels)
                return
        self.fail("contract_spec_version label not found")


class DashboardPanelTest(TestCase):
    """26.17.3 — Verify dashboard panels reference real metrics."""

    PHANTOM_METRICS = [
        "normalization_operations_total",
        "hub_contract_spec_version",
        "normalization_backfill_remaining_total",
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dashboard = _load_dashboard_json()
        cls.panels = cls.dashboard["dashboard"]["panels"]

    def test_dashboard_has_6_panels(self):
        self.assertEqual(len(self.panels), 6)

    def test_no_phantom_metrics_in_any_panel(self):
        """No panel should reference metrics that don't exist."""
        for panel in self.panels:
            for target in panel.get("targets", []):
                expr = target.get("expr", "")
                for phantom in self.PHANTOM_METRICS:
                    self.assertNotIn(
                        phantom,
                        expr,
                        f"Panel '{panel['title']}' references phantom "
                        f"metric '{phantom}' in expr: {expr}",
                    )

    def test_panel_normalization_ops_uses_odcs_normalization_total(self):
        panel = self.panels[0]
        self.assertEqual(panel["title"], "Normalization Operations by Spec Version")
        expr = panel["targets"][0]["expr"]
        self.assertIn("odcs_normalization_total", expr)

    def test_panel_v310_count_uses_version_distribution(self):
        panel = self.panels[1]
        expr = panel["targets"][0]["expr"]
        self.assertIn("odcs_version_distribution_total", expr)
        self.assertIn('version="3.1.0"', expr)

    def test_panel_export_downgrade_uses_contract_export_total(self):
        panel = self.panels[2]
        expr = panel["targets"][0]["expr"]
        self.assertIn("contract_export_total", expr)
        self.assertIn('downgrade="true"', expr)

    def test_panel_failures_uses_odcs_normalization_total(self):
        panel = self.panels[3]
        expr = panel["targets"][0]["expr"]
        self.assertIn("odcs_normalization_total", expr)
        self.assertIn('version="3.1.0"', expr)
        self.assertIn('status="failure"', expr)

    def test_panel_backfill_uses_normalization_backfill_remaining(self):
        panel = self.panels[4]
        expr = panel["targets"][0]["expr"]
        self.assertIn("normalization_backfill_remaining", expr)
        self.assertNotIn("_total", expr)

    def test_panel_fallback_uses_odcs_v310_fallback_total(self):
        panel = self.panels[5]
        expr = panel["targets"][0]["expr"]
        self.assertIn("odcs_v310_fallback_total", expr)

    def test_panel_fallback_color_is_red(self):
        panel = self.panels[5]
        color = panel["fieldConfig"]["defaults"]["color"]
        self.assertEqual(color["fixedColor"], "red")
