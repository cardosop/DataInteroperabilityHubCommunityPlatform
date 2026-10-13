"""
Contract tests for the warehouse suite's environment-gating policy
(oss-release-remediation W0.10, W1).

The warehouse live suites (Databricks/Athena, Snowflake/BigQuery) gate on
credential presence. The plain ``pytest.mark.skipif`` markers the suites
shipped with SKIP silently under CI — a mis-configured runner reported
green while the live suites never ran (the W1 false-claim). The W16 policy
says environment-dependence must announce itself: ``skip_or_fail`` raises
in CI and skips gracefully locally.

Pins:
1. no plain ``pytest.mark.skipif`` remains in the two warehouse connector
   test files (the env-gating class);
2. the W16 ``skip_or_fail`` call sites exist per connector (Databricks,
   Athena, Snowflake, BigQuery) so the gate is real, not removed.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WAREHOUSE_TESTS = REPO_ROOT / "hub" / "apps" / "warehouses" / "tests"
FILES = (
    WAREHOUSE_TESTS / "test_connectors_databricks_athena.py",
    WAREHOUSE_TESTS / "test_connectors_snowflake_bigquery.py",
)


class TestNoPlainEnvGatingSkipifs:
    def test_no_plain_skipif_in_the_warehouse_connector_suites(self):
        for path in FILES:
            src = path.read_text()
            assert "pytest.mark.skipif" not in src, (
                f"{path.name} still carries a plain pytest.mark.skipif — "
                "env-gated skips must go through skip_or_fail (W16: raise "
                "in CI, skip locally) or a mis-configured CI runner goes "
                "green while the live suites never ran"
            )

    def test_every_connector_gate_uses_skip_or_fail(self):
        for path in FILES:
            src = path.read_text()
            assert "skip_or_fail" in src, (
                f"{path.name} lost its W16 gate — the env-gating must "
                "stay, only the mechanism changes"
            )
        for helper in (
            "_require_databricks_creds",
            "_require_athena_sandbox",
            "_require_snowflake_creds",
            "_require_bigquery_creds",
        ):
            assert any(helper in p.read_text() for p in FILES), (
                f"{helper} not found — a connector gate was dropped"
            )
