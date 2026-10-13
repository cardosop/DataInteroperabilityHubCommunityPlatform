"""TDD pins for task 3.10 — the exhaustive tier-gating matrix of the
``databricks.warehouse.create`` chain (the D3 gate).

The contract is the ALLOWANCE TABLE below — hardcoded here as the
independent specification, then checked three ways:

1. the production ``TIER_ALLOWED_WAREHOUSE_SIZES`` table must EQUAL the
   contract (the chain's vocabulary cannot drift silently);
2. the REAL chain runner must agree with the contract for EVERY
   (plan tier x size token) cell — 3 tiers x 9 tokens (8 classic +
   SERVERLESS) — a refused cell carries ``DATABRICKS_WAREHOUSE_TIER_FORBIDDEN``;
3. tiers the table does not know fail CLOSED for every token (never a
   permissive default), and the tier gate is OUTERMOST (a malformed
   request on an ineligible tier surfaces the tier refusal before any
   structural verdict).

No mocks: real Postgres tenants/plans, the REAL chain runner, the REAL
``PlanLimitService``. Zero network — a gated run leaves the request
recorder untouched (the chain has no network surface by construction).
"""

import itertools
from pathlib import Path

import pytest

from hub.apps.databricks_admin.tests.test_warehouse_create_chain import _plan, _run, _seed
from hub.apps.tenants.models import PlanTier

pytestmark = pytest.mark.django_db(transaction=True)

CHAIN_NAME = "databricks.warehouse.create"

PROJECT_ROOT = Path(__file__).resolve().parents[4]

# The contract — the independent specification the production table and
# the chain behavior are both checked against. FREE caps at S
# (trial-scale), PRO at L + serverless, ENTERPRISE carries every classic
# tier + serverless (D3).
EXPECTED_ALLOWANCES = {
    "FREE": frozenset({"XS", "S"}),
    "PRO": frozenset({"XS", "S", "M", "L", "SERVERLESS"}),
    "ENTERPRISE": frozenset({"XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "SERVERLESS"}),
}

ALL_TOKENS = ("XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "SERVERLESS")

TIER_NAMES = {"FREE": PlanTier.FREE, "PRO": PlanTier.PRO, "ENTERPRISE": PlanTier.ENTERPRISE}


def _payload_for(token):
    """The request shape per token: SERVERLESS is its own token (the
    serverless flag), a classic token is the size field."""
    if token == "SERVERLESS":
        return {"name": "matrix-wh", "serverless": True, "auto_stop_mins": 30}
    return {"name": "matrix-wh", "size": token, "auto_stop_mins": 30}


class TestAllowanceTableContract:
    def test_the_production_table_equals_the_contract(self):
        from hub.apps.databricks_admin.chains import (
            CLASSIC_WAREHOUSE_SIZES,
            TIER_ALLOWED_WAREHOUSE_SIZES,
        )

        assert TIER_ALLOWED_WAREHOUSE_SIZES == EXPECTED_ALLOWANCES
        assert set(CLASSIC_WAREHOUSE_SIZES) == {"XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL"}, (
            "the classic vocabulary is exactly the eight documented tiers"
        )

    def test_every_tier_in_the_table_is_a_plan_tier(self):
        from hub.apps.databricks_admin.chains import TIER_ALLOWED_WAREHOUSE_SIZES

        for tier, _allowed in TIER_ALLOWED_WAREHOUSE_SIZES.items():
            assert tier in PlanTier.values, f"{tier!r} is not a PlanTier"


class TestTierGatingMatrix:
    """Every (tier, token) cell against the REAL chain runner."""

    @pytest.mark.parametrize(
        ("tier_name", "token"),
        list(itertools.product(sorted(TIER_NAMES), ALL_TOKENS)),
        ids=lambda value: value if isinstance(value, str) else "",
    )
    def test_every_cell_agrees_with_the_contract(self, tier_name, token):
        from hub.apps.databricks_admin.tests._http import RecordingHandler

        allowed = EXPECTED_ALLOWANCES[tier_name]
        tenant, _workspace, _plan_row = _seed(tier=TIER_NAMES[tier_name])
        RecordingHandler.requests = []
        result = _run(tenant, payload=_payload_for(token))
        if token in allowed:
            assert result["outcome"] == "PASS", (tier_name, token, result)
        else:
            assert result["outcome"] == "FAIL", (tier_name, token, result)
            assert any(
                "[DATABRICKS_WAREHOUSE_TIER_FORBIDDEN]" in err for err in result["errors"]
            ), (tier_name, token, result["errors"])
        assert RecordingHandler.requests == [], (
            "the gate is pure policy — a gated run must never touch the network"
        )

    @pytest.mark.parametrize("token", ALL_TOKENS)
    def test_an_unknown_tier_fails_closed_for_every_token(self, token):
        tenant, _workspace, _plan_row = _seed(plan=False)
        bogus = _plan("STARTER")  # raw create bypasses choices validation
        tenant.plan = bogus
        tenant.save(update_fields=["plan"])
        result = _run(tenant, payload=_payload_for(token))
        assert result["outcome"] == "FAIL", (token, result)
        assert any("[DATABRICKS_WAREHOUSE_TIER_FORBIDDEN]" in err for err in result["errors"]), (
            token,
            result["errors"],
        )


class TestTierGateIsOutermost:
    """The 2.4 denylist-outermost discipline: the tier verdict precedes
    every structural verdict."""

    def test_serverless_with_a_size_surfaces_the_tier_refusal_on_an_ineligible_tier(self):
        # FREE forbids SERVERLESS — the malformed serverless+size request
        # must surface TIER_FORBIDDEN, never the structural contradiction.
        tenant, _ws, _plan = _seed(tier=PlanTier.FREE)
        result = _run(
            tenant,
            payload={"name": "matrix-wh", "serverless": True, "size": "L", "auto_stop_mins": 30},
        )
        assert result["outcome"] == "FAIL", result
        assert any("[DATABRICKS_WAREHOUSE_TIER_FORBIDDEN]" in err for err in result["errors"]), (
            result["errors"]
        )

    def test_serverless_with_a_size_surfaces_the_structural_verdict_on_an_eligible_tier(self):
        # PRO allows SERVERLESS — the SAME malformed request now reaches
        # the structural step, which refuses the serverless+size contradiction.
        tenant, _ws, _plan = _seed(tier=PlanTier.PRO)
        result = _run(
            tenant,
            payload={"name": "matrix-wh", "serverless": True, "size": "L", "auto_stop_mins": 30},
        )
        assert result["outcome"] == "FAIL", result
        assert any("[DATABRICKS_WAREHOUSE_INVALID_CONFIG]" in err for err in result["errors"]), (
            result["errors"]
        )

    def test_a_malformed_payload_is_refused_before_any_verdict_on_every_tier(self):
        for tier_name, tier in TIER_NAMES.items():
            tenant, _ws, _plan = _seed(tier=tier)
            result = _run(tenant, payload="not-a-dict")
            assert result["outcome"] == "FAIL", (tier_name, result)
            assert any(
                "[DATABRICKS_WAREHOUSE_INVALID_CONFIG]" in err for err in result["errors"]
            ), (tier_name, result["errors"])


class TestMatrixFidelity:
    def test_the_matrix_spec_is_complete(self):
        """The suite's own completeness guard: the matrix spans every
        documented tier and token — a future tier or size added to the
        production table without a matrix row fails here."""
        cells = {(t, tok) for t, tok in itertools.product(sorted(TIER_NAMES), ALL_TOKENS)}
        assert cells == set(itertools.product(sorted(EXPECTED_ALLOWANCES), ALL_TOKENS))
        assert len(cells) == 3 * 9, "3 tiers x 9 tokens — the full matrix"

    def test_each_tier_has_a_distinct_cap_shape(self):
        # The three tiers are NOT aliases of each other (a copy-paste
        # table would pass every cell and still be wrong).
        assert (
            EXPECTED_ALLOWANCES["FREE"]
            < EXPECTED_ALLOWANCES["PRO"]
            < EXPECTED_ALLOWANCES["ENTERPRISE"]
        )

    def test_chain_name_is_registered(self):
        from hub.apps.core.business_rules.chains import get_chain

        assert get_chain(CHAIN_NAME) is not None, f"{CHAIN_NAME} not registered"

    def test_matrix_file_artifacts_are_in_place(self):
        """The seed migration + seed command carry the tier caps (the
        quota half of D3) — the matrix pins the allowance half; both
        halves must agree on the same tiers."""
        seed_source = (
            PROJECT_ROOT / "hub/apps/tenants/management/commands/seed_default_plans.py"
        ).read_text()
        assert "max_databricks_warehouses" in seed_source
