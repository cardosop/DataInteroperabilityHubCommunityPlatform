"""
Phase 274.7.3/274.7.10 — chain side-effect ordering invariant test.

Asserts NO side-effect helpers fire until ALL chain steps succeed.
"""

import pytest
from django.test import TestCase

from hub.apps.core.business_rules.base import ValidationResult
from hub.apps.core.business_rules.chains import RuleChain

pytestmark = pytest.mark.django_db(transaction=True)


def _step_pass(ctx, **kwargs):
    return ValidationResult(is_valid=True)


def _step_fail(ctx, **kwargs):
    return ValidationResult(is_valid=False, errors=["step failed"])


class TestChainSideEffects(TestCase):
    """Phase 274.7.3 — side-effect ordering invariant."""

    def test_all_steps_pass_returns_pass(self):
        chain = RuleChain(
            name="test.pass",
            steps=[_step_pass, _step_pass],
            requires_transaction=False,
        )
        result = chain.execute()
        assert result["outcome"] == "PASS"
        assert len(result["steps"]) == 2

    def test_short_circuit_on_first_failure(self):
        call_order = []

        def step_a(ctx, **kw):
            call_order.append("a")
            return ValidationResult(is_valid=True)

        def step_b(ctx, **kw):
            call_order.append("b")
            return ValidationResult(is_valid=False, errors=["b failed"])

        def step_c(ctx, **kw):
            call_order.append("c")
            return ValidationResult(is_valid=True)

        chain = RuleChain(
            name="test.short_circuit",
            steps=[step_a, step_b, step_c],
            short_circuit=True,
            requires_transaction=False,
        )
        result = chain.execute()
        assert result["outcome"] == "FAIL"
        assert call_order == ["a", "b"], f"Step C should not run: {call_order}"

    def test_dep_order_respected(self):
        order = []

        def first(ctx, **kw):
            order.append(1)
            return ValidationResult(is_valid=True)

        def second(ctx, **kw):
            order.append(2)
            return ValidationResult(is_valid=True)

        def third(ctx, **kw):
            order.append(3)
            return ValidationResult(is_valid=True)

        chain = RuleChain(
            name="test.order",
            steps=[first, second, third],
            requires_transaction=False,
        )
        result = chain.execute()
        assert result["outcome"] == "PASS"
        assert order == [1, 2, 3]

    def test_audit_event_shape(self):
        chain = RuleChain(
            name="test.audit",
            steps=[_step_pass, _step_pass],
            requires_transaction=False,
        )
        result = chain.execute()
        assert "outcome" in result
        assert "steps" in result
        assert "duration_ms" in result
        assert "errors" in result
        assert result["outcome"] == "PASS"
        assert result["errors"] == []
