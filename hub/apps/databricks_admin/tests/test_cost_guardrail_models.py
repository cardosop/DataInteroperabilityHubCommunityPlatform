"""P7 (openspec add-databricks-cost-guardrails task 7.2) — the
DatabricksCostBudget + DatabricksCostLedger models + their RLS pairing
(design D1).

Model pins (real Postgres, django_db applies the actual migrations):
  - a fresh budget defaults UNLIMITED (NULL budget_units_per_hour) with
    the BLOCK enforcement mode + the DBU unit label,
  - the per-warehouse scope: a warehouse-bound budget scopes only that
    warehouse; a tenant-wide (warehouse NULL) budget is a separate row;
    the (tenant, warehouse) pair is unique with NULLS NOT DISTINCT — a
    second tenant-wide budget is refused by the constraint,
  - the cross-tenant guard: a budget referencing another tenant's
    warehouse is refused by clean(),
  - a non-positive budget is refused,
  - the ledger rows persist with the source attribution (all five source
    choices), an unknown source is refused, negative units are refused,
    recorded_at defaults to now.

RLS pins (the migration-scan convention, the 0.2 precedent): ONE
migration carries the CREATE POLICY for BOTH tables (the direct-FK
template with the per-table kill-switch GUCs) and the reverse SQL.
"""

import os
import re

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from tests.factories import TenantFactory


def _workspace(tenant, *, host=REAL_HOST):
    from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace

    return DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=f"ws-{host[:4]}",
        host=host,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
    )


def _warehouse(workspace, *, warehouse_id="wh-1", name="analytics"):
    from hub.apps.databricks_admin.models import DatabricksSqlWarehouse

    return DatabricksSqlWarehouse.objects.create(
        workspace=workspace,
        warehouse_id=warehouse_id,
        name=name,
        state="RUNNING",
        serverless=True,
    )


class DatabricksCostBudgetModelTests(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        self.workspace = _workspace(self.tenant)
        self.warehouse = _warehouse(self.workspace)

    def test_a_fresh_budget_defaults_unlimited_with_block_mode(self):
        from hub.apps.databricks_admin.models import DatabricksCostBudget

        budget = DatabricksCostBudget.objects.create(tenant=self.tenant)

        assert budget.budget_units_per_hour is None, "NULL = unlimited"
        assert budget.enforcement_mode == "BLOCK"
        assert budget.unit_label == "DBU"
        assert budget.warehouse is None

    def test_a_warehouse_scoped_budget_is_stored(self):
        from hub.apps.databricks_admin.models import DatabricksCostBudget

        budget = DatabricksCostBudget.objects.create(
            tenant=self.tenant,
            warehouse=self.warehouse,
            budget_units_per_hour=100,
        )

        budget.refresh_from_db()
        assert budget.warehouse_id == self.warehouse.id
        assert budget.budget_units_per_hour == 100

    def test_the_tenant_warehouse_pair_is_unique(self):
        from hub.apps.databricks_admin.models import DatabricksCostBudget

        DatabricksCostBudget.objects.create(
            tenant=self.tenant, warehouse=self.warehouse, budget_units_per_hour=100
        )
        # The model layer refuses first (full_clean → validate_unique)…
        with pytest.raises(ValidationError):
            DatabricksCostBudget.objects.create(
                tenant=self.tenant, warehouse=self.warehouse, budget_units_per_hour=200
            )
        # …and the DB constraint is the belt beneath (bulk_create skips clean).
        with pytest.raises(IntegrityError), transaction.atomic():
            DatabricksCostBudget.objects.bulk_create(
                [
                    DatabricksCostBudget(
                        tenant=self.tenant,
                        warehouse=self.warehouse,
                        budget_units_per_hour=200,
                    )
                ]
            )

    def test_a_second_tenant_wide_budget_is_refused(self):
        from hub.apps.databricks_admin.models import DatabricksCostBudget

        DatabricksCostBudget.objects.create(tenant=self.tenant, budget_units_per_hour=100)
        with pytest.raises(ValidationError):
            DatabricksCostBudget.objects.create(tenant=self.tenant, budget_units_per_hour=200)
        # The NULLS NOT DISTINCT DB belt beneath the model check.
        with pytest.raises(IntegrityError), transaction.atomic():
            DatabricksCostBudget.objects.bulk_create(
                [DatabricksCostBudget(tenant=self.tenant, budget_units_per_hour=200)]
            )

    def test_a_cross_tenant_warehouse_is_refused(self):
        from hub.apps.databricks_admin.models import DatabricksCostBudget

        other_tenant = TenantFactory.create_tenant()
        other_workspace = _workspace(other_tenant)
        other_warehouse = _warehouse(other_workspace, warehouse_id="wh-other")

        with pytest.raises(ValidationError):
            DatabricksCostBudget.objects.create(
                tenant=self.tenant,
                warehouse=other_warehouse,
                budget_units_per_hour=100,
            )

    def test_a_non_positive_budget_is_refused(self):
        from hub.apps.databricks_admin.models import DatabricksCostBudget

        with pytest.raises(ValidationError):
            DatabricksCostBudget.objects.create(tenant=self.tenant, budget_units_per_hour=0)


class DatabricksCostLedgerModelTests(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        self.workspace = _workspace(self.tenant)
        self.warehouse = _warehouse(self.workspace)

    def test_a_ledger_row_persists_with_source_attribution(self):
        from hub.apps.databricks_admin.models import DatabricksCostLedger

        row = DatabricksCostLedger.objects.create(
            tenant=self.tenant,
            workspace=self.workspace,
            warehouse=self.warehouse,
            source="query",
            units=12.5,
            meta={"query_id": "q-1"},
        )

        row.refresh_from_db()
        assert row.units == 12.5
        assert row.source == "query"
        assert row.unit_label == "DBU"
        assert row.workspace_id == self.workspace.id
        assert row.warehouse_id == self.warehouse.id
        assert row.meta == {"query_id": "q-1"}
        assert row.recorded_at is not None

    def test_all_source_choices_persist(self):
        from hub.apps.databricks_admin.models import DatabricksCostLedger

        for source in ("query", "export", "ingestion", "job", "billing_sync"):
            DatabricksCostLedger.objects.create(
                tenant=self.tenant, workspace=self.workspace, source=source, units=1
            )

        from hub.apps.databricks_admin.models import DatabricksCostLedger as Ledger

        assert Ledger.objects.filter(tenant=self.tenant).count() == 5

    def test_an_unknown_source_is_refused(self):
        from hub.apps.databricks_admin.models import DatabricksCostLedger

        with pytest.raises(ValidationError):
            DatabricksCostLedger.objects.create(
                tenant=self.tenant, workspace=self.workspace, source="guess", units=1
            )

    def test_negative_units_are_refused(self):
        from hub.apps.databricks_admin.models import DatabricksCostLedger

        with pytest.raises(ValidationError):
            DatabricksCostLedger.objects.create(
                tenant=self.tenant, workspace=self.workspace, source="query", units=-1
            )


class DatabricksCostGuardrailRLSPolicyTests(TestCase):
    """The CLAUDE.md pairing contract: the new tenant-scoped models ship
    their RLS CREATE POLICY in the same migration (design D1)."""

    def setUp(self):
        import hub.apps.databricks_admin

        app_dir = os.path.dirname(hub.apps.databricks_admin.__file__)
        mig_dir = os.path.join(app_dir, "migrations")
        texts = []
        for fname in sorted(os.listdir(mig_dir)):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            with open(os.path.join(mig_dir, fname), encoding="utf-8") as fh:
                texts.append(fh.read())
        self.migration_text = "\n".join(texts)

    def test_rls_policies_created_for_both_tables(self):
        for table in ("databricks_cost_budgets", "databricks_cost_ledger"):
            assert re.search(
                rf"CREATE\s+POLICY\s+\S+\s+ON\s+{table}",
                self.migration_text,
                re.IGNORECASE,
            ), f"{table} must ship a paired RLS policy (CLAUDE.md contract)"

    def test_the_direct_fk_template_with_per_table_kill_switches(self):
        for guc in (
            "app.rls_databricks_cost_budgets_enabled",
            "app.rls_databricks_cost_ledger_enabled",
        ):
            assert f"current_setting('{guc}'" in self.migration_text
        assert "app.current_tenant_id" in self.migration_text

    def test_reverse_sql_drops_both_policies(self):
        for table in ("databricks_cost_budgets", "databricks_cost_ledger"):
            assert f"DROP POLICY IF EXISTS tenant_isolation ON {table}" in self.migration_text
            assert f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY" in self.migration_text
