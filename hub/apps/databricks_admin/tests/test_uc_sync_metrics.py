"""Phase 1 (openspec add-databricks-uc-read task 1.10) — UC sync metrics.

The sync emits Prometheus metrics through the ``hub.apps.databricks_admin.
metrics`` record wrappers (the search/metrics module-boundary convention):
patches target the record functions ONLY — the sync code path is the real
one (real Postgres mirrors, real local HTTP, real client).

Metrics (consumed by the 1.10 dashboard + alerts):
- ``databricks_uc_sync_runs_total{outcome}`` — success/failure/skipped
- ``databricks_uc_sync_duration_seconds`` — per-workspace sync duration
- ``databricks_uc_sync_rows_total{operation}`` — created/updated/deleted
- ``databricks_uc_sync_last_success_timestamp{tenant_id, workspace}`` —
  the staleness anchor for the DatabricksUCMetadataSyncStale alert
"""

import uuid
from unittest.mock import patch

import pytest
from django.test import TestCase

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests.test_uc_sync import (
    _estate,
    _local_client_factory,
    _make_approval,
    _make_credential,
    _make_workspace,
    _routes_for,
    _start_estate_server,
    _stop_estate_server,
)
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _make_user
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


class UcSyncMetricsEmissionTests(TestCase):
    """Every sync outcome records its metric; rows are recorded per
    operation; success stamps the last-success gauge."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.user = _make_user(
            self.tenant, f"ucs-metric-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        self.workspace = _make_workspace(self.tenant)
        self.approval = _make_approval(self.tenant, self.user)
        self._server, self.port = _start_estate_server()
        self.addCleanup(_stop_estate_server, self._server)

        import hub.apps.databricks_admin.uc_sync as uc_sync_module

        self._factory = _local_client_factory(self.port)
        self._original_factory = uc_sync_module._build_uc_client
        uc_sync_module._build_uc_client = self._factory
        self.addCleanup(setattr, uc_sync_module, "_build_uc_client", self._original_factory)
        from hub.apps.databricks_admin.tests._http import UCEstateHandler

        UCEstateHandler.routes = _routes_for(_estate())

    def test_success_records_outcome_duration_rows_and_timestamp(self):
        from unittest.mock import ANY

        from hub.apps.databricks_admin.uc_sync import sync_uc_workspace

        _make_credential(self.workspace, self.approval)
        with (
            patch("hub.apps.databricks_admin.metrics.record_sync_outcome") as outcome,
            patch("hub.apps.databricks_admin.metrics.record_sync_duration") as duration,
            patch("hub.apps.databricks_admin.metrics.record_sync_rows") as rows,
            patch("hub.apps.databricks_admin.metrics.record_sync_success_timestamp") as timestamp,
        ):
            sync_uc_workspace(self.workspace)

        outcome.assert_called_once_with("success", tenant_id=str(self.tenant.id))
        duration.assert_called_once()
        assert duration.call_args.kwargs["seconds"] >= 0
        # All three operations are recorded (the record function skips
        # non-positive counts internally); the fresh estate created 9
        # rows, nothing else.
        rows_calls = {call.args[0]: call for call in rows.call_args_list}
        assert set(rows_calls) == {"created", "updated", "deleted"}
        assert rows_calls["created"].args[1] == 9
        assert rows_calls["updated"].args[1] == 0
        assert rows_calls["deleted"].args[1] == 0
        timestamp.assert_called_once_with(
            tenant_id=str(self.tenant.id), workspace_id=str(self.workspace.id), value=ANY
        )

    def test_failure_records_the_failure_outcome(self):
        from hub.apps.databricks_admin.client import DatabricksApiError
        from hub.apps.databricks_admin.tests._http import UCEstateHandler
        from hub.apps.databricks_admin.uc_sync import sync_uc_workspace

        _make_credential(self.workspace, self.approval)
        # A scripted 5xx with the retry budget exhausted → the production
        # client raises AFTER retries — the real failure path.
        UCEstateHandler.status = 500
        UCEstateHandler.routes = _routes_for(_estate())
        with (
            patch("hub.apps.databricks_admin.metrics.record_sync_outcome") as outcome,
            patch("hub.apps.databricks_admin.metrics.record_sync_duration") as duration,
            pytest.raises(DatabricksApiError),
        ):
            sync_uc_workspace(self.workspace)
        UCEstateHandler.status = 200
        outcome.assert_called_once_with("failure", tenant_id=str(self.tenant.id))
        duration.assert_called_once()

    def test_skip_records_the_skipped_outcome(self):
        from hub.apps.databricks_admin.uc_sync import sync_uc_workspace

        # No credential at all → the fail-closed skip path (zero network).
        with (
            patch("hub.apps.databricks_admin.metrics.record_sync_outcome") as outcome,
            patch("hub.apps.databricks_admin.metrics.record_sync_duration") as duration,
            patch("hub.apps.databricks_admin.metrics.record_sync_rows") as rows,
            patch("hub.apps.databricks_admin.metrics.record_sync_success_timestamp") as timestamp,
        ):
            result = sync_uc_workspace(self.workspace)
        assert "skipped" in result
        outcome.assert_called_once_with("skipped", tenant_id=str(self.tenant.id))
        duration.assert_called_once()
        rows.assert_not_called()
        timestamp.assert_not_called()


class UcSyncMetricDefinitionTests(TestCase):
    """The metric objects exist with the documented names/labels."""

    def test_metric_definitions_are_registered(self):
        from hub.apps.databricks_admin import metrics

        for name in (
            "databricks_uc_sync_runs_total",
            "databricks_uc_sync_duration_seconds",
            "databricks_uc_sync_rows_total",
            "databricks_uc_sync_last_success_timestamp",
        ):
            assert hasattr(metrics, name), f"metric {name} missing"

    def test_real_metrics_can_be_incremented(self):
        # The REAL prometheus_client objects (registered in the process
        # registry) accept the documented labels without error.
        from hub.apps.databricks_admin import metrics

        metrics.record_sync_outcome("success", tenant_id="t")
        metrics.record_sync_duration(seconds=1.5)
        metrics.record_sync_rows("created", 3, tenant_id="t")
        metrics.record_sync_success_timestamp(tenant_id="t", workspace_id="w", value=1.0)

    def test_module_degrades_to_stubs_on_duplicate_registration(self):
        # prometheus_client raises ValueError when the SAME metric name is
        # registered twice (module re-import / dev autoreload). The metrics
        # module must degrade to no-op stubs instead of crashing the
        # import — observability is best-effort by contract, and the drift
        # pin in test_uc_sync_alerts reads the metric ``_name`` so the
        # stub must carry it.
        import importlib

        importlib.reload(importlib.import_module("hub.apps.databricks_admin.metrics"))

        from hub.apps.databricks_admin import metrics

        metrics.record_sync_outcome("success", tenant_id="t")
        metrics.record_sync_duration(seconds=1.5)
        metrics.record_sync_rows("created", 3, tenant_id="t")
        metrics.record_sync_success_timestamp(tenant_id="t", workspace_id="w", value=1.0)
        assert metrics.databricks_uc_sync_runs_total._name == "databricks_uc_sync_runs_total", (
            "the stub fallback must keep the registered metric name (the drift pin reads it)"
        )
