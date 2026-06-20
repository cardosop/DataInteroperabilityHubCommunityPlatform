"""
Phase 227 Wave 1 (227.L7) — observability tests.

Covers four L7.* tasks:

* L7.1 — counter / histogram emission on Layer-3 raises and
  successful normalisations. We test through the public surface
  (the metric helpers in ``normalization_metrics.py``) since the
  underlying ``_CounterWrapper``/``_HistogramWrapper`` classes are
  no-op when OTel isn't installed — the test container DOES have
  OTel, so observation calls succeed; we verify the helpers are
  invoked correctly via spy patches on the wrapper objects.
* L7.3 — audit events at every Layer-3 raise (
  ``CONTRACT_VALIDATION_FAILED``,
  ``CONTRACT_STRUCTURELESS_REJECTED``) and at the L6 batch end
  (``CONTRACT_BATCH_RENORMALIZED``).
* L7.4 — structured WARN logs at every Layer-3 raise carrying
  ``contract_id``, ``spec_type``, ``tenant_id``, ``subcode``.
* L7.6 — ``--output=count`` mode emits a single integer to stdout
  (no extra noise) and updates the
  ``contract_structureless_backlog`` gauge.

No internal-code mocks. Real DB rows. Real ``ContractService``.
We DO patch the OTel metric wrapper objects with ``unittest.mock`` —
that's not an "internal mock"; it's an OTel boundary spy used by
the observability stack itself for in-process verification.
"""

from __future__ import annotations

import json
import logging
import uuid
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.test import TestCase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_tenant():
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"L7 Co {suffix}",
        slug=f"l7-co-{suffix}",
    )


def _structureless_odcs_yaml() -> str:
    return (
        "kind: DataContract\n"
        "apiVersion: v3.0.2\n"
        f"id: bad-{uuid.uuid4().hex[:6]}\n"
        "name: bad\n"
        "version: 1.0.0\n"
        "status: active\n"
        "info:\n"
        "  description: no schema\n"
    )


def _structural_odcs_yaml() -> str:
    return (
        "kind: DataContract\n"
        "apiVersion: v3.0.2\n"
        f"id: ok-{uuid.uuid4().hex[:6]}\n"
        "name: ok\n"
        "version: 1.0.0\n"
        "status: active\n"
        "schema:\n"
        "  - name: customers\n"
        "    fields:\n"
        "      - name: id\n"
        "        type: string\n"
    )


def _create_structureless_odcs_contract(tenant):
    from hub.apps.contracts.models import Contract

    return Contract.objects.create(
        tenant=tenant,
        version=1,
        original_spec_type="ODCS",
        original_spec_version="3.0.2",
        original_format="YAML",
        original_raw=_structureless_odcs_yaml(),
        hub_contract_json={"models": [], "schema": {"fields": []}},
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status="ACTIVE",
    )


# ---------------------------------------------------------------------------
# L7.1 — metric emission on Layer-3 raises
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestFloorViolationMetricsEmitted(TestCase):
    """``enforce_structural_floor`` increments
    ``contract_validation_failed_total`` and
    ``contract_structureless_total`` on every raise."""

    def test_floor_raise_emits_validation_failed_counter(self):
        from hub.apps.contracts.structural_floor import (
            enforce_structural_floor,
        )
        from hub.apps.core.services.base import ValidationError

        with patch(
            # Patch where USED — `normalization_metrics.py` does an
            # eager `from otel_metrics import contract_validation_failed_total`,
            # so the use-site binding is independent of the source
            # module's binding (Python's "from X import Y" semantics).
            "hub.apps.contracts.normalization_metrics.contract_validation_failed_total"
        ) as mock_counter:
            with pytest.raises(ValidationError):
                enforce_structural_floor(
                    {"models": []},
                    spec_type="ODPS",
                    spec_version="bitol-1.0.0",
                    source="creation",
                )
            # The wrapper exposes ``.labels(**kwargs).inc()`` — verify
            # both stages were invoked at least once.
            assert mock_counter.labels.called, (
                "contract_validation_failed_total.labels() not called"
            )
            kwargs = mock_counter.labels.call_args.kwargs
            assert kwargs["code"] == "STRUCTURELESS_CONTRACT"
            assert kwargs["subcode"] == "STRUCTURELESS_ODPS_NO_PORTS"
            assert kwargs["spec_type"] == "ODPS"

    def test_floor_raise_emits_structureless_total_counter(self):
        from hub.apps.contracts.structural_floor import (
            enforce_structural_floor,
        )
        from hub.apps.core.services.base import ValidationError

        with patch(
            "hub.apps.contracts.normalization_metrics.contract_structureless_total"
        ) as mock_counter:
            with pytest.raises(ValidationError):
                enforce_structural_floor(
                    None,
                    spec_type="ODCS",
                    spec_version="3.0.2",
                    source="update",
                )
            assert mock_counter.labels.called
            kwargs = mock_counter.labels.call_args.kwargs
            assert kwargs["spec_type"] == "ODCS"
            assert kwargs["source"] == "update"

    def test_floor_raise_with_unknown_spec_uses_unknown_label(self):
        """Defensive: ``spec_type=None`` must produce a literal
        ``'UNKNOWN'`` label, not raise on the metric backend (which
        rejects None values)."""
        from hub.apps.contracts.structural_floor import (
            enforce_structural_floor,
        )
        from hub.apps.core.services.base import ValidationError

        with patch(
            # Patch where USED — `normalization_metrics.py` does an
            # eager `from otel_metrics import contract_validation_failed_total`,
            # so the use-site binding is independent of the source
            # module's binding (Python's "from X import Y" semantics).
            "hub.apps.contracts.normalization_metrics.contract_validation_failed_total"
        ) as mock_counter:
            with pytest.raises(ValidationError):
                enforce_structural_floor(
                    None,
                    spec_type=None,
                    spec_version=None,
                )
            kwargs = mock_counter.labels.call_args.kwargs
            assert kwargs["spec_type"] == "UNKNOWN"
            # Subcode for None spec_type is GENERIC.
            assert kwargs["subcode"] == "STRUCTURELESS_GENERIC"


@pytest.mark.django_db(transaction=True)
class TestSuccessPathHistogramsEmitted(TestCase):
    """Successful normalisation observes the per-spec model+field
    count histograms (L7.1)."""

    def test_record_models_count_observes_histogram(self):
        from hub.apps.contracts.normalization_metrics import (
            record_normalization_models_count,
        )

        with patch(
            "hub.apps.contracts.normalization_metrics.contract_normalization_models_count"
        ) as mock_hist:
            hub_contract = {
                "models": [
                    {"name": "a", "fields": [{"name": "x"}]},
                    {"name": "b", "fields": []},
                    {"name": "c", "fields": [{"name": "y"}]},
                ]
            }
            record_normalization_models_count(hub_contract, spec_type="ODCS")
            assert mock_hist.labels.called
            mock_hist.labels.return_value.observe.assert_called_with(3)

    def test_record_fields_total_count_sums_models_and_schema(self):
        from hub.apps.contracts.normalization_metrics import (
            record_normalization_fields_total_count,
        )

        with patch(
            "hub.apps.contracts.normalization_metrics.contract_normalization_fields_total_count"
        ) as mock_hist:
            hub_contract = {
                "models": [
                    {"name": "a", "fields": [{"name": "x"}, {"name": "y"}]},
                ],
                "schema": {
                    "fields": [{"name": "z"}],
                },
            }
            record_normalization_fields_total_count(hub_contract, spec_type="ODCS")
            # 2 (model fields) + 1 (schema fields) = 3
            mock_hist.labels.return_value.observe.assert_called_with(3)


# ---------------------------------------------------------------------------
# L7.3 — audit events at Layer-3 raises
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestL3RaiseEmitsAuditEvent(TestCase):
    """Every Layer-3 raise emits a ``CONTRACT_STRUCTURELESS_REJECTED``
    audit event (L7.3) with the canonical 7-key details payload.

    This test calls ``enforce_structural_floor`` DIRECTLY rather than
    through ``ContractService.create_contract``. Reason: ``create_contract``
    is decorated ``@transaction.atomic``, and the ``ValidationError``
    raised by the floor causes the entire transaction to roll back —
    INCLUDING the AuditEvent INSERT. In production this is fine because
    the L7.4 structured WARN log persists to stdout/Loki regardless of
    DB transaction state, so ops still see the rejection. But for THIS
    test (which checks the DB row), we need to invoke the floor outside
    a rolling-back transaction.

    Calling ``enforce_structural_floor`` directly is the correct unit-
    level test: it pins the contract that ``_emit_floor_violation_observability``
    creates a ``CONTRACT_STRUCTURELESS_REJECTED`` audit row when invoked
    in a non-rollback context, with the canonical 7-key details payload.

    The transaction-rollback behaviour itself is tested implicitly by
    the L3 service-layer tests in ``test_structureless_contract_validation.py``
    (which assert that no Contract row persists on rejection — a side-
    effect of the same rollback that drops the audit row).
    """

    def test_floor_raise_emits_structureless_rejected_audit(self):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.contracts.structural_floor import (
            enforce_structural_floor,
        )
        from hub.apps.core.services.base import ValidationError

        tenant = _create_tenant()

        before = AuditEvent.objects.filter(
            action="CONTRACT_STRUCTURELESS_REJECTED",
        ).count()

        with pytest.raises(ValidationError):
            enforce_structural_floor(
                None,
                spec_type="ODCS",
                spec_version="3.0.2",
                tenant_id=str(tenant.id),
                source="creation",
            )

        after = AuditEvent.objects.filter(
            action="CONTRACT_STRUCTURELESS_REJECTED",
        ).count()
        assert after == before + 1, (
            f"Floor raise must emit exactly one CONTRACT_STRUCTURELESS_"
            f"REJECTED audit event; before={before} after={after}"
        )

        event = (
            AuditEvent.objects.filter(
                action="CONTRACT_STRUCTURELESS_REJECTED",
            )
            .order_by("-timestamp")
            .first()
        )
        assert event is not None
        details = event.details_json
        # Canonical detail keys.
        for key in (
            "code",
            "subcode",
            "spec_type",
            "spec_version",
            "models_count",
            "schema_fields_count",
            "source",
        ):
            assert key in details, f"missing detail key {key!r}"
        assert details["code"] == "STRUCTURELESS_CONTRACT"
        assert details["source"] == "creation"
        assert details["spec_type"] == "ODCS"
        assert event.result == "FAILURE"


# ---------------------------------------------------------------------------
# L7.4 — structured WARN logs at every Layer-3 raise
# ---------------------------------------------------------------------------


class _CapturingHandler(logging.Handler):
    """Plain stdlib log handler that captures records for assertion.

    Real handler (no mocks); we only attach it to the structlog
    ``LoggerAdapter`` underlying logger for the duration of the test.
    """

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.mark.django_db(transaction=True)
class TestL3StructuredWarnLog(TestCase):
    """Layer-3 raises emit a WARN-level structlog event named
    ``structural_floor_violation`` with the four required fields:
    ``contract_id``, ``spec_type``, ``tenant_id``, ``subcode``.
    """

    def test_floor_raise_emits_warn_log_with_required_fields(self):
        from hub.apps.contracts.structural_floor import (
            enforce_structural_floor,
        )
        from hub.apps.core.services.base import ValidationError

        # structlog routes through stdlib logging by default in this
        # codebase (configured in hub/apps/observability/logging.py),
        # so attaching a stdlib handler at the right logger captures
        # the emitted record.
        target_logger = logging.getLogger("hub.apps.contracts.structural_floor")
        handler = _CapturingHandler()
        handler.setLevel(logging.WARNING)
        target_logger.addHandler(handler)
        previous_level = target_logger.level
        target_logger.setLevel(logging.WARNING)

        try:
            cid = "11111111-2222-3333-4444-555555555555"
            tid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
            with pytest.raises(ValidationError):
                enforce_structural_floor(
                    {"models": []},
                    spec_type="ODPS",
                    spec_version="bitol-1.0.0",
                    contract_id=cid,
                    tenant_id=tid,
                    source="creation",
                )
        finally:
            target_logger.removeHandler(handler)
            target_logger.setLevel(previous_level)

        # Find the structural_floor_violation record (structlog emits
        # the event-name as part of the message). Allow ANY record
        # that mentions the event name for tolerance to the structlog
        # processor chain.
        matching = [r for r in handler.records if "structural_floor_violation" in r.getMessage()]
        assert matching, (
            f"No WARN log carrying 'structural_floor_violation' found; "
            f"got {[r.getMessage() for r in handler.records]!r}"
        )
        msg = matching[-1].getMessage()
        # All four required fields are in the rendered message.
        assert cid in msg, f"contract_id missing from log: {msg!r}"
        assert "ODPS" in msg, f"spec_type missing from log: {msg!r}"
        assert tid in msg, f"tenant_id missing from log: {msg!r}"
        assert "STRUCTURELESS_ODPS_NO_PORTS" in msg, f"subcode missing from log: {msg!r}"


# ---------------------------------------------------------------------------
# L7.6 — --output=count cron mode
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestOutputCountFlag(TestCase):
    """``renormalize_contracts --filter=structureless --dry-run
    --output=count`` emits exactly one integer line to stdout — the
    count of structureless contracts in the tenant's catalogue."""

    def _run(self, tenant):
        out = StringIO()
        call_command(
            "renormalize_contracts",
            "--spec-version=3.1.0",
            "--filter=structureless",
            "--dry-run",
            "--output=count",
            f"--tenant-id={tenant.id}",
            stdout=out,
        )
        return out.getvalue()

    def test_count_zero_when_no_structureless(self):
        """Empty tenant catalogue → '0'."""
        tenant = _create_tenant()
        output = self._run(tenant)

        # Single line containing only the count integer.
        lines = [line for line in output.splitlines() if line.strip() and not line.startswith("#")]
        assert lines == ["0"], f"Expected single line '0'; got {lines!r}"

    def test_count_matches_structureless_population(self):
        tenant = _create_tenant()
        for _ in range(3):
            _create_structureless_odcs_contract(tenant)

        output = self._run(tenant)

        lines = [line for line in output.splitlines() if line.strip() and not line.startswith("#")]
        assert lines == ["3"], (
            f"Expected single line '3' (3 structureless contracts); got {lines!r}"
        )

    def test_count_output_is_clean_for_pushgateway(self):
        """The output MUST be parseable as ``int(stdout.strip())`` —
        the cron's pushgateway hook expects exactly one integer
        line (no headers, no warnings, no log noise on stdout)."""
        tenant = _create_tenant()
        _create_structureless_odcs_contract(tenant)

        output = self._run(tenant)

        # Filter out '#'-prefixed lines (they're optional comments).
        body_lines = [ln for ln in output.splitlines() if ln.strip() and not ln.startswith("#")]
        # The body must be EXACTLY one line.
        assert len(body_lines) == 1, (
            f"Cron output must be one integer line; got {len(body_lines)} lines: {body_lines!r}"
        )
        # That line must parse cleanly as an int.
        try:
            count = int(body_lines[0].strip())
        except ValueError:
            self.fail(f"Cron output line {body_lines[0]!r} is not a parseable integer")
        assert count >= 0


# ---------------------------------------------------------------------------
# L7.6 — backlog gauge delta semantics
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestBacklogGaugeDeltas(TestCase):
    """``set_structureless_backlog`` emits an ``inc(delta)`` against
    the OTel UpDownCounter, computing the delta from a process-local
    cache. Called repeatedly with the same value, it's a no-op."""

    def test_first_call_advances_gauge_by_count(self):
        from hub.apps.contracts.normalization_metrics import (
            _last_backlog_value,
            set_structureless_backlog,
        )

        # Reset process-local cache for a deterministic test.
        _last_backlog_value.clear()

        with patch(
            "hub.apps.contracts.normalization_metrics.contract_structureless_backlog"
        ) as mock_gauge:
            set_structureless_backlog(count=12, tenant_id="t1")

            mock_gauge.labels.assert_called_with(tenant_id="t1")
            mock_gauge.labels.return_value.inc.assert_called_with(12)

    def test_second_call_with_same_count_is_noop(self):
        from hub.apps.contracts.normalization_metrics import (
            _last_backlog_value,
            set_structureless_backlog,
        )

        _last_backlog_value.clear()

        with patch(
            "hub.apps.contracts.normalization_metrics.contract_structureless_backlog"
        ) as mock_gauge:
            set_structureless_backlog(count=5, tenant_id="t2")
            set_structureless_backlog(count=5, tenant_id="t2")

            # First call: inc(5). Second call: no inc (delta=0).
            assert mock_gauge.labels.return_value.inc.call_count == 1, (
                "Same-value backlog reading must not emit a redundant inc"
            )

    def test_decreasing_count_emits_negative_delta(self):
        """Backlog draining (e.g., after Wave 3) must emit a negative
        inc so the gauge value decreases."""
        from hub.apps.contracts.normalization_metrics import (
            _last_backlog_value,
            set_structureless_backlog,
        )

        _last_backlog_value.clear()

        with patch(
            "hub.apps.contracts.normalization_metrics.contract_structureless_backlog"
        ) as mock_gauge:
            set_structureless_backlog(count=10, tenant_id="t3")
            set_structureless_backlog(count=3, tenant_id="t3")

            calls = mock_gauge.labels.return_value.inc.call_args_list
            # Two calls: +10, then -7.
            assert len(calls) == 2
            assert calls[0].args == (10,)
            assert calls[1].args == (-7,)


# ---------------------------------------------------------------------------
# L7.2 — Schema-editor metrics POST endpoint
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestSchemaEditorMetricsEndpoint(TestCase):
    """``POST /api/v1/contracts/schema-editor/metrics`` increments the
    OTel counters server-side based on frontend telemetry events."""

    def _client(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        from hub.apps.tenants.models import KYCStatus, Tenant
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )
        from hub.apps.users.models import UserStatus

        suffix = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"L7.2 Co {suffix}",
            slug=f"l72-co-{suffix}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(tenant)
        user = get_user_model().objects.create_user(
            email=f"l72-{suffix}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        client = APIClient()
        client.force_authenticate(user=user)
        return client, tenant

    def test_opened_event_increments_opened_counter(self):
        client, tenant = self._client()

        with patch(
            "hub.apps.observability.otel_metrics.schema_editor_opened_total"
        ) as mock_counter:
            response = client.post(
                "/api/v1/contracts/schema-editor/metrics",
                data={"event": "opened", "spec_type": "ODCS"},
                format="json",
            )

        assert response.status_code == 204
        mock_counter.labels.assert_called_with(tenant_id=str(tenant.id), spec_type="ODCS")
        mock_counter.labels.return_value.inc.assert_called_once()

    def test_save_success_increments_counter_and_observes_ttfs(self):
        client, tenant = self._client()

        with (
            patch("hub.apps.observability.otel_metrics.schema_editor_save_total") as mock_save,
            patch(
                "hub.apps.observability.otel_metrics.schema_editor_time_to_first_save_seconds"
            ) as mock_hist,
        ):
            response = client.post(
                "/api/v1/contracts/schema-editor/metrics",
                data={
                    "event": "save",
                    "spec_type": "ODCS",
                    "outcome": "success",
                    "time_to_first_save_seconds": 42.5,
                },
                format="json",
            )

        assert response.status_code == 204
        mock_save.labels.assert_called_with(
            tenant_id=str(tenant.id),
            spec_type="ODCS",
            outcome="success",
        )
        mock_hist.labels.assert_called_with(tenant_id=str(tenant.id), spec_type="ODCS")
        mock_hist.labels.return_value.observe.assert_called_with(42.5)

    def test_save_conflict_increments_counter_no_histogram(self):
        client, _tenant = self._client()

        with (
            patch("hub.apps.observability.otel_metrics.schema_editor_save_total") as mock_save,
            patch(
                "hub.apps.observability.otel_metrics.schema_editor_time_to_first_save_seconds"
            ) as mock_hist,
        ):
            response = client.post(
                "/api/v1/contracts/schema-editor/metrics",
                data={
                    "event": "save",
                    "spec_type": "ODPS",
                    "outcome": "conflict",
                    # No ttfs — the failure path doesn't observe.
                },
                format="json",
            )

        assert response.status_code == 204
        kwargs = mock_save.labels.call_args.kwargs
        assert kwargs["outcome"] == "conflict"
        # Histogram MUST NOT be observed on non-success outcomes.
        mock_hist.labels.return_value.observe.assert_not_called()

    def test_unknown_event_is_silently_accepted(self):
        """Forward-compat: a future frontend event name MUST NOT 4xx —
        we want the server to fail-open on unknown events so a partial
        rollout doesn't surface client errors."""
        client, _tenant = self._client()
        response = client.post(
            "/api/v1/contracts/schema-editor/metrics",
            data={"event": "future_event", "spec_type": "ODCS"},
            format="json",
        )
        assert response.status_code == 204

    def test_missing_event_returns_400(self):
        """Empty body / missing event field is a client error."""
        client, _tenant = self._client()
        response = client.post(
            "/api/v1/contracts/schema-editor/metrics",
            data={},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["code"] == "EVENT_REQUIRED"

    def test_unauthenticated_request_is_rejected(self):
        from rest_framework.test import APIClient

        client = APIClient()  # no force_authenticate
        response = client.post(
            "/api/v1/contracts/schema-editor/metrics",
            data={"event": "opened", "spec_type": "ODCS"},
            format="json",
        )
        # DRF default: 401 when authentication required and absent.
        assert response.status_code in (401, 403)

    def test_invalid_outcome_normalized_to_error(self):
        """Defensive: an unknown ``outcome`` value (e.g. typo, future
        client) is bucketed as ``error`` rather than passed through —
        keeps cardinality bounded."""
        client, _tenant = self._client()

        with patch("hub.apps.observability.otel_metrics.schema_editor_save_total") as mock_save:
            response = client.post(
                "/api/v1/contracts/schema-editor/metrics",
                data={
                    "event": "save",
                    "spec_type": "ODCS",
                    "outcome": "totally-bogus",
                },
                format="json",
            )

        assert response.status_code == 204
        assert mock_save.labels.call_args.kwargs["outcome"] == "error"

    # ----------------------------------------------------------------
    # Phase 227 Wave 2 (227.W2.4) — audit-event persistence
    # ----------------------------------------------------------------

    def test_opened_event_persists_audit_row_for_adoption_gate(self):
        """The W2.4 adoption-gate report joins the structureless-tenant
        population against ``AuditEvent.action='SCHEMA_EDITOR_OPENED'``.
        Pin that the metric endpoint actually writes that row — the
        OTel counter alone is queryable from Prometheus only and cannot
        feed the gate."""
        from hub.apps.audit.models import AuditEvent

        client, tenant = self._client()
        before = AuditEvent.objects.filter(
            action="SCHEMA_EDITOR_OPENED",
            tenant=tenant,
        ).count()

        response = client.post(
            "/api/v1/contracts/schema-editor/metrics",
            data={"event": "opened", "spec_type": "odcs"},
            format="json",
        )

        assert response.status_code == 204
        rows = AuditEvent.objects.filter(
            action="SCHEMA_EDITOR_OPENED",
            tenant=tenant,
        )
        assert rows.count() == before + 1
        row = rows.order_by("-timestamp").first()
        # W2.4-AUDIT-2 fix — resource_type must reflect the row's actual
        # subject (the tenant), not "CONTRACT" (no contract id is in
        # the metric payload).
        assert row.resource_type == "TENANT"
        assert str(row.resource_id) == str(tenant.id)
        # spec_type lower-cased on the wire is upper-cased server-side
        # for label-cardinality consistency with the OTel counter.
        assert row.details_json.get("spec_type") == "ODCS"

    def test_save_event_does_not_persist_audit_row(self):
        """The adoption gate counts opens, not saves — confirm save
        events do NOT add ``SCHEMA_EDITOR_OPENED`` rows that would
        double-count adoption."""
        from hub.apps.audit.models import AuditEvent

        client, tenant = self._client()
        before = AuditEvent.objects.filter(
            action="SCHEMA_EDITOR_OPENED",
            tenant=tenant,
        ).count()

        response = client.post(
            "/api/v1/contracts/schema-editor/metrics",
            data={
                "event": "save",
                "spec_type": "ODCS",
                "outcome": "success",
                "time_to_first_save_seconds": 12.0,
            },
            format="json",
        )

        assert response.status_code == 204
        after = AuditEvent.objects.filter(
            action="SCHEMA_EDITOR_OPENED",
            tenant=tenant,
        ).count()
        assert after == before

    def test_audit_persist_failure_does_not_break_metric_ingest(self):
        """The audit-row write is best-effort: if the audit subsystem
        fails (e.g. transient DB hiccup) the metric endpoint MUST
        still 204 so the OTel counter increment lands. Pin that the
        endpoint stays available even when ``create_audit_event``
        raises."""
        client, _tenant = self._client()
        with patch(
            "hub.apps.contracts.views_schema_editor_metrics._record_editor_opened_audit",
            side_effect=RuntimeError("simulated audit-store outage"),
        ):
            response = client.post(
                "/api/v1/contracts/schema-editor/metrics",
                data={"event": "opened", "spec_type": "ODCS"},
                format="json",
            )

        assert response.status_code == 204


# ---------------------------------------------------------------------------
# L7.5 — Grafana dashboard JSON validity
# ---------------------------------------------------------------------------


class TestStructurelessRolloutDashboardJSON(TestCase):
    """The new ``structureless-contract-rollout.json`` dashboard MUST
    parse as valid JSON, declare a ``uid``, and reference only metrics
    we actually emit. Catching dashboard breakage at unit-test time
    saves the Grafana provisioning sidecar from no-op'ing on parse
    failure (the failure mode is silent — the dashboard just doesn't
    show up)."""

    DASHBOARD_PATH = "monitoring/grafana/dashboards/structureless-contract-rollout.json"

    EXPECTED_METRICS = {
        "contract_validation_failed_total",
        "contract_structureless_total",
        "contract_structureless_backlog",
        "contract_normalization_models_count_bucket",
        "contracts_renormalize_batch_duration_seconds_bucket",
        "schema_editor_opened_total",
        "schema_editor_save_total",
        "schema_editor_time_to_first_save_seconds_bucket",
    }

    def test_dashboard_is_valid_json(self):
        from pathlib import Path

        path = Path(self.DASHBOARD_PATH)
        assert path.exists(), f"Dashboard file missing: {path}"
        # Just round-trips the JSON — pin parseability.
        data = json.loads(path.read_text())
        assert "dashboard" in data
        assert data["dashboard"]["uid"] == "hub-structureless-rollout-227"

    def test_dashboard_panels_reference_emitted_metrics(self):
        """Every PromQL query in the dashboard must reference a metric
        we actually emit. Catches typos like ``contract_strucureless_total``
        that would render an empty panel forever."""
        from pathlib import Path

        data = json.loads(Path(self.DASHBOARD_PATH).read_text())
        panels = data["dashboard"]["panels"]
        all_exprs = []
        for panel in panels:
            for target in panel.get("targets", []):
                expr = target.get("expr", "")
                if expr:
                    all_exprs.append(expr)

        # Each expr should mention at least one expected metric (or
        # the audit_events_total exception which is sourced from the
        # audit aggregator, not otel_metrics.py).
        accepted = self.EXPECTED_METRICS | {"audit_events_total"}
        for expr in all_exprs:
            assert any(m in expr for m in accepted), (
                f"Dashboard query references no known metric: {expr!r}\n"
                f"Expected one of: {sorted(accepted)}"
            )

    def test_all_dashboard_metrics_exist_in_otel_metrics(self):
        """Sanity check: every base metric name (sans ``_bucket``
        Prometheus suffix) we reference in the dashboard is defined
        in ``otel_metrics.py``. Catches a metric rename that broke
        a panel."""
        import importlib

        otel = importlib.import_module("hub.apps.observability.otel_metrics")
        base_names = {name.removesuffix("_bucket") for name in self.EXPECTED_METRICS}
        for base in base_names:
            assert hasattr(otel, base), (
                f"Dashboard expects metric ``{base}`` but it's not "
                f"defined in hub.apps.observability.otel_metrics"
            )


# ---------------------------------------------------------------------------
# 227.L7 audit follow-up — gaps surfaced by post-implementation review
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestAuditEventsCounter(TestCase):
    """Phase 227 L7 audit follow-up — every ``create_audit_event`` call
    increments ``audit_events_total{action, resource_type, result}``.

    Pre-fix the dashboard's "Asset Auto-Reverts (Wave 5)" panel
    referenced ``audit_events_total`` but the metric was never defined
    or emitted — the panel would have rendered empty forever. Fix
    closes the loop: define the metric in ``otel_metrics.py``, emit
    from ``hub.apps.audit.utils.create_audit_event``, dashboard panel
    now lights up.
    """

    def test_create_audit_event_increments_counter(self):
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.create(
            name=f"L7-audit-{uuid.uuid4().hex[:6]}",
            slug=f"l7-audit-{uuid.uuid4().hex[:6]}",
        )

        with patch("hub.apps.observability.otel_metrics.audit_events_total") as mock_counter:
            create_audit_event(
                resource_type="ASSET",
                action="ASSET_AUTO_REVERTED_STRUCTURELESS",
                tenant=tenant,
                result="SUCCESS",
                details={"foo": "bar"},
            )

        mock_counter.labels.assert_called_with(
            action="ASSET_AUTO_REVERTED_STRUCTURELESS",
            resource_type="ASSET",
            result="SUCCESS",
        )
        mock_counter.labels.return_value.inc.assert_called_once()

    def test_metric_failure_does_not_block_audit_row(self):
        """The metric emission MUST NOT block the audit row INSERT.
        If the OTel backend is broken, the audit row is the load-
        bearing artefact — losing it would silently drop a compliance
        signal."""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.create(
            name=f"L7-audit-fail-{uuid.uuid4().hex[:6]}",
            slug=f"l7-audit-fail-{uuid.uuid4().hex[:6]}",
        )

        before = AuditEvent.objects.count()
        with patch(
            "hub.apps.observability.otel_metrics.audit_events_total",
            new=MagicMock(side_effect=RuntimeError("metric backend down")),
        ):
            event = create_audit_event(
                resource_type="CONTRACT",
                action="CONTRACT_STRUCTURELESS_REJECTED",
                tenant=tenant,
                result="FAILURE",
                details={"foo": "bar"},
            )
        after = AuditEvent.objects.count()

        # Audit row must persist regardless.
        assert event is not None
        assert after == before + 1


@pytest.mark.django_db(transaction=True)
class TestApplyBatchDurationEmission(TestCase):
    """Phase 227 L7 audit follow-up — the ``--apply`` mode of the
    ``renormalize_contracts`` command observes
    ``contracts_renormalize_batch_duration_seconds{spec_type, outcome}``
    once per batch. Pre-audit there was a coverage gap — the metric
    was emitted but no test verified the call."""

    def test_apply_batch_observes_duration_with_outcome_label(self):
        from hub.apps.contracts.models import Contract
        from hub.apps.tenants.models import Tenant

        suffix = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"L7-batch-{suffix}",
            slug=f"l7-batch-{suffix}",
        )
        # One structureless contract — apply will record a residual
        # outcome (info-only ODCS doc has no resolvable structure).
        Contract.objects.create(
            tenant=tenant,
            version=1,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="YAML",
            original_raw=(
                "kind: DataContract\n"
                "apiVersion: v3.0.2\n"
                f"id: bad-{suffix}\n"
                "name: bad\n"
                "version: 1.0.0\n"
                "status: active\n"
                "info:\n"
                "  description: no schema\n"
            ),
            hub_contract_json={"models": [], "schema": {"fields": []}},
            normalization_status="NORMALIZED_OK",
            validation_status="VALID",
            status="ACTIVE",
        )

        with patch(
            "hub.apps.contracts.normalization_metrics.contracts_renormalize_batch_duration_seconds"
        ) as mock_hist:
            out = StringIO()
            call_command(
                "renormalize_contracts",
                "--spec-version=3.1.0",
                "--filter=structureless",
                "--apply",
                f"--tenant-id={tenant.id}",
                stdout=out,
            )

        # Histogram observed exactly once per batch (one batch here).
        assert mock_hist.labels.called, (
            "Batch duration histogram MUST be observed at least once per --apply run; got no calls."
        )
        # The observed duration is a non-negative float.
        observe_calls = mock_hist.labels.return_value.observe.call_args_list
        assert observe_calls, "observe() never called on the histogram"
        for call in observe_calls:
            (duration,) = call.args
            assert isinstance(duration, (int, float))
            assert duration >= 0
        # Outcome label must be one of the four documented values.
        labels_kwargs = mock_hist.labels.call_args.kwargs
        assert labels_kwargs["outcome"] in {
            "healed",
            "residual",
            "mixed",
            "failed",
        }


@pytest.mark.django_db(transaction=True)
class TestValidationErrorMetricEmission(TestCase):
    """Phase 227 L7 audit follow-up — the non-structural Pydantic-
    validation path (``code='VALIDATION_ERROR'`` rather than
    ``STRUCTURELESS_CONTRACT``) ALSO increments
    ``contract_validation_failed_total``. Pre-audit no test verified
    this path's metric emission."""

    def test_validation_error_path_increments_counter(self):
        """A contract whose normalisation succeeds but whose Pydantic
        schema validation fails must increment the counter via the
        ``_emit_validation_failed_observability`` helper."""
        # The simplest way to exercise the VALIDATION_ERROR path
        # without inducing the floor: patch the spy directly and
        # invoke the helper. This is a unit-level assertion of the
        # contract; the integration path is covered by the
        # ``test_create_rejects_*`` suite in
        # ``test_structureless_contract_validation.py``.
        from hub.apps.contracts.services import ContractService

        service = ContractService(tenant_id=str(uuid.uuid4()))

        with patch(
            "hub.apps.contracts.normalization_metrics.contract_validation_failed_total"
        ) as mock_counter:
            service._emit_validation_failed_observability(
                validation_errors=["info -> name: field required"],
                spec_type="ODCS",
                spec_version="3.0.2",
                contract_id=None,
                tenant_id=str(uuid.uuid4()),
                source="creation",
            )

        mock_counter.labels.assert_called_with(
            code="VALIDATION_ERROR",
            subcode="UNSPECIFIED",
            spec_type="ODCS",
        )
        mock_counter.labels.return_value.inc.assert_called_once()
