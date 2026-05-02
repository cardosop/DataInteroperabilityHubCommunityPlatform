"""
Phase 240.5.A.3 — billing emit tests for ``execute_dq_run``.

Pins three contracts that close 240.5.A:

1. **Emit-once on success.** Every SUCCEEDED DQ run produces
   exactly ONE ``billing.dq.run.completed`` event. No more, no
   less.
2. **No emit on failure.** A DQ run that ends in ``FAILED``
   status emits ZERO billing events — failed runs are not
   billable per the 240.5.A spec.
3. **Payload completeness.** The event payload carries the seven
   spec-required keys (``tenant_id``, ``dq_run_id``, ``engine``,
   ``rows_inspected``, ``columns_inspected``,
   ``execution_time_seconds``, ``quality_score``) with values
   sourced from the actual DQRun row + the dq-service result.

Real Django ORM rows + the real ``execute_dq_run`` codepath. The
only mocks are at the network/transport boundaries
(``S3StorageClient.download_file`` and
``DQServiceClient.run_dq``) — equivalent to a stub for an
external service. The billing-emit code itself runs unmocked
through ``hub.apps.billing.events.emit_event``; we observe the
emit at the module-attribute boundary so the assertion proves
the production codepath fired the event, not just that the
helper was importable.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.dq.tests.test_base import DQAPITransactionTestBase


pytestmark = pytest.mark.django_db(transaction=True)


# A canonical successful DQ-service result payload — matches the
# wire shape returned by ``services/dq-service/main.py`` /run when
# the input is a tiny CSV. We pin it here so the test doesn't
# regress when the dq-service shape evolves; if it does, this
# constant fails first and the diff is one place.
_SUCCESS_RESULT = {
    "overall_status": "PASS",
    "quality_score": 99.5,
    "checks": [],
    "engine_type": "GX",
    "engine_version": "0.18.x",
    "profile_key": "intake_basic_gx",
    "metadata": {
        "total_rows": 100,
        "total_columns": 4,
        "execution_time_seconds": 0.42,
        "timestamp": "2026-05-02T12:00:00Z",
    },
}


def _patch_storage():
    """Stub the S3 download — returns a minimal valid CSV body."""
    return patch(
        "hub.apps.files.storage.S3StorageClient.download_file",
        return_value=b"col_a,col_b\n1,2\n",
    )


def _patch_dq_service_success():
    """Stub the dq-service /run call — returns the canonical PASS payload."""
    return patch(
        "hub.apps.dq.service_client.DQServiceClient.run_dq",
        return_value=_SUCCESS_RESULT,
    )


def _patch_dq_service_failure():
    """Stub the dq-service /run call — raises to drive the failure path."""
    return patch(
        "hub.apps.dq.service_client.DQServiceClient.run_dq",
        side_effect=RuntimeError("simulated dq-service crash"),
    )


class DQRunBillingEmitTests(DQAPITransactionTestBase):

    def setUp(self):
        super().setUp()
        # Pre-seed a DQRun in PENDING state. ``engine`` is required
        # (DQRun.save() calls full_clean()); the GX adapter is
        # canonical for ``intake_basic_gx``.
        self.dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            status=DQRunStatus.PENDING,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
        )

    # ──────────────────────────────────────────────────────────────
    # Emit-once on success
    # ──────────────────────────────────────────────────────────────

    def test_emit_called_exactly_once_on_succeeded_run(self):
        """A successful ``execute_dq_run`` produces exactly one
        ``billing.dq.run.completed`` event. We patch
        ``emit_event`` at the module attribute the production
        callsite imports from, so a passing assertion is direct
        proof the production codepath fired."""
        from hub.apps.dq.views import execute_dq_run

        with _patch_storage(), _patch_dq_service_success():
            with patch(
                "hub.apps.billing.events.emit_event",
            ) as emit_spy:
                execute_dq_run(str(self.dq_run.id))

        self.assertEqual(
            emit_spy.call_count, 1,
            f"emit_event must fire exactly once on a SUCCEEDED DQ run; "
            f"got {emit_spy.call_count} calls. "
            f"call_args_list={emit_spy.call_args_list}",
        )

        # DQRun must have transitioned to SUCCEEDED — sanity check
        # that we actually exercised the success branch.
        self.dq_run.refresh_from_db()
        self.assertEqual(self.dq_run.status, DQRunStatus.SUCCEEDED)

    def test_emit_payload_contains_all_seven_spec_required_fields(self):
        """The 240.5.A spec pins seven keys in the payload:
        ``tenant_id``, ``dq_run_id``, ``engine``, ``rows_inspected``,
        ``columns_inspected``, ``execution_time_seconds``,
        ``quality_score``. Each value MUST be sourced from the
        real DQRun row (or the dq-service result for the
        engine-derived ones)."""
        from hub.apps.dq.views import execute_dq_run

        with _patch_storage(), _patch_dq_service_success():
            with patch(
                "hub.apps.billing.events.emit_event",
            ) as emit_spy:
                execute_dq_run(str(self.dq_run.id))

        self.assertEqual(emit_spy.call_count, 1)

        # The first positional/keyword arg pattern depends on the
        # callsite shape. We accept either ``emit_event(event_type,
        # payload, ...)`` positional or ``emit_event(event_type=..,
        # payload=.., ...)`` keyword. Resolve both into a single
        # ``payload`` dict.  Use a plain ``assert`` (not
        # ``assertIsNotNone``) so the type checker narrows away the
        # ``Optional`` for the subscript / ``in`` operations below.
        call = emit_spy.call_args
        payload = call.kwargs.get("payload")
        if payload is None and len(call.args) >= 2:
            payload = call.args[1]
        assert payload is not None, (
            f"emit_event call shape unexpected: {call}"
        )

        for key in (
            "tenant_id",
            "dq_run_id",
            "engine",
            "rows_inspected",
            "columns_inspected",
            "execution_time_seconds",
            "quality_score",
        ):
            self.assertIn(
                key, payload,
                f"Spec-required key {key!r} missing from emit "
                f"payload; got keys: {sorted(payload.keys())}",
            )

        # Value-level pins: tenant + run identity + dq-service result.
        self.assertEqual(payload["tenant_id"], str(self.tenant.id))
        self.assertEqual(payload["dq_run_id"], str(self.dq_run.id))
        self.assertEqual(payload["engine"], "GX")
        self.assertEqual(payload["rows_inspected"], 100)
        self.assertEqual(payload["columns_inspected"], 4)
        self.assertEqual(payload["quality_score"], 99.5)
        # ``execution_time_seconds`` is computed from
        # ``timezone.now() - dq_run.started_at`` so we can't pin
        # the exact value, but we can pin the type contract.
        self.assertIsInstance(
            payload["execution_time_seconds"], (int, float),
        )
        self.assertGreaterEqual(payload["execution_time_seconds"], 0)

    def test_emit_uses_canonical_event_type_constant(self):
        """The first positional arg to emit_event MUST equal the
        ``DQ_RUN_COMPLETED`` constant exported by
        ``hub.apps.billing.event_types``. This pins integration
        between the producer (DQ pipeline) and the constant
        registry — a typo would cause subscribers to silently
        miss events."""
        from hub.apps.billing.event_types import DQ_RUN_COMPLETED
        from hub.apps.dq.views import execute_dq_run

        with _patch_storage(), _patch_dq_service_success():
            with patch(
                "hub.apps.billing.events.emit_event",
            ) as emit_spy:
                execute_dq_run(str(self.dq_run.id))

        call = emit_spy.call_args
        event_type = call.kwargs.get("event_type")
        if event_type is None and len(call.args) >= 1:
            event_type = call.args[0]
        self.assertEqual(event_type, DQ_RUN_COMPLETED)

    # ──────────────────────────────────────────────────────────────
    # No emit on FAILED runs
    # ──────────────────────────────────────────────────────────────

    def test_emit_NOT_called_when_dq_service_raises(self):
        """A DQ run that crashes inside the dq-service call ends
        in ``FAILED`` status. Per the 240.5.A spec failed runs are
        NOT billable — no event must be emitted."""
        from hub.apps.dq.views import execute_dq_run

        with _patch_storage(), _patch_dq_service_failure():
            with patch(
                "hub.apps.billing.events.emit_event",
            ) as emit_spy:
                execute_dq_run(str(self.dq_run.id))

        self.assertEqual(
            emit_spy.call_count, 0,
            f"emit_event must NOT fire on a FAILED DQ run; "
            f"got {emit_spy.call_count} calls",
        )

        # Sanity: the DQRun should be in a failure terminal state.
        self.dq_run.refresh_from_db()
        self.assertIn(
            self.dq_run.status,
            (DQRunStatus.FAILED,),
            f"Test fixture broken: expected DQRun to land in "
            f"FAILED after dq-service raised, got "
            f"{self.dq_run.status!r}",
        )

    # ──────────────────────────────────────────────────────────────
    # Idempotency — second invocation does NOT double-emit
    # ──────────────────────────────────────────────────────────────

    def test_billing_failure_does_not_break_dq_run_pipeline(self):
        """Defence-in-depth: if the billing bus itself raises (e.g.
        Redis is down), the DQ run MUST still complete
        successfully. Billing emit is observability, not a
        load-bearing path. The emit failure is logged at WARN but
        the DQRun is still saved as SUCCEEDED."""
        from hub.apps.dq.views import execute_dq_run

        with _patch_storage(), _patch_dq_service_success():
            with patch(
                "hub.apps.billing.events.emit_event",
                side_effect=Exception("simulated billing bus outage"),
            ):
                # Should NOT raise even though emit_event blew up.
                execute_dq_run(str(self.dq_run.id))

        # DQRun still landed as SUCCEEDED despite the billing
        # failure — this is the contract for "billing is best-effort".
        self.dq_run.refresh_from_db()
        self.assertEqual(self.dq_run.status, DQRunStatus.SUCCEEDED)
