"""
Contract tests for the pilot credential-verification Makefile targets
(pilot-readiness 2.2).

Pins the first-query guardrail shape so it cannot regress:

- `verify-pilot-creds` is the ADVISORY run (a SKIP is not a failure) —
  the operator's daily acquisition check;
- `verify-pilot-creds-gate` is the FIRST-QUERY GATE — `--strict` turns
  every SKIP into a failure and `--require-budgets` refuses to exit 0
  unless the budget caps were verified PASS, so the live suites (which
  start compute) cannot be reached before the caps exist;
- `live-warehouse-gated` is the LOCAL first-query path for 2.3: the
  gate runs BEFORE the warehouse live classes, so a local operator
  cannot start customer compute without verified caps either (the
  nightly workflow already enforces the same order CI-side);
- all three targets are .PHONY-protected.
"""

import re
from pathlib import Path

import pytest

MAKEFILE = Path(__file__).parent.parent.parent / "Makefile"


def _recipe(target: str) -> list[str]:
    text = MAKEFILE.read_text()
    match = re.search(
        rf"^{re.escape(target)}:.*\n((?:\t.*\n|\t.*\\\n\t.*\n)+)",
        text,
        re.MULTILINE,
    )
    assert match, f"target {target} not found in Makefile"
    return list(match.group(1).splitlines())


@pytest.fixture
def advisory_recipe():
    return _recipe("verify-pilot-creds")


@pytest.fixture
def gate_recipe():
    return _recipe("verify-pilot-creds-gate")


@pytest.fixture
def gated_live_recipe():
    return _recipe("live-warehouse-gated")


def test_targets_are_phony():
    text = MAKEFILE.read_text()
    phony_lines = [ln for ln in text.splitlines() if ln.startswith(".PHONY")]
    for target in ("verify-pilot-creds", "verify-pilot-creds-gate", "live-warehouse-gated"):
        assert any(re.search(rf"(^|\s){target}(\s|$)", ln) for ln in phony_lines), (
            f"{target} is missing from .PHONY"
        )


def test_advisory_target_runs_all_surfaces_without_strict(advisory_recipe):
    joined = "\n".join(advisory_recipe)
    assert "verify_pilot_creds.py" in joined
    assert "--strict" not in joined, (
        "the advisory run must not turn SKIPs into failures (no credentials yet)"
    )
    assert "--require-budgets" not in joined


def test_gate_target_requires_budgets_and_is_strict(gate_recipe):
    joined = "\n".join(gate_recipe)
    assert "verify_pilot_creds.py" in joined
    assert "--strict" in joined, "the gate must treat a SKIP as a failure"
    assert "--require-budgets" in joined, (
        "the gate must refuse to pass without VERIFIED budget caps "
        "(pilot-readiness 2.2: caps BEFORE the first query)"
    )


def test_gate_chains_the_connector_verifier_with_an_explicit_probe_list(gate_recipe):
    # W0.5: ONE gate covers every rotated surface. The connector verifier
    # must run in the gate — with an EXPLICIT probe list, because the
    # unprovisioned connectors (dados, azure catalog) would fail a strict
    # all-probes run forever.
    joined = "\n".join(gate_recipe)
    assert "verify_connector_creds.py" in joined, (
        "the gate must chain the connector verifier (W0.5: all surfaces)"
    )
    connector_line = next(ln for ln in gate_recipe if "verify_connector_creds.py" in ln)
    for probe in ("gcp", "azure-sp", "snowflake", "stripe", "ckan", "databricks"):
        assert probe in connector_line, f"explicit probe list must carry {probe}"
    assert "--strict" in connector_line
    # Host-side runs cannot resolve the compose-internal ckan-test host —
    # the gate must default CKAN_TEST_BASE_URL to the published port.
    assert "CKAN_TEST_BASE_URL=$${CKAN_TEST_BASE_URL:-http://localhost:5100}" in (
        connector_line
    ), "the gate must default the CKAN base URL for host-side runs"


def test_gate_chains_the_stripe_test_key_verifier(gate_recipe):
    joined = "\n".join(gate_recipe)
    assert "verify_stripe_test_keys.py" in joined, (
        "the gate must chain the Stripe test-key verifier (W0.5: Stripe surface)"
    )
    stripe_line = next(ln for ln in gate_recipe if "verify_stripe_test_keys.py" in ln)
    assert "--strict" in stripe_line


def test_gate_order_pilot_first_then_connectors_then_stripe(gate_recipe):
    pilot_idx = next(i for i, ln in enumerate(gate_recipe) if "verify_pilot_creds.py" in ln)
    connector_idx = next(
        i for i, ln in enumerate(gate_recipe) if "verify_connector_creds.py" in ln
    )
    stripe_idx = next(
        i for i, ln in enumerate(gate_recipe) if "verify_stripe_test_keys.py" in ln
    )
    assert pilot_idx < connector_idx < stripe_idx, (
        "budget caps must be verified BEFORE the connector/stripe surfaces "
        "(the first-query guardrail runs first)"
    )


def test_gate_never_chains_the_old_creds_dead_check(gate_recipe):
    # The dead-check reads OLD values out of git history — the sources
    # vanish at the W0.4 force-push, so chaining it would leave the gate
    # permanently RED. It is a one-time in-window evidence generator.
    assert "verify_old_creds_dead.py" not in "\n".join(gate_recipe), (
        "the dead-check must never be chained into the gate "
        "(its git-history sources vanish post-force-push)"
    )


def test_live_warehouse_gated_runs_the_gate_before_the_live_classes(
    gated_live_recipe,
):
    joined = "\n".join(gated_live_recipe)
    assert "--strict" in joined
    assert "--require-budgets" in joined, "the local 2.3 path must run the first-query gate"
    guard_idx = next(i for i, ln in enumerate(gated_live_recipe) if "verify_pilot_creds.py" in ln)
    run_idx = next(
        i for i, ln in enumerate(gated_live_recipe) if "TestDatabricksLiveIntegration" in ln
    )
    assert guard_idx < run_idx, (
        "budget caps must be verified BEFORE the warehouse live classes "
        "(they start customer compute — the first query)"
    )
