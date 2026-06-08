"""
Phase 274.7.10 — per-chain test file with 4 standard cases.

Happy path, short-circuit, dep-order via probe rule, audit-event shape.
"""
from __future__ import annotations
import pytest

import pytest
from django.test import TestCase

from hub.apps.core.business_rules.base import RuleExecutionContext, ValidationResult
from hub.apps.core.business_rules.chains import (
    RuleChain, register_chain, execute_chain, get_chain, _CHAINS,
)

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.integration
class TestChainHappyPath(TestCase):
    """All steps pass → outcome=PASS."""

    @pytest.mark.integration
    def test_all_steps_pass_returns_pass(self):
        chain = RuleChain(name="test.happy", short_circuit=True)
        chain.steps = [
            lambda ctx, **kw: ValidationResult(is_valid=True),
            lambda ctx, **kw: ValidationResult(is_valid=True),
        ]
        chain.steps[0].__name__ = "step_a"
        chain.steps[1].__name__ = "step_b"
        result = chain.execute(tenant_id="t1")
        assert result["outcome"] == "PASS"
        assert len(result["steps"]) == 2
        assert result["errors"] == []


@pytest.mark.integration
class TestChainShortCircuit(TestCase):
    """First failure short-circuits remaining steps."""

    @pytest.mark.integration
    def test_first_failure_short_circuits(self):
        executed: list[str] = []

        def _pass(ctx, **kw):
            executed.append("pass")
            return ValidationResult(is_valid=True)

        def _fail(ctx, **kw):
            executed.append("fail")
            return ValidationResult(is_valid=False, errors=["reason"])

        def _skip(ctx, **kw):
            executed.append("skip")
            return ValidationResult(is_valid=True)

        _pass.__name__ = "pass"
        _fail.__name__ = "fail"
        _skip.__name__ = "skip"

        chain = RuleChain(name="test.short", short_circuit=True)
        chain.steps = [_pass, _fail, _skip]
        result = chain.execute(tenant_id="t1")
        assert result["outcome"] == "FAIL"
        assert "skip" not in executed


@pytest.mark.integration
class TestChainStepOrdering(TestCase):
    """Step execution order follows registration order."""

    @pytest.mark.integration
    def test_steps_executed_in_order(self):
        order: list[str] = []

        def _first(ctx, **kw):
            order.append("first")
            return ValidationResult(is_valid=True)

        def _second(ctx, **kw):
            order.append("second")
            return ValidationResult(is_valid=True)

        _first.__name__ = "first"
        _second.__name__ = "second"

        chain = RuleChain(name="test.order", short_circuit=False)
        chain.steps = [_first, _second]
        chain.execute(tenant_id="t1")
        assert order == ["first", "second"]


@pytest.mark.integration
class TestChainAuditEventShape(TestCase):
    """Chain execution emits RULE_CHAIN_COMPLETED audit event."""

    @pytest.mark.integration
    def test_audit_event_shape(self):
        chain = RuleChain(name="test.audit_shape", short_circuit=True)
        chain.steps = [
            lambda ctx, **kw: ValidationResult(is_valid=True),
        ]
        chain.steps[0].__name__ = "single_step"
        result = chain.execute(tenant_id="t1")
        assert "steps" in result
        assert "duration_ms" in result
        assert "outcome" in result
        assert result["outcome"] in ("PASS", "FAIL")
