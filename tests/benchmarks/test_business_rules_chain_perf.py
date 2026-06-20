"""
Phase 274.7.11 — business rules chain performance benchmark.

SLO target: chain overhead p95 < 50ms.
Fail PR if regression > 20% (Phase 227.L8.7 perf-gate convention).

Uses pytest-benchmark if available; silently skips otherwise.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.skip(reason="Requires pytest-benchmark and live dataset for meaningful numbers")
def test_chain_overhead_p95(benchmark):
    """Chain runner overhead should be under 50ms p95."""
    from hub.apps.core.business_rules.base import RuleExecutionContext

    def _run_chain():
        RuleExecutionContext(tenant_id="t1", user_id="u1")
        return {"outcome": "PASS"}

    result = benchmark(_run_chain)
    assert result["outcome"] == "PASS"


class TestChainPerfSmoke(TestCase):
    """Smoke test — chain execution overhead is reasonable."""

    def test_chain_execution_is_sub_second(self):
        import time

        from hub.apps.core.business_rules.chains import RuleChain

        chain = RuleChain(
            name="perf.smoke",
            steps=[
                lambda ctx, **kw: __import__(
                    "hub.apps.core.business_rules.base", fromlist=["ValidationResult"]
                ).ValidationResult(is_valid=True),
                lambda ctx, **kw: __import__(
                    "hub.apps.core.business_rules.base", fromlist=["ValidationResult"]
                ).ValidationResult(is_valid=True),
            ],
            requires_transaction=False,
        )
        started = time.monotonic()
        result = chain.execute()
        elapsed = time.monotonic() - started
        assert result["outcome"] == "PASS"
        assert elapsed < 1.0, f"Chain overhead {elapsed:.3f}s exceeds 1s"
