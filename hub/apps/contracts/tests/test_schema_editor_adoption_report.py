"""
Phase 227 Wave 2 (227.W2.4) — adoption-gate report tests.

Pins the join + ratio computation that gates Wave 2 → Wave 3
progression. Uses real DB rows (no mocks) — tenant + contract +
audit-event fixtures are created via the standard managers and the
``compute_adoption_report`` pure function is exercised end-to-end.

What we pin
-----------
* Tenants whose only contracts are structureless count toward the
  denominator.
* A ``SCHEMA_EDITOR_OPENED`` audit row inside the watch window moves
  a tenant to the numerator.
* Audit rows OUTSIDE the watch window do not count.
* Tenants with no contracts are excluded (vacuously satisfied).
* The empty-population case yields ``ratio=0.0`` (no division by zero).
* The ``--gate-threshold`` exit-code path: command exits non-zero
  when the ratio is below the threshold.
"""
from __future__ import annotations

import io
import uuid
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone


def _create_tenant(slug_prefix: str = "w24"):
    from hub.apps.tenants.models import Tenant
    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"{slug_prefix}-{suffix}",
        slug=f"{slug_prefix}-{suffix}",
    )


def _create_contract(tenant, *, hub_contract_json):
    from hub.apps.contracts.models import (
        Contract,
        ContractStatus,
        OriginalFormat,
        OriginalSpecType,
    )
    return Contract.objects.create(
        tenant=tenant,
        version=1,
        original_spec_type=OriginalSpecType.ODCS,
        original_spec_version="3.1.0",
        original_format=OriginalFormat.JSON,
        original_raw="{}",
        hub_contract_json=hub_contract_json,
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status=ContractStatus.DRAFT,
    )


def _record_editor_opened(tenant, *, when=None):
    from hub.apps.audit.models import AuditEvent
    return AuditEvent.objects.create(
        tenant=tenant,
        action="SCHEMA_EDITOR_OPENED",
        resource_type="CONTRACT",
        resource_id=tenant.id,
        result="SUCCESS",
        timestamp=when or timezone.now(),
        details_json={},
    )


_HC_OK = {
    "models": [
        {"name": "m", "fields": [{"name": "id", "data_type": "string"}]}
    ],
    "schema": {"fields": [{"name": "id", "data_type": "string"}]},
}
_HC_STRUCTURELESS = {"models": [], "schema": {"fields": []}}


@pytest.mark.django_db(transaction=True)
class AdoptionReportTests(TestCase):
    """``compute_adoption_report`` pure-function tests."""

    def test_empty_population_returns_zero_ratio(self):
        from hub.apps.contracts.management.commands.schema_editor_adoption_report import (
            compute_adoption_report,
        )

        report = compute_adoption_report(since_days=7)
        self.assertEqual(report["structureless_tenant_count"], 0)
        self.assertEqual(report["adopted_tenant_count"], 0)
        self.assertEqual(report["ratio"], 0.0)

    def test_tenant_with_structureless_only_counts_toward_denominator(self):
        from hub.apps.contracts.management.commands.schema_editor_adoption_report import (
            compute_adoption_report,
        )

        tenant = _create_tenant("denom")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)

        report = compute_adoption_report(
            since_days=7, include_tenants=True,
        )
        self.assertIn(str(tenant.id), report["structureless_tenant_ids"])
        self.assertEqual(report["adopted_tenant_count"], 0)

    def test_tenant_only_counts_once_even_with_multiple_structureless(self):
        from hub.apps.contracts.management.commands.schema_editor_adoption_report import (
            compute_adoption_report,
        )

        tenant = _create_tenant("dedup")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)

        report = compute_adoption_report(
            since_days=7, include_tenants=True,
        )
        # The same tenant should appear only once.
        self.assertEqual(
            report["structureless_tenant_ids"].count(str(tenant.id)), 1,
        )

    def test_tenant_with_structural_only_is_excluded(self):
        from hub.apps.contracts.management.commands.schema_editor_adoption_report import (
            compute_adoption_report,
        )

        tenant = _create_tenant("structural-only")
        _create_contract(tenant, hub_contract_json=_HC_OK)

        report = compute_adoption_report(
            since_days=7, include_tenants=True,
        )
        self.assertNotIn(str(tenant.id), report.get("structureless_tenant_ids", []))

    def test_audit_event_inside_window_promotes_to_numerator(self):
        from hub.apps.contracts.management.commands.schema_editor_adoption_report import (
            compute_adoption_report,
        )

        tenant = _create_tenant("adopted")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _record_editor_opened(tenant)

        report = compute_adoption_report(
            since_days=7, include_tenants=True,
        )
        self.assertEqual(report["structureless_tenant_count"], 1)
        self.assertEqual(report["adopted_tenant_count"], 1)
        self.assertEqual(report["ratio"], 1.0)

    def test_audit_event_outside_window_does_not_count(self):
        from hub.apps.contracts.management.commands.schema_editor_adoption_report import (
            compute_adoption_report,
        )

        tenant = _create_tenant("stale")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        # Record an opened event 30 days ago — outside a 7-day window.
        _record_editor_opened(
            tenant, when=timezone.now() - timedelta(days=30),
        )

        report = compute_adoption_report(since_days=7)
        self.assertEqual(report["structureless_tenant_count"], 1)
        self.assertEqual(
            report["adopted_tenant_count"], 0,
            "Stale audit row must not count against the watch-window gate",
        )

    def test_mixed_population_yields_correct_ratio(self):
        from hub.apps.contracts.management.commands.schema_editor_adoption_report import (
            compute_adoption_report,
        )

        # 3 structureless tenants; 1 of them opened the editor.
        t_open = _create_tenant("mixed-open")
        t_silent_a = _create_tenant("mixed-silent-a")
        t_silent_b = _create_tenant("mixed-silent-b")
        for t in (t_open, t_silent_a, t_silent_b):
            _create_contract(t, hub_contract_json=_HC_STRUCTURELESS)
        _record_editor_opened(t_open)

        report = compute_adoption_report(since_days=7)
        self.assertEqual(report["structureless_tenant_count"], 3)
        self.assertEqual(report["adopted_tenant_count"], 1)
        self.assertAlmostEqual(report["ratio"], 1 / 3, places=4)


@pytest.mark.django_db(transaction=True)
class AdoptionReportGateExitCodeTests(TestCase):
    """The management command exits non-zero when the gate fails."""

    def test_gate_threshold_exits_nonzero_on_underadoption(self):
        # 2 structureless tenants, none adopted → ratio 0 < threshold 0.30.
        for i in range(2):
            t = _create_tenant(f"under-{i}")
            _create_contract(t, hub_contract_json=_HC_STRUCTURELESS)

        # ``call_command`` raises ``SystemExit`` when ``raise SystemExit(1)``
        # is called inside the command; catch it here.
        out = io.StringIO()
        err = io.StringIO()
        with pytest.raises(SystemExit) as exc:
            call_command(
                "schema_editor_adoption_report",
                "--since-days=7",
                "--gate-threshold=0.30",
                "--output=json",
                stdout=out,
                stderr=err,
            )
        self.assertEqual(exc.value.code, 1)
        # Stderr carries the operator-facing failure message.
        self.assertIn("Adoption gate FAILED", err.getvalue())

    def test_gate_threshold_passes_when_adoption_exceeds(self):
        # 2 structureless tenants, both adopted → ratio 1.0 ≥ threshold 0.30.
        for i in range(2):
            t = _create_tenant(f"over-{i}")
            _create_contract(t, hub_contract_json=_HC_STRUCTURELESS)
            _record_editor_opened(t)

        out = io.StringIO()
        err = io.StringIO()
        # No SystemExit expected.
        call_command(
            "schema_editor_adoption_report",
            "--since-days=7",
            "--gate-threshold=0.30",
            "--output=json",
            stdout=out,
            stderr=err,
        )
        self.assertNotIn("Adoption gate FAILED", err.getvalue())

    def test_omitting_threshold_never_exits_nonzero(self):
        # No threshold specified → the command always exits 0.
        for i in range(3):
            t = _create_tenant(f"report-{i}")
            _create_contract(t, hub_contract_json=_HC_STRUCTURELESS)
        out = io.StringIO()
        # No SystemExit expected.
        call_command(
            "schema_editor_adoption_report",
            "--since-days=7",
            "--output=human",
            stdout=out,
        )
        self.assertIn("Adoption ratio", out.getvalue())
