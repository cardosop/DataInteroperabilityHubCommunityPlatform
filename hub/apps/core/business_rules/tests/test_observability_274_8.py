"""
Phase 274.8 regression — observability + Sentry signal-vs-noise contract.

Covers all four behavioural promises of Phase 274.8:

* 274.8.1 ``BusinessRules._emit_observability`` is defined on the BASE
  class (not on a side mixin), so every subclass inherits it without
  opt-in.
* 274.8.2 ``RuleChain.execute`` opens a parent OTel span with the
  canonical attribute set (name, tenant_id, user_id, short_circuit,
  steps_planned, steps_executed, outcome, duration_ms, errors_count).
* 274.8.3 ``execute()`` always invokes ``_emit_observability`` on the
  result, on BOTH the validation-failure (is_valid=False) path and the
  exception-wrapped failure path.
* 274.8.5 Signal-vs-noise: ``is_valid=False`` must NOT produce a Sentry
  event; an exception inside ``validate_*`` MUST.

External boundaries (the Prometheus metric object, the Sentry capture
facade, the OTel tracer factory) are patched because there is no test
infrastructure for a real Sentry server / real Prometheus pushgateway
in the unit suite. The internal contracts under test
(``BusinessRules.execute``, ``RuleChain.execute``, the canonical
attribute shape) all run for real.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase

from hub.apps.core.business_rules.base import (
    BusinessRules,
    BusinessRulesObservabilityMixin,
    ValidationResult,
)
from hub.apps.core.business_rules.chains import RuleChain

pytestmark = pytest.mark.django_db(transaction=True)


class _AlwaysValidRule(BusinessRules):
    """Returns is_valid=True. Smallest concrete rule for hook tests."""

    def get_rule_name(self) -> str:
        return "always_valid_test_rule"

    def validate(self, context=None, *args, **kwargs) -> ValidationResult:
        return ValidationResult(is_valid=True)


class _AlwaysInvalidRule(BusinessRules):
    """Returns is_valid=False without raising — exercises the
    'business signal, NOT a Sentry event' path."""

    def get_rule_name(self) -> str:
        return "always_invalid_test_rule"

    def validate(self, context=None, *args, **kwargs) -> ValidationResult:
        return ValidationResult(
            is_valid=False,
            errors=["business assertion failed"],
        )


class _RaisingRule(BusinessRules):
    """Raises a non-trivial exception inside validate_* — exercises the
    'exception IS a Sentry event' path."""

    def get_rule_name(self) -> str:
        return "raising_test_rule"

    def validate(self, context=None, *args, **kwargs) -> ValidationResult:
        raise RuntimeError("boom from inside validate_*")


# ─────────────────────────────────────────────────────────────────────
# 274.8.1 — base-class placement
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestEmitObservabilityIsOnBaseClass(TestCase):
    """``_emit_observability`` MUST be defined on ``BusinessRules`` itself
    so EVERY rule has it without opting into a side mixin."""

    @pytest.mark.integration
    def test_method_lives_on_base_class(self):
        # Must be findable as a method of the abstract base class — not
        # only as an attribute of subclasses or the legacy mixin.
        self.assertTrue(
            callable(getattr(BusinessRules, "_emit_observability", None)),
            "BusinessRules._emit_observability must be defined on the base "
            "class; the standalone mixin only worked for opted-in subclasses",
        )

    @pytest.mark.integration
    def test_legacy_mixin_is_now_a_noop_shim(self):
        # The mixin survives as a deprecation shim. It must NOT carry its
        # own ``_emit_observability`` anymore — that lives on the base.
        # The check is that the mixin doesn't define the method in its
        # own __dict__ (inherited from object is fine; methods on the
        # MRO above object via the base class are also fine).
        own_method = BusinessRulesObservabilityMixin.__dict__.get("_emit_observability")
        self.assertIsNone(
            own_method,
            "Legacy mixin must not redefine _emit_observability; the "
            "single source of truth is BusinessRules.",
        )


# ─────────────────────────────────────────────────────────────────────
# 274.8.3 — hook invoked from BusinessRules.execute on both paths
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestEmitObservabilityIsCalledFromExecute(TestCase):
    """``execute()`` MUST call ``_emit_observability`` regardless of the
    validation outcome — passing, failing-by-assertion, or
    failing-by-exception."""

    @patch("hub.apps.core.business_rules.base.BusinessRules._emit_observability")
    @pytest.mark.integration
    def test_hook_called_on_pass(self, mock_emit):
        _AlwaysValidRule().execute()
        self.assertEqual(mock_emit.call_count, 1)
        passed_result = mock_emit.call_args[0][0]
        self.assertTrue(passed_result.is_valid)

    @patch("hub.apps.core.business_rules.base.BusinessRules._emit_observability")
    @pytest.mark.integration
    def test_hook_called_on_business_failure(self, mock_emit):
        _AlwaysInvalidRule().execute()
        self.assertEqual(mock_emit.call_count, 1)
        passed_result = mock_emit.call_args[0][0]
        self.assertFalse(passed_result.is_valid)
        self.assertEqual(passed_result.errors, ["business assertion failed"])

    @patch("hub.apps.core.business_rules.base.BusinessRules._emit_observability")
    @pytest.mark.integration
    def test_hook_called_on_exception_path(self, mock_emit):
        _RaisingRule().execute()
        self.assertEqual(mock_emit.call_count, 1)
        passed_result = mock_emit.call_args[0][0]
        self.assertFalse(passed_result.is_valid)
        # The synthesized error result carries the exception type as
        # detail metadata — assert the shape so dashboards keying off
        # ``details.exception_type`` keep working.
        self.assertEqual(passed_result.details.get("exception_type"), "RuntimeError")


@pytest.mark.integration
class TestEmitObservabilityIncrementsFailureCounter(TestCase):
    """The default hook implementation must increment the canonical
    Prometheus failure counter on ``is_valid=False`` results."""

    @patch("hub.apps.observability.otel_metrics.business_rule_validation_failures_total")
    @pytest.mark.integration
    def test_counter_inc_on_business_failure(self, mock_counter):
        _AlwaysInvalidRule().execute()
        # ``.labels(rule=...).inc()`` — verify the .inc was reached.
        self.assertTrue(
            mock_counter.labels.return_value.inc.called,
            "Failure counter must be incremented when is_valid=False",
        )

    @patch("hub.apps.observability.otel_metrics.business_rule_validation_failures_total")
    @pytest.mark.integration
    def test_counter_inc_on_exception_path(self, mock_counter):
        _RaisingRule().execute()
        self.assertTrue(
            mock_counter.labels.return_value.inc.called,
            "Failure counter must also fire when validate_* raises",
        )

    @patch("hub.apps.observability.otel_metrics.business_rule_validation_failures_total")
    @pytest.mark.integration
    def test_counter_not_inc_on_pass(self, mock_counter):
        _AlwaysValidRule().execute()
        self.assertFalse(
            mock_counter.labels.return_value.inc.called,
            "Failure counter must NOT fire when is_valid=True",
        )


# ─────────────────────────────────────────────────────────────────────
# 274.8.5 — Sentry signal-vs-noise contract
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestSentrySignalVsNoise(TestCase):
    """``is_valid=False`` must NOT reach Sentry; an exception inside
    ``validate_*`` MUST reach Sentry via the project's ``track_error``
    facade with proper context (rule_name, exception_type)."""

    @patch("hub.apps.core.error_handling.error_tracking.track_error")
    @pytest.mark.integration
    def test_is_valid_false_does_not_capture_sentry(self, mock_track):
        _AlwaysInvalidRule().execute()
        self.assertEqual(
            mock_track.call_count,
            0,
            "is_valid=False is normal business signal; it must NOT be "
            "tracked in Sentry or on-call would drown in false-positives",
        )

    @patch("hub.apps.core.error_handling.error_tracking.track_error")
    @pytest.mark.integration
    def test_exception_in_validate_captures_sentry(self, mock_track):
        _RaisingRule().execute()
        self.assertEqual(
            mock_track.call_count,
            1,
            "An exception inside validate_* is a real bug; it MUST be "
            "routed to Sentry via track_error so on-call gets paged",
        )
        # Verify the captured exception is the one we raised and that
        # the context payload carries the rule_name + exception_type so
        # Sentry deduplication groups errors correctly.
        kwargs = mock_track.call_args.kwargs
        self.assertIsInstance(kwargs["error"], RuntimeError)
        self.assertEqual(str(kwargs["error"]), "boom from inside validate_*")
        self.assertEqual(kwargs["error_code"], "BUSINESS_RULE_EXECUTION_FAILED")
        self.assertEqual(kwargs["context"]["rule_name"], "raising_test_rule")
        self.assertEqual(kwargs["context"]["exception_type"], "RuntimeError")

    @patch("hub.apps.core.error_handling.error_tracking.track_error")
    @pytest.mark.integration
    def test_pass_does_not_capture_sentry(self, mock_track):
        _AlwaysValidRule().execute()
        self.assertEqual(mock_track.call_count, 0)


# ─────────────────────────────────────────────────────────────────────
# 274.8.2 — RuleChain parent span with canonical attribute shape
# ─────────────────────────────────────────────────────────────────────


def _patched_chain_tracer():
    """Build a (mock_tracer, mock_span) pair where ``start_as_current_span``
    yields ``mock_span`` as a context manager — matching the existing
    convention in ``test_base.py::test_tracing``."""
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_span.is_recording.return_value = True

    @contextmanager
    def span_ctx(_name):
        yield mock_span

    mock_tracer.start_as_current_span.side_effect = span_ctx
    return mock_tracer, mock_span


@pytest.mark.integration
class TestRuleChainOpensParentSpan(TestCase):
    """``RuleChain.execute`` must open a parent span named
    ``business_rule_chain.<chain_name>`` and stamp the canonical
    attribute shape on both PASS and FAIL outcomes."""

    @patch("hub.apps.core.business_rules.chains._otel_get_tracer")
    @patch("hub.apps.core.business_rules.chains._OTEL_AVAILABLE", True)
    @pytest.mark.integration
    def test_canonical_attributes_on_pass(self, mock_get_tracer):
        mock_tracer, mock_span = _patched_chain_tracer()
        mock_get_tracer.return_value = mock_tracer

        chain = RuleChain(name="test.pass_chain", requires_transaction=False)
        chain.steps = [lambda ctx, **kw: ValidationResult(is_valid=True)]
        chain.steps[0].__name__ = "always_ok"

        result = chain.execute(tenant_id="tnt-1", user_id="usr-1")
        self.assertEqual(result["outcome"], "PASS")

        # Span name
        mock_tracer.start_as_current_span.assert_called_once_with(
            "business_rule_chain.test.pass_chain"
        )
        # Canonical attributes
        attr_calls = {
            args[0]: args[1]
            for args, _ in (call for call in mock_span.set_attribute.call_args_list)
        }
        self.assertEqual(attr_calls["business_rule_chain.name"], "test.pass_chain")
        self.assertEqual(attr_calls["business_rule_chain.tenant_id"], "tnt-1")
        self.assertEqual(attr_calls["business_rule_chain.user_id"], "usr-1")
        self.assertEqual(attr_calls["business_rule_chain.steps_planned"], 1)
        self.assertEqual(attr_calls["business_rule_chain.steps_executed"], 1)
        self.assertEqual(attr_calls["business_rule_chain.outcome"], "PASS")
        self.assertEqual(attr_calls["business_rule_chain.errors_count"], 0)
        # duration_ms is timing-dependent; assert presence + type only.
        self.assertIn("business_rule_chain.duration_ms", attr_calls)
        self.assertIsInstance(attr_calls["business_rule_chain.duration_ms"], float)

    @patch("hub.apps.core.business_rules.chains._otel_get_tracer")
    @patch("hub.apps.core.business_rules.chains._OTEL_AVAILABLE", True)
    @pytest.mark.integration
    def test_canonical_attributes_on_fail(self, mock_get_tracer):
        mock_tracer, mock_span = _patched_chain_tracer()
        mock_get_tracer.return_value = mock_tracer

        chain = RuleChain(name="test.fail_chain", requires_transaction=False)
        chain.steps = [
            lambda ctx, **kw: ValidationResult(is_valid=False, errors=["nope"]),
        ]
        chain.steps[0].__name__ = "always_fail"

        result = chain.execute(tenant_id="tnt-2")
        self.assertEqual(result["outcome"], "FAIL")

        attr_calls = {
            args[0]: args[1]
            for args, _ in (call for call in mock_span.set_attribute.call_args_list)
        }
        self.assertEqual(attr_calls["business_rule_chain.outcome"], "FAIL")
        self.assertEqual(attr_calls["business_rule_chain.errors_count"], 1)

    @patch("hub.apps.core.business_rules.chains._otel_get_tracer")
    @patch("hub.apps.core.business_rules.chains._OTEL_AVAILABLE", True)
    @pytest.mark.integration
    def test_step_exception_recorded_on_chain_span(self, mock_get_tracer):
        """When a step raises, ``record_exception`` must be called on the
        chain span so Tempo/Jaeger surfaces the failure without forcing
        operators to cross-reference logs."""
        mock_tracer, mock_span = _patched_chain_tracer()
        mock_get_tracer.return_value = mock_tracer

        boom = RuntimeError("step exploded")

        def _raising(ctx, **kw):
            raise boom

        chain = RuleChain(name="test.exc_chain", requires_transaction=False)
        chain.steps = [_raising]
        result = chain.execute(tenant_id="tnt-3")
        self.assertEqual(result["outcome"], "FAIL")

        # The exception was recorded on the span (we don't assert
        # identity since record_exception receives the *raised* object
        # which is the same RuntimeError instance).
        mock_span.record_exception.assert_called_once()
        recorded = mock_span.record_exception.call_args[0][0]
        self.assertIs(recorded, boom)
