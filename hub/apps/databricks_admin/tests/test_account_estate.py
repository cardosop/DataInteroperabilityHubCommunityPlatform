"""P8 (openspec add-databricks-account-plane task 8.4) — the registration-
first ADR + the cross-tenant estate summary (design D3/D6, the spec's
"Registration-First Operating Model and Estate Summary" scenarios).

``GET /api/v1/databricks/estate-summary/`` is the PLATFORM-admin surface:
a read-only, DERIVED aggregate of every tenant's workspace counts (by
state) and cost-budget figures, read over the admin alias (BYPASSRLS —
the sanctioned cross-tenant path; a platform-admin request carries no
tenant GUC so every row is cross-tenant by construction). A
non-platform-admin caller gets 403 with the canonical ``PERMISSION_DENIED``
code (the prose error table). The registration-first ADR is a REAL
artifact: the file + the index row + the freshness contract.

NO MOCKS: real Postgres rows on the shared test DB (workspace mirror +
budget rows across tenants), the REAL DRF view over real HTTP.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from hub.apps.databricks_admin.models import (
    DatabricksCloud,
    DatabricksCostBudget,
    DatabricksCostBudgetEnforcementMode,
    DatabricksWorkspace,
    DatabricksWorkspaceStatus,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)

ESTATE_URL = "/api/v1/databricks/estate-summary/"


def _mk_tenant(*, name):
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"{name}-{uid}",
        slug=f"{name.lower().replace(' ', '-')}-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _mk_workspace(tenant, *, status):
    from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns

    require_dns()
    return DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=f"ws-{uuid.uuid4().hex[:8]}",
        host=REAL_HOST,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status=status,
    )


def _mk_warehouse(tenant):
    from hub.apps.databricks_admin.models import DatabricksSqlWarehouse

    workspace = _mk_workspace(tenant, status=DatabricksWorkspaceStatus.ACTIVE)
    return DatabricksSqlWarehouse.objects.create(
        workspace=workspace,
        warehouse_id=f"wh-{uuid.uuid4().hex[:8]}",
        name="analytics",
        state="RUNNING",
        serverless=True,
    )


def _mk_budget(
    tenant, *, units=None, mode=DatabricksCostBudgetEnforcementMode.BLOCK, warehouse=None
):
    return DatabricksCostBudget.objects.create(
        tenant=tenant,
        budget_units_per_hour=units,
        enforcement_mode=mode,
        warehouse=warehouse,
    )


def _platform_user():
    user = User.objects.create_user(
        email=f"estate-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass123",
        status=UserStatus.ACTIVE,
    )
    user.is_platform_admin = True
    user.save(update_fields=["is_platform_admin"])
    return user


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _summary_rows(client):
    """ALL summary rows across every page.

    The summary is paginated (50/page, max 100) and the shared DB's
    residue tenants — hundreds by now — legitimately push THIS test's
    fresh rows past page 1. Reading only ``results`` (the first page)
    is the pagination-blindness class: the pin must walk the whole
    cursor (the leak-proof discipline extended to the pagination).
    """
    resp = client.get(ESTATE_URL)
    assert resp.status_code == 200, resp.content
    data = resp.json()
    rows = list(data["results"])
    for page in range(2, data.get("total_pages", 1) + 1):
        resp = client.get(ESTATE_URL, {"page": page})
        assert resp.status_code == 200, resp.content
        rows.extend(resp.json()["results"])
    return rows


class TestAccountEstateSummary:
    def test_the_summary_aggregates_counts_states_and_budgets_across_tenants(self):
        tenant_a = _mk_tenant(name="Alpha")
        _mk_workspace(tenant_a, status=DatabricksWorkspaceStatus.ACTIVE)
        _mk_workspace(tenant_a, status=DatabricksWorkspaceStatus.DISABLED)
        # ONE tenant-wide budget row is allowed (the (tenant, warehouse)
        # unique with NULLS NOT DISTINCT) — the second row is scoped.
        _mk_budget(tenant_a, units=Decimal("100"), mode=DatabricksCostBudgetEnforcementMode.BLOCK)
        _mk_budget(
            tenant_a,
            units=None,
            mode=DatabricksCostBudgetEnforcementMode.ALERT,
            warehouse=_mk_warehouse(tenant_a),
        )

        tenant_b = _mk_tenant(name="Beta")
        _mk_workspace(tenant_b, status=DatabricksWorkspaceStatus.ACTIVE)
        _mk_workspace(tenant_b, status=DatabricksWorkspaceStatus.ACTIVE)
        _mk_workspace(tenant_b, status=DatabricksWorkspaceStatus.ERROR)

        rows = {row["tenant_id"]: row for row in _summary_rows(_client(_platform_user()))}
        # The shared DB carries leaked fixture tenants from earlier
        # waves — the summary legitimately reports them ALL. The pin
        # scopes to THIS test's rows (the leak-proof discipline).
        assert {str(tenant_a.id), str(tenant_b.id)} <= set(rows)

        alpha = rows[str(tenant_a.id)]
        assert alpha["tenant_name"] == tenant_a.name
        # 3 workspaces: the two direct fixtures + the warehouse
        # mirror's parent workspace (_mk_warehouse creates it).
        assert alpha["workspace_count"] == 3
        assert alpha["workspaces_by_state"] == {"ACTIVE": 2, "DISABLED": 1}
        assert alpha["budget_count"] == 2
        assert alpha["budgeted_units_total"] == "100.000000", (
            "only the non-unlimited budgets sum into the figure"
        )
        assert alpha["block_budgets"] == 1
        assert alpha["alert_budgets"] == 1

        beta = rows[str(tenant_b.id)]
        assert beta["tenant_name"] == tenant_b.name
        assert beta["workspaces_by_state"] == {"ACTIVE": 2, "ERROR": 1}
        assert beta["budget_count"] == 0
        assert beta["budgeted_units_total"] is None
        assert beta["block_budgets"] == 0
        assert beta["alert_budgets"] == 0

    def test_the_summary_reads_across_tenants_over_the_admin_alias(self):
        # The platform-admin caller is TENANT-LESS — every row the
        # summary returns is cross-tenant by construction (the
        # BYPASSRLS admin-alias read; a tenant-scoped queryset would
        # return nothing for this caller).
        tenant_a = _mk_tenant(name="Alpha")
        _mk_workspace(tenant_a, status=DatabricksWorkspaceStatus.ACTIVE)

        rows = _summary_rows(_client(_platform_user()))
        assert str(tenant_a.id) in [r["tenant_id"] for r in rows], (
            "the tenant-less platform caller sees the tenant's estate — "
            "the BYPASSRLS admin-alias read"
        )

    def test_a_non_platform_admin_caller_gets_403_permission_denied(self):
        tenant = _mk_tenant(name="Alpha")
        user = User.objects.create_user(
            email=f"estate-{uuid.uuid4().hex[:8]}@meshant.test",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )

        resp = _client(user).get(ESTATE_URL)

        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "PERMISSION_DENIED"

    def test_unauthenticated_requests_get_401(self):
        resp = APIClient().get(ESTATE_URL)
        assert resp.status_code == 401

    def test_a_tenant_without_estate_is_omitted(self):
        tenant_a = _mk_tenant(name="Alpha")
        _mk_workspace(tenant_a, status=DatabricksWorkspaceStatus.ACTIVE)
        empty = _mk_tenant(name="Empty")  # no workspaces, no budgets — no row

        ids = [r["tenant_id"] for r in _summary_rows(_client(_platform_user()))]
        assert str(tenant_a.id) in ids
        assert str(empty.id) not in ids, "a tenant without estate renders no row"


class TestRegistrationFirstADR:
    def test_the_adr_is_written_and_indexed(self):
        from pathlib import Path

        adr = Path(__file__).resolve().parents[4] / "docs/adr/databricks-registration-first/ADR.md"
        assert adr.is_file(), "the registration-first ADR must exist"

        text = adr.read_text()
        assert "**Status**: Accepted" in text
        assert "**Date**:" in text
        assert "## Context" in text
        assert "## Decision" in text
        assert "registration-first" in text.lower()

        index = (Path(__file__).resolve().parents[4] / "docs/adr/index.md").read_text()
        assert "databricks-registration-first" in index or "Registration-First" in index, (
            "the ADR index carries the row"
        )
