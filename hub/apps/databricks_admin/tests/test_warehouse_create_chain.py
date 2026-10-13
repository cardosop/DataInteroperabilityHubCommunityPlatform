"""TDD pins for the warehouse-creation chain (openspec
add-databricks-sql-warehouses task 3.4) — the D3 gate.

``databricks.warehouse.create`` = TenantScoping → tier gate (the
tenant's plan tier → allowed size set, serverless included) →
per-tenant quota (the plan limit ``max_databricks_warehouses`` counted
through the core resource-counter registry, DELETING rows excluded) →
structural validation. Every refusal carries a classified code; the
chain has NO network surface by construction (the 3.3 client is never
constructed), so a gated request fails with ZERO network calls and no
mirror row.

No mocks: real Postgres tenants/plans/workspaces/warehouse rows, the
REAL chain runner, the REAL ``PlanLimitService`` (row-lock + counter).
"""

import inspect
import uuid
from pathlib import Path

import pytest

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests.test_uc_change_requests import _make_workspace
from hub.apps.tenants.models import PlanTier, TenantPlan
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

CHAIN_NAME = "databricks.warehouse.create"

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _plan(tier, limits=None):
    """A REAL per-test TenantPlan row (unique slug — the shared DB may
    carry leaked plans from parallel sessions)."""
    suffix = uuid.uuid4().hex[:8]
    return TenantPlan.objects.create(
        name=f"Warehouse {tier} {suffix}",
        slug=f"wh-{tier.lower()}-{suffix}",
        tier=tier,
        limits_json=limits if limits is not None else {"max_databricks_warehouses": 2},
    )


def _seed(*, tier=PlanTier.FREE, limits=None, plan=True):
    require_dns()
    tenant = TenantFactory.create_tenant()
    workspace = _make_workspace(tenant)
    plan_row = _plan(tier, limits) if plan else None
    if plan_row is not None:
        tenant.plan = plan_row
        tenant.save(update_fields=["plan"])
    return tenant, workspace, plan_row


def _warehouse(workspace, *, state="RUNNING"):
    from hub.apps.databricks_admin.models import DatabricksSqlWarehouse

    return DatabricksSqlWarehouse.objects.create(
        workspace=workspace,
        warehouse_id=uuid.uuid4().hex[:16],
        name=f"wh-{uuid.uuid4().hex[:6]}",
        state=state,
    )


def _payload(**overrides):
    payload = {"name": "analytics-wh", "size": "S", "auto_stop_mins": 30}
    payload.update(overrides)
    return payload


def _run(tenant, **kwargs):
    from django.db import transaction

    from hub.apps.core.business_rules.chains import execute_chain

    with transaction.atomic():
        return execute_chain(CHAIN_NAME, tenant=tenant, **kwargs)


def _failed_with(result, code):
    assert result["outcome"] == "FAIL", result
    return any(f"[{code}]" in err for err in result["errors"]), result


class TestChainRegistration:
    def test_chain_is_registered(self):
        from hub.apps.core.business_rules.chains import get_chain

        assert get_chain(CHAIN_NAME) is not None, f"{CHAIN_NAME} not registered"

    def test_chain_requires_an_active_transaction(self):
        from hub.apps.core.business_rules.chains import execute_chain

        tenant, _ws, _plan = _seed()
        with pytest.raises(RuntimeError, match="active transaction"):
            execute_chain(CHAIN_NAME, tenant=tenant, payload=_payload())


class TestTierGate:
    def test_free_plan_allows_xs_and_s(self):
        tenant, _ws, _plan = _seed(tier=PlanTier.FREE)
        for size in ("XS", "S"):
            result = _run(tenant, payload=_payload(size=size))
            assert result["outcome"] == "PASS", (size, result)

    def test_free_plan_refuses_l_with_the_tier_code(self):
        tenant, _ws, _plan = _seed(tier=PlanTier.FREE)
        refused, result = _failed_with(
            _run(tenant, payload=_payload(size="L")), "DATABRICKS_WAREHOUSE_TIER_FORBIDDEN"
        )
        assert refused, result["errors"]

    def test_pro_plan_allows_l(self):
        tenant, _ws, _plan = _seed(tier=PlanTier.PRO)
        assert _run(tenant, payload=_payload(size="L"))["outcome"] == "PASS"

    def test_pro_plan_refuses_4xl(self):
        tenant, _ws, _plan = _seed(tier=PlanTier.PRO)
        refused, result = _failed_with(
            _run(tenant, payload=_payload(size="4XL")), "DATABRICKS_WAREHOUSE_TIER_FORBIDDEN"
        )
        assert refused, result["errors"]

    def test_enterprise_allows_4xl(self):
        tenant, _ws, _plan = _seed(tier=PlanTier.ENTERPRISE)
        assert _run(tenant, payload=_payload(size="4XL"))["outcome"] == "PASS"

    def test_serverless_requires_at_least_pro(self):
        free_tenant, _ws, _ = _seed(tier=PlanTier.FREE)
        refused, result = _failed_with(
            _run(free_tenant, payload=_payload(serverless=True, size=None)),
            "DATABRICKS_WAREHOUSE_TIER_FORBIDDEN",
        )
        assert refused, result["errors"]

        pro_tenant, _ws2, _ = _seed(tier=PlanTier.PRO)
        assert _run(pro_tenant, payload=_payload(serverless=True, size=None))["outcome"] == "PASS"

    def test_unknown_size_is_invalid_config_not_tier(self):
        """A size no tier has (e.g. '5XL') is a malformed request — the
        INVALID_CONFIG code, never a tier refusal."""
        tenant, _ws, _plan = _seed(tier=PlanTier.ENTERPRISE)
        refused, result = _failed_with(
            _run(tenant, payload=_payload(size="5XL")), "DATABRICKS_WAREHOUSE_INVALID_CONFIG"
        )
        assert refused, result["errors"]
        assert not any("DATABRICKS_WAREHOUSE_TIER_FORBIDDEN" in e for e in result["errors"])

    def test_no_plan_falls_back_to_the_active_free_tier(self):
        """The check_limit precedent: a tenant without a plan resolves
        the active FREE plan — the tier gate follows the same rule."""
        tenant, _ws, _plan = _seed(plan=False)
        TenantPlan.objects.get_or_create(
            slug="free",
            defaults={
                "name": "Free Plan",
                "tier": PlanTier.FREE,
                "limits_json": {"max_databricks_warehouses": 2},
            },
        )
        refused, result = _failed_with(
            _run(tenant, payload=_payload(size="L")), "DATABRICKS_WAREHOUSE_TIER_FORBIDDEN"
        )
        assert refused, result["errors"]

    def test_dangling_plan_id_falls_back_to_the_free_tier(self):
        """A plan_id whose row no longer exists resolves the FREE
        fallback — never a crash, never permissive. (A dangling FK can't
        exist in the DB — the referential constraint forbids it — so the
        resolver is pinned directly with a stand-in object carrying the
        stale id; the chain path is covered by the no-plan pin.)"""
        from types import SimpleNamespace

        from hub.apps.databricks_admin.chains import _resolve_plan_tier

        TenantPlan.objects.get_or_create(
            slug="free",
            defaults={
                "name": "Free Plan",
                "tier": PlanTier.FREE,
                "limits_json": {"max_databricks_warehouses": 2},
            },
        )
        assert _resolve_plan_tier(SimpleNamespace(plan_id=uuid.uuid4())) == PlanTier.FREE

    def test_unknown_plan_tier_fails_closed(self):
        """A plan whose tier this code does not know (a deploy-rollback
        vocabulary row) gets NO allowlist — TIER_FORBIDDEN, the 2.4
        denylist discipline."""
        tenant, _ws, _ = _seed(plan=False)
        bogus = _plan("STARTER")  # raw create bypasses choices validation
        tenant.plan = bogus
        tenant.save(update_fields=["plan"])
        refused, result = _failed_with(
            _run(tenant, payload=_payload(size="XS")), "DATABRICKS_WAREHOUSE_TIER_FORBIDDEN"
        )
        assert refused, result["errors"]

    def test_serverless_with_size_on_free_refuses_tier_first(self):
        """The D3 order: the tier gate is OUTERMOST — a malformed
        request (serverless + size contradiction) on a FREE tenant
        surfaces the tier refusal before the structural contradiction
        (the 2.4 denylist-outermost precedent)."""
        tenant, _ws, _plan = _seed(tier=PlanTier.FREE)
        refused, result = _failed_with(
            _run(tenant, payload=_payload(serverless=True)), "DATABRICKS_WAREHOUSE_TIER_FORBIDDEN"
        )
        assert refused, result["errors"]


class TestQuotaGate:
    def test_under_quota_passes(self):
        tenant, workspace, _plan = _seed(
            tier=PlanTier.FREE, limits={"max_databricks_warehouses": 2}
        )
        _warehouse(workspace)
        assert _run(tenant, payload=_payload())["outcome"] == "PASS"

    def test_at_quota_fails_with_the_quota_code(self):
        tenant, workspace, _plan = _seed(
            tier=PlanTier.FREE, limits={"max_databricks_warehouses": 2}
        )
        _warehouse(workspace)
        _warehouse(workspace)
        refused, result = _failed_with(
            _run(tenant, payload=_payload()), "DATABRICKS_WAREHOUSE_QUOTA_EXCEEDED"
        )
        assert refused, result["errors"]

    def test_deleting_rows_do_not_count(self):
        """The quota counts LIVE warehouses — a DELETING mirror row (on
        its way out) never blocks a create."""
        tenant, workspace, _plan = _seed(
            tier=PlanTier.FREE, limits={"max_databricks_warehouses": 2}
        )
        _warehouse(workspace)
        _warehouse(workspace, state="DELETING")
        assert _run(tenant, payload=_payload())["outcome"] == "PASS"

        # Two LIVE rows + a DELETING row → the quota fires at 2.
        _warehouse(workspace)
        refused, result = _failed_with(
            _run(tenant, payload=_payload()), "DATABRICKS_WAREHOUSE_QUOTA_EXCEEDED"
        )
        assert refused, result["errors"]

    def test_unlimited_plan_never_fails(self):
        tenant, workspace, _plan = _seed(
            tier=PlanTier.ENTERPRISE, limits={"max_databricks_warehouses": None}
        )
        for _ in range(5):
            _warehouse(workspace)
        assert _run(tenant, payload=_payload())["outcome"] == "PASS"

    def test_missing_limit_key_means_unlimited(self):
        """The repo-wide plan-limit semantics: an absent key is
        unlimited (``check_limit``'s max=None) — the 3.4 backfill
        migration + seed defaults carry the tier caps for existing and
        new plans respectively."""
        tenant, workspace, _plan = _seed(tier=PlanTier.FREE, limits={})
        for _ in range(3):
            _warehouse(workspace)
        assert _run(tenant, payload=_payload())["outcome"] == "PASS"


class TestStructuralValidation:
    def test_missing_name_fails(self):
        tenant, _ws, _plan = _seed(tier=PlanTier.PRO)
        payload = _payload()
        del payload["name"]
        refused, result = _failed_with(
            _run(tenant, payload=payload), "DATABRICKS_WAREHOUSE_INVALID_CONFIG"
        )
        assert refused, result["errors"]

    def test_blank_name_fails(self):
        tenant, _ws, _plan = _seed(tier=PlanTier.PRO)
        refused, result = _failed_with(
            _run(tenant, payload=_payload(name="   ")), "DATABRICKS_WAREHOUSE_INVALID_CONFIG"
        )
        assert refused, result["errors"]

    def test_classic_without_size_fails(self):
        tenant, _ws, _plan = _seed(tier=PlanTier.PRO)
        payload = _payload()
        del payload["size"]
        refused, result = _failed_with(
            _run(tenant, payload=payload), "DATABRICKS_WAREHOUSE_INVALID_CONFIG"
        )
        assert refused, result["errors"]

    def test_serverless_with_size_fails(self):
        """The mirror invariant: a serverless warehouse has no size tier
        (the 3.3 client's own ValueError contract, re-validated here)."""
        tenant, _ws, _plan = _seed(tier=PlanTier.PRO)
        refused, result = _failed_with(
            _run(tenant, payload=_payload(serverless=True)), "DATABRICKS_WAREHOUSE_INVALID_CONFIG"
        )
        assert refused, result["errors"]

    def test_non_bool_serverless_fails(self):
        tenant, _ws, _plan = _seed(tier=PlanTier.PRO)
        refused, result = _failed_with(
            _run(tenant, payload=_payload(serverless="yes")), "DATABRICKS_WAREHOUSE_INVALID_CONFIG"
        )
        assert refused, result["errors"]

    def test_negative_auto_stop_fails(self):
        tenant, _ws, _plan = _seed(tier=PlanTier.PRO)
        refused, result = _failed_with(
            _run(tenant, payload=_payload(auto_stop_mins=-1)), "DATABRICKS_WAREHOUSE_INVALID_CONFIG"
        )
        assert refused, result["errors"]

    def test_non_int_auto_stop_fails(self):
        tenant, _ws, _plan = _seed(tier=PlanTier.PRO)
        refused, result = _failed_with(
            _run(tenant, payload=_payload(auto_stop_mins="30")),
            "DATABRICKS_WAREHOUSE_INVALID_CONFIG",
        )
        assert refused, result["errors"]

    def test_bool_auto_stop_fails(self):
        """The isinstance-bool trap: ``isinstance(True, int)`` is True —
        a boolean auto_stop_mins must be refused, not treated as 1."""
        tenant, _ws, _plan = _seed(tier=PlanTier.PRO)
        refused, result = _failed_with(
            _run(tenant, payload=_payload(auto_stop_mins=True)),
            "DATABRICKS_WAREHOUSE_INVALID_CONFIG",
        )
        assert refused, result["errors"]

    def test_non_dict_payload_fails(self):
        tenant, _ws, _plan = _seed(tier=PlanTier.PRO)
        refused, result = _failed_with(
            _run(tenant, payload="not-a-dict"), "DATABRICKS_WAREHOUSE_INVALID_CONFIG"
        )
        assert refused, result["errors"]

    def test_cross_tenant_workspace_fails(self):
        tenant, _ws, _plan = _seed(tier=PlanTier.PRO)
        other_tenant = TenantFactory.create_tenant()
        foreign_workspace = _make_workspace(other_tenant, name="foreign-ws")
        refused, result = _failed_with(
            _run(tenant, payload=_payload(), workspace=foreign_workspace),
            "DATABRICKS_WAREHOUSE_INVALID_CONFIG",
        )
        assert refused, result["errors"]


class TestGateLeavesNoTrace:
    def test_refused_chains_create_no_mirror_row(self):
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouse

        tenant, workspace, _plan = _seed(
            tier=PlanTier.FREE, limits={"max_databricks_warehouses": 2}
        )
        _run(tenant, payload=_payload(size="L"))  # tier-refused
        _warehouse(workspace)
        _warehouse(workspace)
        _run(tenant, payload=_payload())  # quota-refused
        assert (
            not DatabricksSqlWarehouse.objects.filter(workspace__tenant=tenant)
            .filter(name="analytics-wh")
            .exists()
        ), "a refused chain must create no mirror row"

    def test_zero_network_by_construction(self):
        """The chain's builder never touches the compute client — the
        gate is pure policy over local state (the 0.11 AST-scan
        convention)."""
        from hub.apps.databricks_admin import chains as chains_module

        src = inspect.getsource(chains_module._warehouse_create_chain)
        assert "sql_warehouse_client" not in src
        assert "DatabricksApiClient" not in src


class TestPlanSystemExtension:
    def test_limit_key_is_known(self):
        assert "max_databricks_warehouses" in TenantPlan.KNOWN_LIMIT_KEYS

    def test_counter_counts_live_warehouse_rows(self):
        from hub.apps.core.limit_registry import get_resource_count

        tenant, workspace, _plan = _seed(tier=PlanTier.ENTERPRISE)
        _warehouse(workspace)
        _warehouse(workspace)
        _warehouse(workspace, state="DELETING")
        assert get_resource_count(str(tenant.id), "max_databricks_warehouses") == 2

    def test_seed_defaults_carry_the_tier_caps(self):
        """FREE=2, PRO=10, ENTERPRISE=None (unlimited) — the seed command
        and the backfill migration agree on one source of truth."""
        seed_source = (
            PROJECT_ROOT / "hub/apps/tenants/management/commands/seed_default_plans.py"
        ).read_text()
        assert "max_databricks_warehouses" in seed_source

        migration_dir = PROJECT_ROOT / "hub/apps/tenants/migrations"
        backfill = next(p for p in sorted(migration_dir.glob("0110_*.py")) if "warehouse" in p.name)
        namespace = {}
        exec(compile(backfill.read_text(), str(backfill), "exec"), namespace)
        assert namespace["TIER_DEFAULTS"] == {"FREE": 2, "PRO": 10, "ENTERPRISE": None}

    def test_backfill_migration_sets_caps_and_never_overwrites(self):
        from django.apps import apps as live_apps

        migration_dir = PROJECT_ROOT / "hub/apps/tenants/migrations"
        backfill = next(p for p in sorted(migration_dir.glob("0110_*.py")) if "warehouse" in p.name)
        namespace = {}
        exec(compile(backfill.read_text(), str(backfill), "exec"), namespace)
        _backfill = namespace["_backfill_warehouse_caps"]

        fresh = _plan(PlanTier.FREE, limits={})
        custom = _plan(PlanTier.PRO, limits={"max_databricks_warehouses": 99})
        # The migration receives the app registry from the migration
        # runner; the pin passes the LIVE registry (the function only
        # uses apps.get_model + plain ORM reads).
        _backfill(live_apps, None)
        fresh.refresh_from_db()
        custom.refresh_from_db()
        assert fresh.limits_json["max_databricks_warehouses"] == 2
        assert custom.limits_json["max_databricks_warehouses"] == 99, (
            "an explicit operator value is never overwritten"
        )

    def test_reverse_migration_strips_the_key(self):
        from django.apps import apps as live_apps

        migration_dir = PROJECT_ROOT / "hub/apps/tenants/migrations"
        backfill = next(p for p in sorted(migration_dir.glob("0110_*.py")) if "warehouse" in p.name)
        namespace = {}
        exec(compile(backfill.read_text(), str(backfill), "exec"), namespace)
        _strip = namespace["_strip_warehouse_caps"]

        capped = _plan(PlanTier.FREE, limits={"max_databricks_warehouses": 2})
        untouched = _plan(PlanTier.PRO, limits={})
        _strip(live_apps, None)
        capped.refresh_from_db()
        untouched.refresh_from_db()
        assert "max_databricks_warehouses" not in capped.limits_json
        assert "max_databricks_warehouses" not in untouched.limits_json, (
            "a plan that never carried the key is untouched by the reverse"
        )
